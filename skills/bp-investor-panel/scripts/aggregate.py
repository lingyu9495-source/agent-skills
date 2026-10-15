#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aggregate.py — 投资人评审团聚合器

读取 review-raw.json（+ score-history.json），产出 review-report.md：
  ① 多角色评分矩阵（表）
  ② 分歧矩阵（议题 × 角色命中矩阵）
  ③ 钱的性质审查（全团强制项 · 结构性闸门）
  ④ 政府基金专项评审维度（第二层角色专属）
  ⑤ 共识问题 vs 分歧问题（分开列）
  ⑥ P0 致命伤汇总
  ⑦ 加权总分与 Go/No-Go（附判定规则回溯）
  ⑧ 修改优先级清单
  ⑨ 复审建议 + 评分轨迹

用法：
    python3 aggregate.py --raw review-raw.json --out review-report.md
    python3 aggregate.py --raw review-raw.json --verdict-only   # 只打印结论
"""
import argparse
import json
import re
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

HERE = Path(__file__).resolve().parent
# 六个核心加权维度 + 一个闸门维度（不参与加权，但低于阈值即一票否决）
DIMENSIONS = ["市场", "团队", "产品壁垒", "商业模式", "财务预测", "融资方案"]
GATE_DIMENSION = "风险合规"
ALL_DIMS = DIMENSIONS + [GATE_DIMENSION]

# —— 议题分类词典：把自由文本的问题归到可比对的议题簇（用于共识/分歧判定）——
TOPIC_RULES = [
    ("财务勾稽与口径", r"勾稽|口径|对不上|不一致|打架|矛盾|重算|复算|乘不|两个数|数字冲突|量级|差 ?10 ?倍"),
    ("收入确认与真实性", r"收入确认|确认政策|履约进度|完工法|审计|台账|发票|银行流水|回款|第三方验证|无出处"),
    ("返投与落地安排", r"返投|落地|注册地|迁|纳税|税收|就业|岗位|招商|达产|厂房|用地|产线"),
    ("国资审批与退出适配", r"国资|国有资产|保值增值|审批|备案|公示|追责|回购|对赌|兜底|监管"),
    ("政府基金考核与让利", r"引导基金|子基金|遴选|让利|容错|存续期|考核|返投比例|理事"),
    ("市场规模与测算", r"市场规模|TAM|SAM|SOM|天花板|自下而上|自上而下|市场空间|市占率|渗透率|份额"),
    ("单位经济", r"单位经济|ARPU|CAC|LTV|NDR|净收入留存|回收期|毛利率|付费客户|客单价"),
    ("增长质量与牵引", r"可重复|一次性|PoC|试点|订单质量|留存|增速|增长质量|pipeline|复购|续约"),
    ("护城河与壁垒", r"壁垒|护城河|moat|不可复制|资产库|替代|大厂|差异化|稀缺|复制"),
    ("退出路径与现金流", r"退出|接盘|并购退出|IPO|S ?交易|自由现金流|EBITDA|现金流|杠杆|买方"),
    ("估值与融资方案", r"估值|投前|出让|稀释|融资额|资金用途|用途|3\.5 ?亿|12\.5%|对赌|回购|币种|美元|人民币"),
    ("钱的性质与阶段匹配", r"谁的钱|钱的性质|资金性质|币种|美元基金|人民币基金|阶段匹配|钱的期限|资金属性"),
    ("团队与组织", r"团队|创始人|创始|CEO|CTO|COO|联创|履历|头衔|可替换|招聘|人才|顾问|决策史|全职|股权结构"),
    ("产品与交付", r"产品|交付|智能体|中台|场景|定制|标准化|实施|人月|产能|私有化|产能利用率"),
    ("客户结构与订单", r"客户集中|前五大|大客户|依赖|订单|在手订单|客户结构|账期|合作年限"),
    ("合规与资质", r"合规|等保|ISO|数据安全|外资准入|资质|备案|知识产权|隐私|诉讼|行政处罚|沿革"),
    ("商业模式与定价", r"商业模式|定价权|收费|订阅|分成|效果付费|收入结构|计价|抽成"),
    ("真实需求与支付能力", r"真痛点|伪需求|痛点|支付能力|决策链|访谈|第一性"),
    ("竞争格局", r"竞争|对手|玩家|2x2|象限|红海|价格战|同质化|产业链位置|议价"),
    ("财务预测假设", r"预测|假设|敏感性|驱动因素|三表|净利率|周转|校准|兑现|管理报表"),
]


def topic_of(text):
    for name, pat in TOPIC_RULES:
        if re.search(pat, text):
            return name
    return "其他"


def sev_rank(s):
    return {"P0": 0, "P1": 1, "P2": 2}.get(str(s).upper(), 3)


def sev_icon(s):
    return {"P0": "🔴 P0", "P1": "🟠 P1", "P2": "🟡 P2"}.get(str(s).upper(), "·")


def bar(v, width=10):
    if v is None:
        return "—"
    n = int(round(max(0, min(100, float(v))) / 100 * width))
    return "█" * n + "░" * (width - n)


# ---------------------------------------------------------------------------
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


def load_veto_rules():
    if yaml is None:
        return {}
    cfg = yaml.safe_load(find_roles_file().read_text(encoding="utf-8"))
    return {r["id"]: r.get("veto", "") for r in cfg["roles"]}


def build_clusters(reviews, role_order):
    """把各角色的 page_level_questions 聚类成议题簇。"""
    items = []
    for r in reviews:
        p = r.get("parsed") or {}
        for q in p.get("page_level_questions", []) or []:
            text = f"{q.get('question', '')} {q.get('quote', '')}"
            items.append({
                "role_id": r["role_id"], "role": r["role"], "model": r["model"],
                "provider_label": r["provider_label"],
                "page": q.get("page"), "quote": q.get("quote", ""),
                "question": q.get("question", ""), "severity": str(q.get("severity", "")).upper(),
                "quote_verified": q.get("quote_verified"),
                "quote_match": q.get("quote_match"), "topic": topic_of(text),
            })
        # 政府基金专项发现也计入议题簇（无页码引用，不参与引用校验统计）
        for f in r.get("gov_special_findings", []) or []:
            text = f"{f.get('finding', '')} {f.get('dimension', '')}"
            items.append({
                "role_id": r["role_id"], "role": r["role"], "model": r["model"],
                "provider_label": r["provider_label"],
                "page": None, "quote": "（政府基金专项判断，无页码引用）",
                "question": f"[专项·{f.get('dimension', '')}] {f.get('finding', '')}",
                "severity": str(f.get("severity", "")).upper(),
                "quote_verified": None, "quote_match": None, "topic": topic_of(text),
            })
    clusters = OrderedDict()
    for it in items:
        key = (it["topic"],)
        clusters.setdefault(key, []).append(it)
    out = []
    for (topic,), members in clusters.items():
        roles = sorted({m["role_id"] for m in members}, key=lambda x: role_order.get(x, 99))
        models = sorted({m["model"] for m in members})
        sevs = [m["severity"] for m in members]
        worst = min(sevs, key=sev_rank) if sevs else "P2"
        pages = Counter(m["page"] for m in members if m["page"] is not None)
        out.append({
            "topic": topic, "members": members, "roles": roles,
            "role_names": [next((x["role"] for x in members if x["role_id"] == rid), rid) for rid in roles],
            "n_roles": len(roles), "models": models, "n_models": len(models),
            "worst_severity": worst,
            "severity_spread": sorted(set(sevs), key=sev_rank),
            "pages": [p for p, _ in pages.most_common()],
            "n_questions": len(members),
            "fabricated": sum(1 for m in members if m.get("quote_match") == "missing"),
            "verbatim": sum(1 for m in members if m.get("quote_match") == "exact"),
            "near": sum(1 for m in members if m.get("quote_match") == "near"),
        })
    out.sort(key=lambda c: (sev_rank(c["worst_severity"]), -c["n_roles"], -c["n_questions"]))
    return out, items


def decide(reviews, clusters, role_order):
    """Go/No-Go 判定，返回 (verdict, 依据列表)。"""
    ok = [r for r in reviews if "parsed" in r]
    # 打分不自洽的角色（自报总分与自身维度分的加权复算结果偏差 >25）不参与基础分均分：
    # 它的维度分和提问仍然采信，但它给出的"整体分"与自己给的分项分互相矛盾，不能作为锚。
    gap_outliers = [r for r in ok if (r.get("score_gap") or 0) > 25]
    scored = [r for r in ok if r.get("weighted_recomputed") is not None and r not in gap_outliers]
    scores = [r["weighted_recomputed"] for r in scored]
    model_scores = [(r.get("parsed") or {}).get("total_score") for r in ok]
    model_scores = [s for s in model_scores if isinstance(s, (int, float))]
    base = round(sum(scores) / len(scores), 1) if scores else None
    veto_roles = [r for r in ok if r.get("veto_triggered")]
    p0_clusters = [c for c in clusters if c["worst_severity"] == "P0"]
    p0_consensus = [c for c in p0_clusters if c["n_roles"] >= 2]
    p0_single = [c for c in p0_clusters if c["n_roles"] == 1]
    fatal = []
    for r in ok:
        for f in (r.get("parsed") or {}).get("fatal_flaws", []) or []:
            fatal.append({"role": r["role"], "role_id": r["role_id"], "model": r["model"], "flaw": f})
    nogo_votes = [r["role"] for r in ok if (r.get("parsed") or {}).get("go_no_go") == "No-Go"]
    cg_votes = [r["role"] for r in ok if (r.get("parsed") or {}).get("go_no_go") == "Conditional-Go"]
    go_votes = [r["role"] for r in ok if (r.get("parsed") or {}).get("go_no_go") == "Go"]

    reasons, penalty = [], 0.0
    n_roles = len(ok) or 1
    # 扣分公式按"比例"而非"绝对票数"，否则评审团越大扣分越狠、总分不可比。
    #   共识 P0：每个 −4 分，上限 −16
    #   否决赛席：按席位比例 ×20，上限 −10
    #   No-Go 票：按票数比例 ×12，上限 −6
    #   总扣分上限 −32（保证"最终分"仍能被解读为百分制质量分）
    c1 = min(16.0, 4.0 * len(p0_consensus))
    if c1:
        penalty += c1
        reasons.append(f"共识 P0 议题 {len(p0_consensus)} 个 × 4 分 = −{round(c1,1)}（上限 16）")
    c2 = min(10.0, 20.0 * len(veto_roles) / n_roles)
    if c2:
        penalty += c2
        reasons.append(f"触发否决阈值 {len(veto_roles)}/{n_roles} 席 = −{round(c2,1)}（20×比例，上限 10）")
    c3 = min(6.0, 12.0 * len(nogo_votes) / n_roles)
    if c3:
        penalty += c3
        reasons.append(f"角色自评 No-Go {len(nogo_votes)}/{n_roles} 票 = −{round(c3,1)}（12×比例，上限 6）")
    if gap_outliers:
        reasons.append(f"打分不自洽（自报总分与自身维度分偏差>25）{len(gap_outliers)} 席已从基础分剔除："
                       f"{'、'.join(r['role'] for r in gap_outliers)}——其维度分与提问仍采信")
    penalty = round(penalty, 1)
    final = round(max(0.0, (base or 0) - penalty), 1) if base is not None else None

    rules_hit = []
    if len(p0_consensus) >= 2 or (veto_roles and len(p0_clusters) >= 2) or len(nogo_votes) >= 3:
        verdict = "No-Go"
        rules_hit.append("规则 NOGO-1：≥2 个共识 P0 议题，或（有角色否决 且 ≥2 个 P0 议题），或 ≥3 票角色 No-Go")
    elif p0_clusters or veto_roles:
        verdict = "Conditional-Go"
        rules_hit.append("规则 COND-1：存在 P0 议题或角色否决，但未达 No-Go 门槛 → 修订后复审")
    else:
        verdict = "Go"
        rules_hit.append("规则 GO-1：无 P0 议题、无角色否决、无 No-Go 票")

    return {
        "verdict": verdict, "reasons": reasons, "rules_hit": rules_hit,
        "base_score": base, "penalty": round(penalty, 1), "final_score": final,
        "p0_clusters": p0_clusters, "p0_consensus": p0_consensus, "p0_single": p0_single,
        "veto_roles": veto_roles, "fatal_flaws": fatal,
        "votes": {"No-Go": nogo_votes, "Conditional-Go": cg_votes, "Go": go_votes},
        "model_scores": model_scores,
        "gap_outliers": gap_outliers,
        "n_scored": len(scored),
    }


def prio_list(clusters, reviews_by_id=None):
    """优先级清单：严重度优先、共识度次之。

    修改动作优先取该议题簇成员角色 top3 里与之同主题的**动作原话**
    （角色被要求把 top3 写成"把 X 改成 Y"的动作），取不到就回落到质疑栏，
    并明确标注"（未给出动作，按质疑栏回应）"——不假装模型给了动作。
    """
    reviews_by_id = reviews_by_id or {}
    pats = dict(TOPIC_RULES)
    prio, n = [], 0
    for c in clusters:
        if c["worst_severity"] not in ("P0", "P1"):
            continue
        n += 1
        who = "、".join(c["role_names"][:3]) + ("等" if len(c["role_names"]) > 3 else "")
        rep = sorted(c["members"], key=lambda m: sev_rank(m["severity"]))[0]
        pat = pats.get(c["topic"])
        action, from_role = "", None
        for rid in c["roles"]:
            for a in ((reviews_by_id.get(rid) or {}).get("parsed") or {}).get("top3", []) or []:
                if pat and re.search(pat, a):
                    action, from_role = a, rid
                    break
            if action:
                break
        prio.append({
            "rank": n, "topic": c["topic"], "severity": c["worst_severity"],
            "n_roles": c["n_roles"], "who": who, "pages": c["pages"][:4],
            "quote": rep["quote"], "question": rep["question"],
            "action": action or "—（该议题无角色给出动作，按质疑栏逐条回应）",
            "action_from": from_role,
            "consensus": c["n_roles"] >= 2,
        })
    return prio


# ---------------------------------------------------------------------------
def render(raw, clusters, items, dec, prio, history, veto_rules):
    m = raw["meta"]
    ok = [r for r in raw["reviews"] if "parsed" in r]
    failed = [r for r in raw["reviews"] if "parsed" not in r]
    role_order = {r["role_id"]: i for i, r in enumerate(raw["reviews"])}
    V = dec["verdict"]
    badge = {"Go": "🟢 GO", "Conditional-Go": "🟡 CONDITIONAL-GO（修订后复审）",
             "No-Go": "🔴 NO-GO（当前形态不可投）"}[V]
    q_total = sum(c["n_questions"] for c in clusters)
    q_fab = sum(c["fabricated"] for c in clusters)
    p0_total = sum(1 for i in items if i["severity"] == "P0")
    p1_total = sum(1 for i in items if i["severity"] == "P1")
    p2_total = sum(1 for i in items if i["severity"] == "P2")

    L = []
    A = L.append
    A(f"# 投资人评审团报告 · {Path(m['bp_file']).name}")
    A("")
    A(f"> **评审结论：{badge}**　|　评审团加权总分 **{dec['final_score']}/100**"
      f"（基础分 {dec['base_score']} − 红线扣分 {dec['penalty']}）")
    used_models = sorted({r["model"] for r in ok})
    used_provs = sorted({r["provider_label"] for r in ok})
    A(f"> 评审团 {m['roles_total']} 席（成功 {m['roles_succeeded']} 席）·"
      f" **本轮实际调用模型 {len(used_models)} 个 / 可用 {len(m['models_available'])} 个**"
      f"（跨 {len(used_provs)} 个 provider）·"
      f" 议题 {len(clusters)} 簇 / 提问 {q_total} 条（P0 {p0_total} · P1 {p1_total} · P2 {p2_total}）")
    A(f"> 生成时间：{m['generated_at']}　|　评审轮次：第 {m.get('round', 1)} 轮"
      + (f"（{m['tag']}）" if m.get("tag") else "")
      + f"　|　模式：{'单模型降级' if m['mode'].startswith('degrade') else '多模型交叉'}")
    A("")

    # —— 0. 执行摘要 ——
    A("## 0. 执行摘要（先看这 6 行）")
    A("")
    A("| 项目 | 结论 |")
    A("|---|---|")
    A(f"| 最终裁定 | **{badge}** |")
    A(f"| 加权总分 | **{dec['final_score']}/100**（模型自报均分 "
      f"{round(sum(dec['model_scores'])/len(dec['model_scores']),1) if dec['model_scores'] else '—'}）|")
    A(f"| 共识 P0 致命伤 | **{len(dec['p0_consensus'])} 个**"
      + (f"：{'、'.join(c['topic'] for c in dec['p0_consensus'])}" if dec["p0_consensus"] else "") + " |")
    A(f"| 单角色 P0（潜在分歧点） | {len(dec['p0_single'])} 个"
      + (f"：{'、'.join(c['topic'] for c in dec['p0_single'])}" if dec["p0_single"] else "") + " |")
    A(f"| 触发否决的角色 | {len(dec['veto_roles'])} 席"
      + (f"：{'、'.join(r['role'] for r in dec['veto_roles'])}" if dec["veto_roles"] else "") + " |")
    A(f"| 角色投票 | No-Go {len(dec['votes']['No-Go'])} · Conditional-Go {len(dec['votes']['Conditional-Go'])}"
      f" · Go {len(dec['votes']['Go'])} |")
    A("")
    A("**一句话结论**：" + _one_liner(dec, clusters, m))
    A("")

    # —— ① 评分矩阵 ——
    A("## ① 多角色评分矩阵")
    A("")
    A("维度分 = 角色对该维度的打分；`复算` = 我方用角色权重对该角色维度分重算的加权分；"
      "`偏差` = |自报总分 − 复算|，>10 说明该角色打分与自身维度分不自洽，应降权看待。")
    A("")
    A("| 角色 | 模型 | " + " | ".join(ALL_DIMS) + " | 自报总分 | 复算 | 偏差 | Go/No-Go | P0 | 否决 |")
    A("|---" * (5 + len(ALL_DIMS)) + "|")
    for r in raw["reviews"]:
        p = r.get("parsed")
        if not p:
            A(f"| {r['role']} | {r.get('model','—')} | " + " | ".join(["—"] * len(ALL_DIMS))
              + f" | ⚠️ 调用失败 | — | — | — | — | — |")
            continue
        d = p.get("dimension_scores", {}) or {}
        cells = []
        for dim in ALL_DIMS:
            v = d.get(dim)
            cells.append(f"{v}" if v is not None else "—")
        n_p0 = sum(1 for q in p.get("page_level_questions", []) or []
                   if str(q.get("severity", "")).upper() == "P0")
        A(f"| {r['role']} | `{r['model']}` | " + " | ".join(cells)
          + f" | {p.get('total_score')} | {r.get('weighted_recomputed')} "
          + f"| {r.get('score_gap') if r.get('score_gap') is not None else '—'} "
          + f"| {p.get('go_no_go')} | {n_p0} | {'✅ 触发' if r.get('veto_triggered') else '—'} |")
    A("")
    # 维度均分
    A("**维度均分（评审团视角的集体短板）**")
    A("")
    A("| 维度 | 均分 | 分布 | 最严角色 | 最宽角色 |")
    A("|---|---|---|---|---|")
    dim_vals = defaultdict(list)
    for r in ok:
        d = (r.get("parsed") or {}).get("dimension_scores", {}) or {}
        for dim in ALL_DIMS:
            if isinstance(d.get(dim), (int, float)):
                dim_vals[dim].append((d[dim], r["role"]))
    rows = []
    for dim in ALL_DIMS:
        vs = dim_vals.get(dim, [])
        if not vs:
            continue
        avg = round(sum(v for v, _ in vs) / len(vs), 1)
        rows.append((avg, dim, min(vs)[1], max(vs)[1]))
    for avg, dim, strict, loose in sorted(rows):
        A(f"| {dim} | **{avg}** | {bar(avg)} | {strict} | {loose} |")
    A("")

    # —— ② 分歧矩阵 ——
    A("## ② 分歧矩阵（议题 × 角色命中图）")
    A("")
    A("读法：每行是一个议题簇，`🔴/🟠/🟡` 表示该角色就此议题给出的最高严重度，`·` 表示未提。"
      "**同一行被多个角色独立命中 = 共识；只有 1 个角色命中 = 分歧/单点视角（需人工判断是否采纳）。**")
    A("")
    hdr_roles = [r["role"] for r in raw["reviews"] if "parsed" in r]
    A("| 议题 | " + " | ".join(_short(h) for h in hdr_roles) + " | 共识度 | 涉页 |")
    A("|---" * (len(hdr_roles) + 3) + "|")
    for c in clusters:
        cells = []
        for rid_role in hdr_roles:
            ms = [x for x in c["members"] if x["role"] == rid_role]
            cells.append(sev_icon(min((x["severity"] for x in ms), key=sev_rank)) if ms else "·")
        cons = (f"**共识 {c['n_roles']}/{len(hdr_roles)}**" if c["n_roles"] >= 2
                else "分歧 ×1")
        A(f"| {c['topic']} | " + " | ".join(cells) + f" | {cons} | {c['pages'][:4]} |")
    A("")
    A("**跨模型一致性**："
      + (f"本议题集中的议题最多横跨 **{max(c['n_models'] for c in clusters)} 个不同模型**"
         if clusters else "—")
      + f"；全团涉及模型：{'、'.join('`'+x+'`' for x in m['models_available'])}。"
      + "同一议题若被不同模型独立提出，可信度高于单一模型的观点。")
    A("")

    # —— ③ 钱的性质审查（全团强制项） ——
    A("## ③ 钱的性质审查（全团强制项 · 结构性闸门）")
    A("")
    A("> 本模块的强制提问：每一份 BP 都必须被问一次——"
      "**「你要的是谁的钱？这笔钱的性质（币种／期限／返投／对赌回购／考核方式）和你现在的阶段匹配吗？」**")
    A("")
    mnc_rows = [r for r in ok if r.get("money_nature_check")]
    mism = [r for r in mnc_rows if r["money_nature_check"].get("matched") is False]
    if not mnc_rows:
        A("_本轮无角色回答该问题（模型未按 schema 输出）→ 视为流程缺陷，必须重跑。_")
    else:
        A(f"**{len(mnc_rows)} 席回答了该问题，其中 {len(mism)} 席判定「不匹配」"
          f"（{round(len(mism) / len(mnc_rows) * 100)}%）。**")
        A("")
        A("| 角色 | 模型 | 匹配 | 判断 | 依据 |")
        A("|---|---|---|---|---|")
        for r in mnc_rows:
            mn = r["money_nature_check"]
            flag = ("✅ 匹配" if mn.get("matched") else
                    ("❌ **不匹配**" if mn.get("matched") is False else "—"))
            A(f"| {r['role']} | `{r['model']}` | {flag} | {str(mn.get('verdict',''))[:70]} "
              f"| {str(mn.get('reason',''))[:150]} |")
        A("")
        if mism:
            A("**判定「不匹配」的具体理由**")
            A("")
            for r in mism:
                A(f"- **{r['role']}**：{str(r['money_nature_check'].get('reason',''))[:220]}")
            A("")
            A("⚠️ **这是结构性发现，优先级高于绝大多数 P0**：它意味着这份 BP 要么没写清融资对象的性质，"
              "要么拿着某一阶段/某一类资金的材料去募另一类钱。**钱的性质决定条款（返投／对赌／回购／期限）"
              "和整个估值故事的写法**——这一项不修，其他项改了也会在尽调阶段崩。")
        else:
            A("_全部角色判定「匹配」，说明 BP 对资金性质与阶段的交代是清楚的。_")
    A("")

    # —— ④ 政府基金专项评审维度 ——
    gov_recs = [r for r in ok if r.get("gov_special_scores")]
    if gov_recs:
        A("## ④ 政府基金专项评审维度")
        A("")
        A("由第二层（政府引导基金 / 地方产业投资平台）角色逐项打分并给出发现。"
          "这五个维度**不进入六个核心维度的加权平均**，但其中任何一项触发否决都会直接导致 No-Go。")
        A("")
        g_dims = list(gov_recs[0].get("gov_special") or [])
        A("| 专项维度 | " + " | ".join(_short(r["role"], 8) for r in gov_recs) + " | 均分 | 判定 |")
        A("|---" * (len(gov_recs) + 3) + "|")
        for g in g_dims:
            vals = [r["gov_special_scores"].get(g) for r in gov_recs]
            nums = [v for v in vals if isinstance(v, (int, float))]
            avg = round(sum(nums) / len(nums), 1) if nums else None
            vd = ("—" if avg is None else ("✅ 达标" if avg >= 70 else ("⚠️ 需补强" if avg >= 55 else "🔴 硬伤")))
            A(f"| {g} | " + " | ".join(str(v) if v is not None else "—" for v in vals)
              + f" | **{avg if avg is not None else '—'}** | {vd} |")
        A("")
        gf = []
        for r in gov_recs:
            for f in r.get("gov_special_findings", []) or []:
                gf.append({"role": r["role"], "dimension": f.get("dimension", ""),
                           "severity": str(f.get("severity", "")).upper(),
                           "finding": f.get("finding", "")})
        gf.sort(key=lambda x: sev_rank(x["severity"]))
        if gf:
            A(f"**专项发现 {len(gf)} 条（按严重度排序）**")
            A("")
            A("| 角色 | 专项维度 | 严重度 | 发现 |")
            A("|---|---|---|---|")
            for x in gf[:25]:
                A(f"| {x['role']} | {x['dimension']} | {sev_icon(x['severity'])} | {x['finding'][:160]} |")
            A("")
    else:
        A("## ④ 政府基金专项评审维度")
        A("")
        A("_本轮无政府基金角色出结果（缺 key 或调用失败），该专项维度**缺失**——"
          "若本次融资涉及国资/引导基金，必须补齐后重跑。_")
        A("")

    # —— ⑤ 共识 vs 分歧 ——
    A("## ⑤ 共识问题 vs 分歧问题")
    A("")
    A(f"### ⑤.1 共识问题（≥2 个角色独立提出 → 必须处理，共 {sum(1 for c in clusters if c['n_roles']>=2)} 个）")
    A("")
    cons = [c for c in clusters if c["n_roles"] >= 2]
    if not cons:
        A("_无（各角色视角完全分散，本身就是危险信号：说明 BP 没有明显硬伤，也没有明显亮点）_")
    for i, c in enumerate(cons, 1):
        A(f"**C{i}. [{c['topic']}]**　最高严重度 {sev_icon(c['worst_severity'])}　"
          f"命中 {c['n_roles']} 席（{'、'.join(c['role_names'])}）")
        for x in sorted(c["members"], key=lambda y: sev_rank(y["severity"]))[:3]:
            fab = (" ⚠️引用未逐字（近似改写）" if x.get("quote_match") == "near"
                   else (" 🚨引用疑似编造" if x.get("quote_match") == "missing" else ""))
            A(f"- {sev_icon(x['severity'])} **{x['role']}**（`{x['model']}`）p.{x['page']}："
              f"「{x['quote'][:60]}」→ {x['question']}{fab}")
        if len(c["members"]) > 3:
            A(f"- _…另有 {len(c['members'])-3} 条同类质疑_")
        A("")
    A(f"### ⑤.2 分歧问题（仅 1 个角色提出 → 需人工判断是否采纳，共 {sum(1 for c in clusters if c['n_roles']==1)} 个）")
    A("")
    dis = [c for c in clusters if c["n_roles"] == 1]
    if not dis:
        A("_无_")
    A("| 议题 | 提出角色 | 模型 | 严重度 | 页码 | 质疑 |")
    A("|---|---|---|---|---|---|")
    for c in dis:
        x = c["members"][0]
        A(f"| {c['topic']} | {x['role']} | `{x['model']}` | {sev_icon(x['severity'])} "
          f"| p.{x['page']} | {x['question'][:90]} |")
    A("")
    spread = [c for c in clusters if len(c["severity_spread"]) >= 2 and c["n_roles"] >= 2]
    if spread:
        A("**严重度判断分歧**（同一议题被不同角色给出不同等级——等级差 ≥1 级）：")
        A("")
        for c in spread:
            detail = "；".join(f"{x['role']}→{x['severity']}" for x in c["members"])
            A(f"- **{c['topic']}**：{detail}　→ 建议按 **{c['worst_severity']}** 从严处理")
        A("")

    # —— ④ P0 致命伤汇总 ——
    A("## ⑥ P0 致命伤汇总")
    A("")
    A(f"评审团共标出 **{p0_total} 条 P0**，归并为 **{len(dec['p0_clusters'])} 个致命议题**"
      f"（其中共识 {len(dec['p0_consensus'])} 个、单角色 {len(dec['p0_single'])} 个）。")
    A("")
    A("| # | 致命议题 | 共识 | 命中角色 | 页码 | 最狠的一句质疑 |")
    A("|---|---|---|---|---|---|")
    for i, c in enumerate(sorted(dec["p0_clusters"], key=lambda x: (-x["n_roles"], x["topic"])), 1):
        rep = sorted([x for x in c["members"] if x["severity"] == "P0"],
                     key=lambda m: role_order.get(m["role_id"], 99))[0]
        A(f"| {i} | **{c['topic']}** | {c['n_roles']} 席 | {'、'.join(c['role_names'])} "
          f"| {c['pages'][:3]} | {rep['question'][:110]} |")
    A("")
    if dec["fatal_flaws"]:
        A("### 6.1 角色原话级「致命伤」（fatal_flaws 字段）")
        A("")
        for x in dec["fatal_flaws"]:
            A(f"- **{x['role']}**（`{x['model']}`）：{x['flaw']}")
        A("")
    # 引用命中级别：逐字为默认，近似改写/疑似编造需单列（防止拿编造的原文当依据）
    _near = [x for x in items if x.get("quote_match") == "near"]
    _miss = [x for x in items if x.get("quote_match") == "missing"]
    if _near or _miss:
        A(f"### 6.2 ⚠️ 引用非逐字命中的条目（{len(_near) + len(_miss)} 条："
          f"近似改写 {len(_near)} · 疑似编造 {len(_miss)}）")
        A("")
        A("> 三档口径：**逐字命中**（可直接引用）／**近似改写**（模型合并或改写了原文，"
          "语义可信但引用前须回原文核对）／**疑似编造**（原文中找不到，**不得**采信）。"
          "引用命中的三档统计见附 ② 局限声明第 4 条。")
        A("")
        for x in _miss:
            A(f"- 🚨 **疑似编造** {x['role']}（`{x['model']}`）p.{x['page']}："
              f"「{x['quote'][:60]}」→ {x['question'][:80]}")
        for x in _near:
            A(f"- ⚠️ 近似改写 {x['role']}（`{x['model']}`）p.{x['page']}："
              f"「{x['quote'][:60]}」→ {x['question'][:80]}")
        A("")

    # —— ⑤ 加权总分与 Go/No-Go ——
    A("## ⑦ 加权总分与 Go/No-Go")
    A("")
    A(f"### 裁定：{badge}")
    A("")
    A("**判定规则回溯（可审计）**")
    A("")
    for r_ in dec["rules_hit"]:
        A(f"- 命中：{r_}")
    for r_ in dec["reasons"]:
        A(f"- {r_}")
    A(f"- 基础分 = 各角色复算加权分的算术平均 = **{dec['base_score']}**")
    if dec.get("gap_outliers"):
        A(f"- 基础分只统计 **{dec['n_scored']} 席打分自洽的角色**（等权算术平均）；"
          f"被剔除的 {len(dec['gap_outliers'])} 席因自报总分与自身维度分偏差过大："
          + "、".join(f"{r['role']}（自报 {r['parsed'].get('total_score')} vs 复算 {r['weighted_recomputed']}，"
                        f"偏差 {r['score_gap']}）" for r in dec["gap_outliers"]))
        A("  （剔除的是它们的**整体分**；其维度分、P0 提问与否决权全部照常计入）")
    A(f"- 红线扣分 = **{dec['penalty']}**")
    A(f"- **最终加权总分 = {dec['final_score']} / 100**")
    A("")
    A("| 角色 | 模型 | 自报总分 | 复算加权分 | 角色裁定 | 是否触发否决阈值 | 否决规则 |")
    A("|---|---|---|---|---|---|---|")
    for r in raw["reviews"]:
        p = r.get("parsed") or {}
        vrule = veto_rules.get(r["role_id"], "")
        A(f"| {r['role']} | `{r.get('model','—')}` | {p.get('total_score','—')} "
          f"| {r.get('weighted_recomputed','—')} | {p.get('go_no_go','—')} "
          f"| {'✅ 触发' if r.get('veto_triggered') else '—'} | {vrule[:70]} |")
    A("")
    A("**投票分布**")
    A("")
    for k, v in dec["votes"].items():
        A(f"- {k}（{len(v)} 票）：{'、'.join(v) if v else '—'}")
    A("")

    # —— ⑥ 修改优先级清单 ——
    A("## ⑧ 修改优先级清单")
    A("")
    A("排序原则：先严重度，后共识度（共识度高的先改，因为一个动作能同时安抚多个投资人）。")
    A("")
    A("| 优先级 | 议题 | 严重度 | 共识 | 谁提的 | 页码 | 原文（须逐字） | 最狠的质疑 | 修改动作（角色 top3 原话） |")
    A("|---|---|---|---|---|---|---|---|---|")
    for p in prio:
        pgs = ", ".join(f"p{x}" for x in p["pages"]) if p["pages"] else "—"
        A(f"| **{p['rank']}** | {p['topic']} | {sev_icon(p['severity'])} | "
          f"{p['n_roles']} 席{'（共识）' if p['consensus'] else '（单方）'} | {p['who']} | {pgs} "
          f"| 「{p['quote'][:50]}」 | {p['question'][:110]} | {p['action'][:130]} |")
    A("")
    A("**Top 3 立即动作（若只有一天时间）**")
    A("")
    for i, p in enumerate(prio[:3], 1):
        A(f"{i}. **{p['topic']}**（{sev_icon(p['severity'])}，{p['n_roles']} 席命中）")
        A(f"   - 动作：{p['action']}")
        A(f"   - 被卡住的原始质疑（{p['who']}）：{p['question'][:150]}")
    A("")

    # —— ⑦ 复审建议 ——
    A("## ⑨ 复审建议")
    A("")
    A(f"1. **复审触发条件**：第 ⑧ 节清单中所有 P0 与 P1 议题完成修订后，**必须整团复审**"
      f"（不是只找提出问题的那个角色复核——换模型/换角色复看，才能发现修订引入的新矛盾）。")
    A(f"2. **复审对象**：重点复看 {_top_pages(items)} 等页；财务页与融资页每次修订后都必须重跑财务尽调官。")
    A(f"3. **复审轮次**：迭代规程上限 **3 轮**，终止条件为「**无 P0**」。"
      f"当前第 {m.get('round',1)} 轮，预计还需 "
      f"{'1–2' if V != 'Go' else '0'} 轮。")
    A(f"4. **本轮特有的复审注意**："
      + (f"存在 {q_fab} 条引用非逐字命中，说明部分质疑基于模型改写过的原文——"
         f"下一轮应把 BP 原文以更小分块投喂，并在 prompt 中加重'不得改写原文'的约束。" if q_fab
         else "所有角色引用均通过原文校验，可直接进入修订。"))
    A(f"5. **分数不升反降的处理**：若复审总分低于本轮，不要怀疑模型——优先检查修订是否"
      f"引入了新的口径冲突（见 ⑤ 共识问题）。")
    gap_roles = [r for r in ok if (r.get("score_gap") or 0) > 10]
    if gap_roles:
        A(f"6. **打分口径漂移**：{len(gap_roles)} 个角色的自报总分与加权复算分偏差 >10"
          f"（{'、'.join(r['role'] for r in gap_roles)}），说明这些角色打分带主观整体印象，"
          f"复审时以**维度分**为主要比较基准，不要只看总分。")
    A("")

    # —— 附. 评分轨迹 ——
    if history:
        A("## 附 ① 评分轨迹（迭代复盘用）")
        A("")
        rounds = sorted(history, key=lambda h: (h.get("tag", ""), h.get("round", 0)))
        role_ids = [r["role_id"] for r in raw["reviews"] if "parsed" in r]
        role_names = {r["role_id"]: r["role"] for r in raw["reviews"]}
        A("| 轮次 | " + " | ".join(_short(role_names.get(rid, rid)) for rid in role_ids)
          + " | 评审团均分 | P0 合计 | 裁定 |")
        A("|---" * (len(role_ids) + 4) + "|")
        for h in rounds:
            cells, tot, p0s = [], [], 0
            for rid in role_ids:
                s = (h.get("scores") or {}).get(rid) or {}
                t = s.get("weighted") if s.get("weighted") is not None else s.get("total")
                cells.append(str(t) if t is not None else "—")
                if isinstance(t, (int, float)):
                    tot.append(t)
                p0s += s.get("P0", 0) or 0
            avg = round(sum(tot) / len(tot), 1) if tot else "—"
            tag = h.get("tag") or ""
            A(f"| {tag} 第{h.get('round')}轮 | " + " | ".join(cells) + f" | **{avg}** | {p0s} | — |")
        A("")
        if len(rounds) >= 2:
            first, last = rounds[0], rounds[-1]
            def _avg(h):
                vs = [s.get("weighted") or s.get("total")
                      for s in (h.get("scores") or {}).values()
                      if (s.get("weighted") or s.get("total")) is not None]
                return round(sum(vs) / len(vs), 1) if vs else None
            a0, a1 = _avg(first), _avg(last)
            if a0 is not None and a1 is not None:
                A(f"**轨迹变化**：{first.get('tag') or ''} 第{first['round']}轮 均分 {a0} → "
                  f"{last.get('tag') or ''} 第{last['round']}轮 均分 {a1}（{'+' if a1>=a0 else ''}{round(a1-a0,1)}）")
                A("")
                A("| 角色 | 首轮 | 末轮 | 变化 |")
                A("|---|---|---|---|")
                for rid in role_ids:
                    s0 = (first.get("scores") or {}).get(rid) or {}
                    s1 = (last.get("scores") or {}).get(rid) or {}
                    v0 = s0.get("weighted") or s0.get("total")
                    v1 = s1.get("weighted") or s1.get("total")
                    delta = (f"{'+' if (v1 or 0)-(v0 or 0)>=0 else ''}{round((v1 or 0)-(v0 or 0),1)}"
                             if (v0 is not None and v1 is not None) else "—")
                    A(f"| {role_names.get(rid, rid)} | {v0} | {v1} | {delta} |")
                A("")
    else:
        A("## 附 ① 评分轨迹")
        A("")
        A("_仅 1 轮，暂无轨迹。第 2 轮评审后自动生成对比。_")
        A("")

    # —— 附. 评审团构成与方法局限 ——
    A("## 附 ② 评审团构成与本次评审的方法局限（必须与报告一起读）")
    A("")
    A("### 评审团构成（9 席 · 三层）")
    A("")
    A("| 层次 | 角色 | 机构类型 | 对标公开风格 | 投资阶段 | 单笔规模 | 本轮模型 |")
    A("|---|---|---|---|---|---|---|")
    for r in raw["reviews"]:
        A(f"| {r.get('tier','—')} | **{r['role']}** | {r.get('firm_type','—')} "
          f"| {r.get('benchmark') or '—'} | {r.get('stage') or '—'} | {r.get('ticket') or '—'} "
          f"| `{r.get('model','—')}` |")
    A("")
    A("**各角色的六维权重 + 闸门维度 + 否决阈值**")
    A("")
    A("| 角色 | " + " | ".join(DIMENSIONS) + f" | 闸门（{GATE_DIMENSION}） | 否决阈值 |")
    A("|---" * (len(DIMENSIONS) + 3) + "|")
    for r in raw["reviews"]:
        w = r.get("weights", {}) or {}
        cells = " | ".join(f"{w.get(d, '—')}" for d in DIMENSIONS)
        A(f"| {r['role']} | {cells} | {r.get('gate_dimension', GATE_DIMENSION)} "
          f"| {str(r.get('veto_rule', ''))[:70]} |")
    A("")
    A("**各角色的决策流程（只写公开可查的通行流程，不写机构内部制度）**")
    A("")
    for r in raw["reviews"]:
        A(f"- **{r['role']}**：{r.get('decision_process') or '—'}")
    A("")
    A("**各角色对 BP 材料的额外要求（缺失即为扣分项）**")
    A("")
    for r in raw["reviews"]:
        reqs = r.get("extra_requirements") or []
        if reqs:
            A(f"- **{r['role']}**：{'；'.join(reqs[:4])}{'…' if len(reqs) > 4 else ''}")
    A("")
    A("**局限声明（不读这段会高估本报告）**")
    A("")
    A(f"1. **模型即评审员，不是真人**：本轮由 {len(used_models)} 个外部大模型"
      f"（{'、'.join('`'+x+'`' for x in used_models)}）扮演 {m['roles_succeeded']} 个角色。"
      f"同一模型扮演不同角色时，角色差异完全依赖 prompt 隔离，可能存在共同的系统性偏好。")
    mode_note = ("**本轮为单模型降级模式**：所有角色由同一个模型扮演，"
                 "「多角色」是 prompt 级隔离而非模型级隔离，分歧度会被系统性低估——"
                 "建议尽快补齐第二个 provider 的 key 后重跑。"
                 if m["mode"].startswith("degrade") else
                 f"**本轮为多模型交叉模式**：角色分布在 {len(used_provs)} 个不同 provider"
                 f"（{'、'.join(used_provs)}）上，不同角色确实由不同模型产出，"
                 f"分歧是真实的跨模型分歧。")
    A(f"2. {mode_note}")
    skip_txt = "；".join(f"{s['provider']}/{s['model']}（{s['reason'][:60]}）" for s in m.get("models_skipped", [])[:6])
    A(f"3. **未参与的模型**：{skip_txt or '无'}。这些 provider 的视角本轮缺失，"
      f"报告结论仅代表已参与模型的共识。")
    q_quoted = [x for x in items if x.get("quote_match") in ("exact", "near", "missing")]
    q_ex = sum(1 for x in q_quoted if x.get("quote_match") == "exact")
    q_near = sum(1 for x in q_quoted if x.get("quote_match") == "near")
    q_miss = sum(1 for x in q_quoted if x.get("quote_match") == "missing")
    q_n = len(q_quoted) or 1
    A(f"4. **引用校验（三档）**：本轮共提出 {q_total} 条质疑，其中 **{len(q_quoted)} 条带原文引用**"
      f"（另有 {q_total - len(q_quoted)} 条为政府基金专项判断，按设计不带原文引用、不参与本项统计）——"
      f"逐字命中 **{q_ex}** 条（{q_ex / q_n * 100:.0f}%）、近似改写 **{q_near}** 条"
      f"（{q_near / q_n * 100:.0f}%，改写幅度 ≤10%，语义可信但引用前须回原文核对）、"
      f"疑似编造 **{q_miss}** 条（{q_miss / q_n * 100:.0f}%）。"
      f"**疑似编造的引用不得作为对客材料依据**。"
      if q_total else "4. **引用校验**：本轮无提问，无法评估。")
    A(f"5. **打分与复算偏差**：{len([r for r in ok if (r.get('score_gap') or 0)>10])} 个角色的自报总分"
      f"与其维度分加权复算结果偏差 >10 分。以复算分为主锚。")
    A(f"6. **失败席位**：{len(failed)} 席未出结果"
      + (f"（{'、'.join(r['role'] for r in failed)}，原因：{failed[0].get('error','')[:80]}）" if failed else "")
      + "。缺席席位的否决权未被计入。")
    A("")
    A("---")
    A("")
    A(f"_本报告由 `review/aggregate.py` 自动生成，原始多模型响应见 `review/review-raw.json`，"
      f"评分轨迹见 `review/score-history.json`。BP 指纹 SHA1:{m['bp_sha1']}，"
      f"{m['bp_pages']} 页 / {m['bp_chars']} 字。_")
    return "\n".join(L)


def _short(name, n=6):
    name = str(name)
    return name if len(name) <= n + 2 else name[:n + 1] + "…"


def _top_pages(items, k=5):
    c = Counter(x["page"] for x in items if sev_rank(x["severity"]) <= 1)
    return "、".join(f"第{p}页" for p, _ in c.most_common(k)) or "—"


def _one_liner(dec, clusters, m):
    V = dec["verdict"]
    topics = "、".join(c["topic"] for c in sorted(
        dec["p0_clusters"], key=lambda x: -x["n_roles"])[:3])
    if V == "No-Go":
        return (f"这份 BP 当前形态**不建议直接投**：{len(dec['p0_consensus'])} 个共识致命伤"
                f"（{topics}）尚未解决，{len(dec['veto_roles'])} 席投资人触发了否决阈值"
                f"（{len(dec['votes']['No-Go'])} 票 No-Go）；但问题集中在材料与口径层面、"
                f"属可修类型，按第 ⑧ 节清单修订后复审，有翻盘空间。")
    if V == "Conditional-Go":
        return (f"**有条件推进**：共 {len(dec['p0_clusters'])} 个致命议题（{topics}），"
                f"未形成致命共振，{len(dec['veto_roles'])} 席触发否决。"
                f"修正第 ⑧ 节 P0 清单后复审即可进入正式流程。")
    return (f"**可进入正式流程**：评审团未发现 P0 致命伤、无角色触发否决阈值，"
            f"加权总分 {dec['final_score']}，主要空间在 P1/P2 的执行层优化。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="review-raw.json")
    ap.add_argument("--history", default="score-history.json")
    ap.add_argument("--out", default="review-report.md")
    ap.add_argument("--verdict-only", action="store_true")
    args = ap.parse_args()

    raw = json.loads(Path(args.raw).read_text(encoding="utf-8"))
    if "error" in raw:
        print(f"原始数据无有效评审：{raw['error']}")
        return
    hist_p = Path(args.history)
    history = json.loads(hist_p.read_text(encoding="utf-8")) if hist_p.exists() else []
    role_order = {r["role_id"]: i for i, r in enumerate(raw["reviews"])}
    veto_rules = load_veto_rules()

    clusters, items = build_clusters(raw["reviews"], role_order)
    dec = decide(raw["reviews"], clusters, role_order)
    prio = prio_list(clusters, {r["role_id"]: r for r in raw["reviews"]})

    if args.verdict_only:
        print(json.dumps({"verdict": dec["verdict"], "final_score": dec["final_score"],
                          "base": dec["base_score"], "penalty": dec["penalty"],
                          "p0_consensus": [c["topic"] for c in dec["p0_consensus"]],
                          "p0_single": [c["topic"] for c in dec["p0_single"]],
                          "veto_roles": [r["role"] for r in dec["veto_roles"]],
                          "votes": {k: len(v) for k, v in dec["votes"].items()}},
                         ensure_ascii=False, indent=2))
        return

    md = render(raw, clusters, items, dec, prio, history, veto_rules)
    Path(args.out).write_text(md, encoding="utf-8")
    print(f"✅ 已生成 {args.out}（{len(md)} 字符 / {len(md.splitlines())} 行）")
    print(f"   裁定：{dec['verdict']}　加权总分：{dec['final_score']}/100　"
          f"共识P0：{len(dec['p0_consensus'])}　否决席位：{len(dec['veto_roles'])}")


if __name__ == "__main__":
    main()
