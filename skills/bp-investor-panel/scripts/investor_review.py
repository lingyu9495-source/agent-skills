#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
investor_review.py — 投资人评审团主引擎

对一份 BP（支持 yaml / json / md）逐页挑刺，每个投资人角色由一个"独立的大模型"
扮演，产出结构化评审 JSON。多角色 × 多模型交叉评审，天然带分歧。

用法：
    python3 investor_review.py --bp engine/bp_content.yaml --out review
    python3 investor_review.py --bp sample_bp.md --round 2 --out review
    python3 investor_review.py --bp bp.yaml --roles early_vc,pe_buyout   # 只跑指定角色
    python3 investor_review.py --bp bp.yaml --dry-run                    # 只探测模型，不评审
    python3 investor_review.py --list-models

产出：
    review/review-raw.json      原始多模型响应（含逐角色解析结果与引用校验）
    review/score-history.json   评分轨迹（每轮追加）
    review/review-run.log       运行日志

设计要点（为什么这么做）：
  1. 角色隔离：每个角色一次独立的 API 调用，prompt 内不含其他角色的输出，避免"串味"。
  2. 引用必须为真：模型给出的 quote 会被回原文校验（去空白/去标点后子串匹配），
     校验失败的条目标记 quote_verified=false 并在报告中降权——防止模型编原文。
  3. 加权复算：模型自报 total_score 之外，我方用角色 weights × dimension_scores 复算一遍，
     两者偏差 >10 分会被标记，说明模型打分与自己的维度分不自洽。
  4. 缺 key 自动降级：每个 provider 缺失或被拒时跳过并记录原因，报告里明写局限。
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

HERE = Path(__file__).resolve().parent
BP_SKILL = HERE.parent

# 六个核心加权维度（角色 weights 的键必须取自这里）
DIMENSIONS = ["市场", "团队", "产品壁垒", "商业模式", "财务预测", "融资方案"]
# 闸门维度：不参与加权平均，但低于角色阈值即触发一票否决（政府基金/国资角色尤其看重）
GATE_DIMENSION = "风险合规"
ALL_DIMS = DIMENSIONS + [GATE_DIMENSION]

# ---------------------------------------------------------------------------
# 1. 模型注册表：provider → base_url / key 环境变量候选 / 模型清单
#    新增模型：在 models 里加一行即可；key 从 env 读，缺失自动跳过。
# ---------------------------------------------------------------------------
PROVIDERS = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "key_envs": ["DEEPSEEK_API_KEY"],
        "json_mode": True,
        "models": {
            # 注意：deepseek-flash 是推理型，reasoning_tokens 会吃掉输出预算。
            # 4096 会导致"思考完就没 token 输出 JSON"，故必须给大预算。
            "deepseek-flash":   {"max_tokens": 16384},
            "deepseek-v4-pro":  {"max_tokens": 32768},
        },
    },
    "qwen": {
        "label": "阿里云百炼 / Qwen",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_envs": ["DASHSCOPE_API_KEY", "QWEN_API_KEY"],
        "json_mode": True,
        "models": {
            "qwen-plus":  {"max_tokens": 8192},
            "qwen-max":   {"max_tokens": 8192},
            "qwen-turbo": {"max_tokens": 8192},
        },
    },
    "moonshot": {
        "label": "Kimi / Moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "key_envs": ["MOONSHOT_API_KEY", "KIMI_API_KEY"],
        "models": {
            "moonshot-v1-8k": {"max_tokens": 4096},
            # 注意：kimi-k3 类长上下文/推理模型需 max_tokens≥32768，否则会返回 400
            "kimi-k2-0905-preview": {"max_tokens": 32768},
        },
    },
    "ark": {
        "label": "豆包 / 火山方舟",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "key_envs": ["ARK_API_KEY", "DOUBAO_API_KEY"],
        "models": {
            # 方舟多为 endpoint id（ep-xxxx）或带日期的模型名；按账户实际可用性填
            "doubao-seed-1-6-250615": {"max_tokens": 4096},
            "doubao-1-5-pro-32k-250115": {"max_tokens": 4096},
        },
    },
}

# 从这些文件补读 env（key 不在环境变量里时的兜底），不覆盖已有环境变量
ENV_FALLBACK_FILES = [
    Path.home() / ".hermes" / ".env",
    Path.home() / ".env",
    HERE / ".env",
]


def log(msg):
    """日志写「当前工作目录」，绝不写进脚本所在目录——否则从技能包调用会污染技能包。"""
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        with open(Path.cwd() / "review-run.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def find_roles_file(explicit=None):
    """定位 roles.yaml：兼容「与脚本同目录」「templates/ 子目录」「技能包根/templates」三种布局，
    并允许 --roles-file 显式指定。角色库是数据，不该被写死在某个固定路径上。"""
    cands = []
    if explicit:
        cands.append(Path(explicit))
    cands += [
        HERE / "roles.yaml",
        HERE / "templates" / "roles.yaml",
        HERE.parent / "templates" / "roles.yaml",
        HERE.parent / "roles.yaml",
        Path.cwd() / "roles.yaml",
        Path.cwd() / "templates" / "roles.yaml",
    ]
    for c in cands:
        if c.exists():
            return c
    raise FileNotFoundError(
        "找不到 roles.yaml；用 --roles-file 指定，或放到以下任一位置："
        + "、".join(str(c) for c in cands))


def load_env():
    """环境变量优先；缺的从 .env 文件补。返回 {provider: key} 及补齐来源说明。"""
    for p in ENV_FALLBACK_FILES:
        if not p.exists():
            continue
        try:
            for raw in p.read_text(encoding="utf-8").splitlines():
                raw = raw.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                k, v = raw.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and v and k not in os.environ:
                    os.environ[k] = v
        except Exception as e:  # noqa
            log(f"WARN 读 env 文件失败 {p}: {e}")


def resolve_key(prov):
    for env_name in PROVIDERS[prov]["key_envs"]:
        v = os.environ.get(env_name)
        if v:
            return v, env_name
    return None, None


def _post(url, key, payload, timeout=180):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def call_model(provider, model, messages, max_tokens=4096, retries=2, json_mode=None):
    """返回 (content, meta)；出错抛异常。meta 含 finish_reason（用于截断判定）。"""
    cfg = PROVIDERS[provider]
    key, key_name = resolve_key(provider)
    if not key:
        raise RuntimeError(f"缺 key（{'/'.join(cfg['key_envs'])}）")
    if json_mode is None:
        json_mode = bool(cfg.get("json_mode"))
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    last = None
    for attempt in range(retries + 1):
        try:
            t0 = time.time()
            try:
                data = _post(f"{cfg['base_url']}/chat/completions", key, payload)
            except urllib.error.HTTPError as e:
                # 有些 provider/模型不支持 response_format → 去掉重试一次
                if e.code == 400 and "response_format" in payload:
                    payload.pop("response_format")
                    data = _post(f"{cfg['base_url']}/chat/completions", key, payload)
                else:
                    raise
            ch = data["choices"][0]
            msg = ch["message"]
            content = (msg.get("content") or "").strip()
            # 推理型模型可能把答案放在 reasoning_content，content 为空
            if not content and msg.get("reasoning_content"):
                content = msg["reasoning_content"].strip()
            usage = data.get("usage", {})
            return content, {
                "key_env": key_name,
                "latency_s": round(time.time() - t0, 1),
                "finish_reason": ch.get("finish_reason"),
                "usage": usage,
            }
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:300]
            last = f"HTTP {e.code}: {body}"
            if e.code in (429, 500, 502, 503) and attempt < retries:
                time.sleep(3 * (attempt + 1))
                continue
            raise RuntimeError(last)
        except Exception as e:  # noqa
            last = f"{type(e).__name__}: {e}"
            if attempt < retries:
                time.sleep(3 * (attempt + 1))
                continue
            raise RuntimeError(last)
    raise RuntimeError(last or "unknown")


def probe_models(models=None, timeout=45):
    """真实探测每个模型是否可用。返回 (available[list], skipped[list])。"""
    available, skipped = [], []
    targets = models or [
        (p, m) for p, cfg in PROVIDERS.items() for m in cfg["models"]
    ]
    for provider, model in targets:
        key, key_name = resolve_key(provider)
        if not key:
            skipped.append({"provider": provider, "model": model,
                            "reason": f"无 key（{'/'.join(PROVIDERS[provider]['key_envs'])} 均未设置）"})
            continue
        try:
            mt = PROVIDERS[provider]["models"].get(model, {}).get("max_tokens", 32)
            content, meta = call_model(
                provider, model,
                [{"role": "user", "content": "回复两个字：可用"}],
                max_tokens=min(mt, 32), retries=0,
            )
            available.append({"provider": provider, "model": model, **meta, "echo": content[:40]})
            log(f"OK   模型可用 {PROVIDERS[provider]['label']}/{model} (key={key_name}, {meta['latency_s']}s)")
        except Exception as e:
            skipped.append({"provider": provider, "model": model, "reason": str(e)[:200]})
            log(f"SKIP 模型不可用 {PROVIDERS[provider]['label']}/{model} → {str(e)[:120]}")
    return available, skipped


# ---------------------------------------------------------------------------
# 2. BP 加载：yaml / json / md → pages: [{page:int, section:str, text:str}]
# ---------------------------------------------------------------------------
SKIP_TOP_KEYS = {"meta", "theme", "fonts", "confidential"}


def _flatten(obj, prefix=""):
    lines = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            lines += _flatten(v, f"{k}" if not prefix else f"{prefix}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj, 1):
            lines += _flatten(v, f"{prefix}[{i}]")
    else:
        lines.append(f"{prefix}: {obj}")
    return lines


def _pages_from_dict(d):
    pages = []
    for i, (k, v) in enumerate(d.items(), 1):
        if k in SKIP_TOP_KEYS:
            continue
        pages.append({"page": len(pages) + 1, "section": k, "text": "\n".join(_flatten(v, k))})
    return pages


def load_bp(path):
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    suf = p.suffix.lower()
    if suf in (".yaml", ".yml"):
        if yaml is None:
            raise RuntimeError("需要 pyyaml：pip install pyyaml")
        return _pages_from_dict(yaml.safe_load(raw))
    if suf == ".json":
        return _pages_from_dict(json.loads(raw))
    # markdown：按 `## ` 或 `---` 切页；无结构则整篇为一页
    if suf in (".md", ".markdown"):
        blocks = re.split(r"\n(?=#{1,3}\s)", raw)
        pages = []
        for b in blocks:
            b = b.strip()
            if not b:
                continue
            title = b.splitlines()[0].lstrip("# ").strip()
            pages.append({"page": len(pages) + 1, "section": title, "text": b})
        if len(pages) <= 1:
            pages = [{"page": 1, "section": "全文", "text": raw}]
        return pages
    raise RuntimeError(f"不支持的 BP 格式：{suf}")


def bp_to_text(pages):
    return "\n\n".join(f"【第{p['page']}页 · {p['section']}】\n{p['text']}" for p in pages)


# ---------------------------------------------------------------------------
# 3. Prompt 构造（角色严格隔离）
# ---------------------------------------------------------------------------
SYSTEM_TMPL = """你是{name}，代表一家{firm_type}（{tier}）。
你的公开风格对标 {benchmark}。**注意：你的内部规则（投委会人数、投票权、过会轮次）不对外披露，
你只按公开的投资方向、阶段、票额和评审偏好来审这份 BP，不要编造机构的内部制度。**

【你的投资边界】
- 投资阶段：{stage}
- 单笔规模：{ticket}
- 决策流程（公开通行流程）：{decision_process}

【你的投资哲学（一句话）】
「{philosophy}」

你现在在做一件很具体的事：**审阅一份商业计划书（BP）的初稿，逐页挑刺。**
你不是来鼓励创业者的，你是来替他找死的——找出会让这笔投资亏钱的那些问题。

【你的六个核心维度权重】（百分制，合计 100）
{weights_block}

【你的闸门维度：{gate}】
不参与加权平均，但低于你的阈值即一票否决——这一项你要单独打分并在提问里体现。

【你的典型质疑句式】（至少用其中 1-2 句的口吻来提问，要像真人说话）
{cross_exam_block}

【你的否决阈值】（触发了就必须 go_no_go = "No-Go"）
{veto}

【对 BP 材料的额外要求】（BP 里缺这些材料本身就是扣分项，要在提问里点出来）
{extra_block}

【你额外要看的清单】
{lens_block}
{gov_block}
【铁律】
1. quote 字段必须**逐字摘抄 BP 原文**，一个标点都不要改。摘不到原文就不要提这条问题——宁缺毋滥。
   （反例：BP 写"客户数 42 家"，你不能写成"约42家客户"或"42 家企业客户"，必须是原样。）
2. page 必须是你摘录内容所在的页码（BP 每段前标了【第N页】）。
3. 只输出 JSON，不要任何解释性文字。
4. total_score 必须与 dimension_scores 一致（自己按权重算一遍，别拍脑袋）。
"""

USER_TMPL = """以下是待评审的 BP 全文（共 {n} 页）：

{bp_text}

---

请严格按下面的 JSON 结构输出你的评审结论（所有字段必填）：

{{
  "role": "{name}",
  "total_score": 0-100 的整数,
  "dimension_scores": {{
    "市场": 0-100, "团队": 0-100, "产品壁垒": 0-100,
    "商业模式": 0-100, "财务预测": 0-100, "融资方案": 0-100,
    "风险合规": 0-100
  }},
  "money_nature_check": {{
    "matched": true 或 false,
    "verdict": "一句话判断：这笔钱的性质与该项目阶段是否匹配",
    "reason": "依据 BP 里的哪些原文（可引用）得出这个判断；BP 没写明资金性质就判不匹配"
  }},
  "page_level_questions": [
    {{
      "page": 页码整数,
      "quote": "从该页逐字摘抄的原文（10-60字）",
      "question": "你的质疑（具体、可被回答，不要空泛）",
      "severity": "P0 或 P1 或 P2"
    }}
  ],{gov_schema}
  "fatal_flaws": ["如果存在：一句话能证伪整个模式的问题；没有就给空数组"],
  "go_no_go": "Go 或 Conditional-Go 或 No-Go",
  "top3": ["最优先要改的 3 件事，按优先级排序，每条一句话，必须是动作（把X改成Y）"]
}}

要求：
- page_level_questions 至少 6 条，覆盖你权重最高的 3 个维度，其中至少 1 条打到第 1 页（定位页）或团队页。
- **必须有一条问题专门问"钱的性质"**（你要的是谁的钱、这笔钱的性质和阶段匹配吗），
  与 money_nature_check 字段呼应，并在 quote 里摘 BP 中关于融资/资金的原文。
- severity 判定标准：P0=不修则不可能过会（数据造假/勾稽冲突/收入无出处/无返投安排/合规硬伤/无退出路径）；
  P1=会显著降低估值或拖长决策周期；P2=影响专业观感。
- top3 必须是**动作**（"把 X 改成 Y"），不是评价（"X 不够好"）。
"""

GOV_SCHEMA_BLOCK = """
  "gov_special_scores": {{
    {gov_dims}
  }},
  "gov_special_findings": [
    {{"dimension": "专项维度名", "finding": "你的判断", "severity": "P0 或 P1 或 P2"}}
  ],"""

MONEY_RULE = ("**每个角色都必须就'钱的性质'给出一次明确判断**：BP 里写没写、"
              "钱的性质（美元/人民币市场化/国资引导基金）与所处阶段是否匹配；"
              "BP 未写明资金性质即判 matched=false。")


def build_prompt(role, pages):
    w = role["weights"]
    weights_block = "\n".join(
        f"- {k}：{v}%" for k, v in sorted(w.items(), key=lambda x: -x[1])
    )
    gate = role.get("gate_dimension") or GATE_DIMENSION
    gov = role.get("gov_special")
    if gov:
        gov_block = ("\n【政府基金专项评审维度（必须逐个打分并给出发现）】\n"
                     + "\n".join(f"- {g}" for g in gov) + "\n")
        gov_dims = ",\n    ".join(f'"{g}": 0-100' for g in gov)
        gov_schema = GOV_SCHEMA_BLOCK.replace("{gov_dims}", gov_dims)
    else:
        gov_block = ""
        gov_schema = ""
    system = SYSTEM_TMPL.format(
        name=role["name"], firm_type=role["firm_type"], tier=role.get("tier", ""),
        benchmark=role["benchmark"], stage=role.get("stage", "—"),
        ticket=role.get("ticket", "—"),
        decision_process=role.get("decision_process", "—"),
        philosophy=role["philosophy"], weights_block=weights_block, gate=gate,
        cross_exam_block="\n".join(f"- {q}" for q in role["cross_exam"]),
        veto=role["veto"],
        extra_block="\n".join(f"- {x}" for x in role.get("extra_requirements", [])) or "- 无特殊要求",
        lens_block="\n".join(f"- {x}" for x in role["lens"]),
        gov_block=gov_block,
    )
    user = USER_TMPL.format(n=len(pages), bp_text=bp_to_text(pages), name=role["name"],
                            gov_schema=gov_schema)
    return [{"role": "system", "content": system},
            {"role": "user", "content": user + "\n\n" + MONEY_RULE}]


# ---------------------------------------------------------------------------
# 4. 响应解析 + 引用校验
# ---------------------------------------------------------------------------
def extract_json(text):
    if not text:
        return None, "空响应"
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t), None
    except Exception:
        pass
    i, j = t.find("{"), t.rfind("}")
    if i >= 0 and j > i:
        frag = t[i:j + 1]
        try:
            return json.loads(frag), None
        except Exception:
            try:
                return json.loads(re.sub(r",\s*([}\]])", r"\1", frag)), None
            except Exception as e:
                return None, f"JSON 解析失败: {e}"
    return None, "响应中找不到 JSON"


def norm(s):
    """归一化用于"逐字引用"比对：去掉空白、标点，以及 markdown 装饰符。

    为什么必须去掉 markdown 装饰符（* _ ` # > |）：BP 以 md 传入时表格单元格写作
    `| **订阅收入（万元）** | **176** |`，模型摘录成"订阅收入（万元）176"是**忠实摘抄**，
    但字面上的 ** 会让子串匹配失败，造成"假报编造"。校验的目的是抓"编原文"，
    不是抓"排版差异"，所以这里对装饰符宽容、对文字内容严格。
    """
    return re.sub(r"[\s，。；：、,.;:!?！？\"'“”‘’（）()【】\[\]—\-·|*_`#>~＝=+]+",
                  "", str(s or ""))


def verify_quote(quote, pages):
    """判定 quote 相对 BP 原文的命中级别 → (level, page)。

    三档而非两档，因为"模型编造原文"与"模型轻微改写了原文"性质完全不同：
      exact   逐字命中（归一化后为子串）→ 可直接作对客材料依据
      near    近似命中（字符 bigram 覆盖率 ≥0.9，改写幅度 ≤10%）→ 可用，但引用前须回原文核对
      missing 未命中 → 高度疑似编造原文，不得采信
    """
    nq = norm(quote)
    if len(nq) < 6:
        return "missing", None
    for p in pages:
        if nq in norm(p["text"]):
            return "exact", p["page"]
    bg = _bigrams(quote)
    if not bg:
        return "missing", None
    best, best_cov = None, 0.0
    for p in pages:
        cov = len(bg & _bigrams(p["text"])) / len(bg)
        if cov > best_cov:
            best, best_cov = p["page"], cov
    return ("near", best) if best_cov >= 0.90 else ("missing", best)


def _bigrams(s):
    s = norm(s)
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) >= 2 else set()


def recompute_weighted(role, dim_scores):
    w = role["weights"]
    tot, wsum = 0.0, 0
    for k, wt in w.items():
        v = dim_scores.get(k)
        if isinstance(v, (int, float)):
            tot += v * wt
            wsum += wt
    return round(tot / wsum, 1) if wsum else None


def review_one(role, pages, assign, bp_path, round_no):
    provider, model = assign["provider"], assign["model"]
    mt = PROVIDERS[provider]["models"].get(model, {}).get("max_tokens", 4096)
    rec = {
        "role_id": role["id"], "role": role["name"], "firm_type": role["firm_type"],
        "tier": role.get("tier"), "benchmark": role.get("benchmark"),
        "stage": role.get("stage"), "ticket": role.get("ticket"),
        "decision_process": role.get("decision_process"),
        "philosophy": role["philosophy"], "weights": role["weights"],
        "gate_dimension": role.get("gate_dimension", GATE_DIMENSION),
        "veto_rule": role["veto"],
        "extra_requirements": role.get("extra_requirements", []),
        "gov_special": role.get("gov_special"),
        "provider": provider, "provider_label": PROVIDERS[provider]["label"],
        "model": model, "round": round_no, "bp": str(bp_path),
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    log(f"CALL 第{round_no}轮 {role['name']} ← {PROVIDERS[provider]['label']}/{model}")
    try:
        content, meta = call_model(provider, model, build_prompt(role, pages), max_tokens=mt)
        data, err = extract_json(content)
        # 截断自愈：推理型模型可能把预算烧在 reasoning 上，JSON 被截断 → 翻倍预算重试一次
        if data is None and meta.get("finish_reason") == "length" and mt < 65536:
            mt2 = min(mt * 2, 65536)
            log(f"RETRY {role['name']}：输出被截断（max_tokens={mt}）→ 用 {mt2} 重试")
            content, meta = call_model(provider, model, build_prompt(role, pages), max_tokens=mt2)
            meta["retried_with_max_tokens"] = mt2
            data, err = extract_json(content)
        rec.update(meta)
        rec["raw_response"] = content
        if data is None:
            rec["error"] = err
            log(f"FAIL {role['name']}: {err}（finish={meta.get('finish_reason')}）")
            return rec
        # —— 归一化与校验 ——
        dims = data.get("dimension_scores", {}) or {}
        dims = {k: dims.get(k) for k in ALL_DIMS if dims.get(k) is not None}
        data["dimension_scores"] = dims
        # 钱的性质审查（全团强制项）
        mnc = data.get("money_nature_check") or {}
        rec["money_nature_check"] = {
            "matched": bool(mnc.get("matched")) if mnc else None,
            "verdict": mnc.get("verdict", ""),
            "reason": mnc.get("reason", ""),
        }
        # 政府基金专项维度
        if role.get("gov_special"):
            gss = data.get("gov_special_scores") or {}
            rec["gov_special_scores"] = {g: gss.get(g) for g in role["gov_special"]}
            rec["gov_special_findings"] = data.get("gov_special_findings") or []
        rec["parsed"] = data
        rec["weighted_recomputed"] = recompute_weighted(role, dims)
        try:
            rec["score_gap"] = round(abs(float(data.get("total_score", 0)) - rec["weighted_recomputed"]), 1)
        except Exception:
            rec["score_gap"] = None

        qs = []
        stats = {"total": 0, "exact": 0, "near": 0, "missing": 0}
        for q in data.get("page_level_questions", []) or []:
            level, real_page = verify_quote(q.get("quote", ""), pages)
            stats["total"] += 1
            stats[level] += 1
            qq = dict(q)
            qq["quote_match"] = level                                # exact / near / missing
            qq["quote_verified"] = level in ("exact", "near")         # 兼容字段：是否可用
            qq["quote_verbatim"] = (level == "exact")
            qq["quote_real_page"] = real_page
            if level != "missing" and real_page and real_page != q.get("page"):
                qq["page_mismatch"] = True
            qs.append(qq)
        data["page_level_questions"] = qs
        stats["usable"] = stats["exact"] + stats["near"]
        rec["quote_stats"] = stats
        rec["quote_fabricated"] = stats["missing"]
        bad = stats["missing"]
        # 否决阈值是否触发
        rec["veto_triggered"] = _veto_check(role, data, rec)
        log(f"DONE {role['name']}: total={data.get('total_score')} "
            f"复算={rec['weighted_recomputed']} 提问={len(qs)} "
            f"引用[逐字{stats['exact']}/近似{stats['near']}/疑似编造{stats['missing']}] "
            f"go={data.get('go_no_go')} veto={rec['veto_triggered']}")
    except Exception as e:
        rec["error"] = str(e)[:300]
        log(f"FAIL {role['name']}: {rec['error']}")
    return rec


def _veto_check(role, data, rec):
    """把角色的否决阈值落成可判定的规则（数值型部分）。定性阈值由角色自判 go_no_go。"""
    dims = data.get("dimension_scores", {}) or {}
    try:
        total = float(data.get("total_score", 100))
    except Exception:
        total = 100.0
    v = role["veto"]
    thr_total = re.search(r"总分<(\d+)", v)
    if thr_total and total < float(thr_total.group(1)):
        return True
    for m in re.finditer(r"(市场|团队|产品壁垒|商业模式|财务预测|融资方案|风险合规)\s*维度?<(\d+)", v):
        d, t = m.group(1), float(m.group(2))
        if isinstance(dims.get(d), (int, float)) and dims[d] < t:
            return True
    if data.get("go_no_go") == "No-Go":
        return True
    # P0 存在且角色阈值里写了"任一 P0"
    if "P0" in v and any(str(q.get("severity", "")).upper() == "P0"
                         for q in data.get("page_level_questions", []) or []):
        return True
    return False


# ---------------------------------------------------------------------------
# 5. 角色 ↔ 模型派单：跨 provider 轮转，保证"多模型"
# ---------------------------------------------------------------------------
def assign_models(roles, available, degrade=False):
    if degrade:
        # 降级模式：所有角色用同一个模型，靠 prompt 严格隔离 + 分轮独立调用
        a = available[0]
        return [{**r, "_assign": {"provider": a["provider"], "model": a["model"]}} for r in roles]
    # 优先跨 provider 轮转（不同角色用不同 provider 的模型），provider 用尽再轮模型
    by_prov = {}
    for a in available:
        by_prov.setdefault(a["provider"], []).append(a["model"])
    prots = list(by_prov)
    seq = []
    round_i = 0
    while len(seq) < len(roles) + 4:
        for p in prots:
            ms = by_prov[p]
            seq.append({"provider": p, "model": ms[round_i % len(ms)]})
        round_i += 1
    out = []
    for i, r in enumerate(roles):
        out.append({**r, "_assign": seq[i]})
    return out


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="投资人评审团 · 多模型交叉评审")
    ap.add_argument("--bp", required=False, help="BP 文件（yaml/json/md）")
    ap.add_argument("--roles", help="只跑指定角色 id，逗号分隔")
    ap.add_argument("--roles-file", default=None, help="角色库 yaml 路径（默认自动定位 roles.yaml）")
    ap.add_argument("--out", default=".", help="输出目录（默认脚本所在目录）")
    ap.add_argument("--out-raw", default="review-raw.json",
                    help="原始响应文件名（多轮时用 review-raw-v2.json 等，避免覆盖）")
    ap.add_argument("--round", type=int, default=1, help="轮次号（用于评分轨迹）")
    ap.add_argument("--tag", default="", help="本轮标签，如 v1/v2")
    ap.add_argument("--degrade", action="store_true", help="单模型降级模式（角色隔离+分轮独立）")
    ap.add_argument("--dry-run", action="store_true", help="只探测模型可用性")
    ap.add_argument("--list-models", action="store_true", help="列出注册表内所有模型")
    ap.add_argument("--reverify", metavar="RAW.json",
                    help="只重算已有 raw.json 的引用校验（修正 norm 规则后无需重跑模型，省 token）")
    ap.add_argument("--max-workers", type=int, default=8)
    args = ap.parse_args()

    load_env()

    if args.list_models:
        for p, cfg in PROVIDERS.items():
            key, kn = resolve_key(p)
            print(f"{cfg['label']:<20} key={'✅ ' + kn if key else '❌ 缺失'}  "
                  f"models={', '.join(cfg['models'])}")
        return

    if args.reverify:
        rp = Path(args.reverify)
        raw = json.loads(rp.read_text(encoding="utf-8"))
        if "error" in raw:
            print(f"该文件无有效评审：{raw['error']}")
            return
        pages = load_bp(raw["meta"]["bp_file"])
        tot = bad = 0
        for rec in raw["reviews"]:
            qs = (rec.get("parsed") or {}).get("page_level_questions", []) or []
            nbad = 0
            for q in qs:
                ok, real = verify_quote(q.get("quote", ""), pages)
                q["quote_verified"] = ok
                q["quote_real_page"] = real
                if not ok:
                    nbad += 1
            if qs:
                rec["quote_stats"] = {"total": len(qs), "verified": len(qs) - nbad,
                                      "fabricated": nbad}
                tot += len(qs)
                bad += nbad
        rp.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ 已重算 {rp.name}：{tot} 条引用，{tot - bad} 条通过逐字校验，{bad} 条未通过"
              f"（通过率 {(tot - bad) / tot * 100:.1f}%）" if tot else "无引用可校验")
        return

    if not args.bp and not args.dry_run:
        ap.error("--bp 必填（除非 --dry-run / --list-models / --reverify）")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    roles_file = find_roles_file(args.roles_file)
    log(f"角色库：{roles_file}")
    roles_cfg = yaml.safe_load(roles_file.read_text(encoding="utf-8"))
    roles = roles_cfg["roles"]
    if args.roles:
        keep = {x.strip() for x in args.roles.split(",")}
        roles = [r for r in roles if r["id"] in keep]
    # 权重自检
    for r in roles:
        s = sum(r["weights"].values())
        if s != 100:
            log(f"WARN 角色 {r['id']} 权重合计 {s} ≠ 100，请修 roles.yaml")

    log(f"=== 评审团启动：{len(roles)} 个角色 · 第 {args.round} 轮 · BP={args.bp} ===")
    avail, skipped = probe_models()
    if not avail:
        log("FATAL 没有任何可用外部模型。请配置 key 后再跑（见 README）。")
        (out_dir / "review-raw.json").write_text(json.dumps(
            {"error": "无可用模型", "skipped": skipped, "ts": datetime.now().isoformat()},
            ensure_ascii=False, indent=2), encoding="utf-8")
        sys.exit(2)
    log(f"可用模型 {len(avail)} 个：{[a['provider'] + '/' + a['model'] for a in avail]}")
    log(f"跳过模型 {len(skipped)} 个：{skipped}")
    if args.dry_run:
        print(json.dumps({"available": avail, "skipped": skipped}, ensure_ascii=False, indent=2))
        return

    pages = load_bp(args.bp)
    log(f"BP 载入：{len(pages)} 页，{sum(len(p['text']) for p in pages)} 字")
    # 把"模型实际看到的 BP 文本"落盘：引用校验与事后审计都以它为准（而不是以原始 BP 文件为准，
    # 因为 yaml/json 会被拍平成带字段路径的形式，模型摘的是拍平后的原文）。
    bp_text_dump = out_dir / f"bp-text-{(args.tag or ('r' + str(args.round)))}.txt"
    bp_text_dump.write_text(bp_to_text(pages), encoding="utf-8")
    log(f"已落盘模型输入原文 {bp_text_dump}（{bp_text_dump.stat().st_size} 字节，用于引用校验）")
    degrade = args.degrade or len(avail) == 1
    if degrade:
        log(f"[降级模式] 仅 {len(avail)} 个可用模型 → 同模型多角色隔离评审，报告将声明该局限")

    tasked = assign_models(roles, avail, degrade=degrade)
    t0 = time.time()
    results = []
    with cf.ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        futs = {ex.submit(review_one, r, pages, r["_assign"], args.bp, args.round): r for r in tasked}
        for f in cf.as_completed(futs):
            results.append(f.result())
    order = {r["id"]: i for i, r in enumerate(roles)}
    results.sort(key=lambda x: order.get(x["role_id"], 99))

    ok = [r for r in results if "parsed" in r]
    raw = {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "bp_file": str(Path(args.bp).resolve()), "bp_pages": len(pages),
            "bp_chars": sum(len(p["text"]) for p in pages),
            "bp_sha1": __import__("hashlib").sha1(
                Path(args.bp).read_bytes()).hexdigest()[:12],
            "round": args.round, "tag": args.tag,
            "mode": "degrade-single-model" if degrade else "multi-model",
            "roles_total": len(roles), "roles_succeeded": len(ok),
            "models_available": [f"{a['provider']}/{a['model']}" for a in avail],
            "models_providers": sorted({a["provider"] for a in avail}),
            "models_skipped": skipped,
            "elapsed_s": round(time.time() - t0, 1),
            "dimensions": DIMENSIONS,
        },
        "reviews": results,
    }
    (out_dir / args.out_raw).write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"已写 {out_dir / args.out_raw}（成功 {len(ok)}/{len(roles)}，耗时 {raw['meta']['elapsed_s']}s）")

    # 评分轨迹
    hist_p = out_dir / "score-history.json"
    hist = json.loads(hist_p.read_text(encoding="utf-8")) if hist_p.exists() else []
    entry = {
        "round": args.round, "tag": args.tag, "ts": raw["meta"]["generated_at"],
        "bp_file": raw["meta"]["bp_file"], "mode": raw["meta"]["mode"],
        "scores": {r["role_id"]: {
            "role": r["role"], "model": r["model"],
            "total": (r.get("parsed") or {}).get("total_score"),
            "weighted": r.get("weighted_recomputed"),
            "go_no_go": (r.get("parsed") or {}).get("go_no_go"),
            "P0": sum(1 for q in (r.get("parsed") or {}).get("page_level_questions", [])
                      if str(q.get("severity", "")).upper() == "P0"),
            "veto": r.get("veto_triggered"),
        } for r in ok},
    }
    hist = [h for h in hist if not (h.get("round") == args.round and h.get("tag") == args.tag)]
    hist.append(entry)
    hist.sort(key=lambda h: (h.get("tag", ""), h.get("round", 0)))
    hist_p.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"已更新评分轨迹 {hist_p}（累计 {len(hist)} 轮）")
    print(f"\n✅ 完成：{len(ok)}/{len(roles)} 角色出结果，原始响应见 {out_dir / 'review-raw.json'}")


if __name__ == "__main__":
    main()
