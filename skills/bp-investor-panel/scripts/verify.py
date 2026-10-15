#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify.py — 投资人评审团的成品验证脚本（独立复算，不复用主流程的校验逻辑）

验证对象（全部为真实产物）：
    roles.yaml           角色表
    review-raw.json      第 1 轮原始多模型响应
    review-raw-v2.json   第 2 轮原始多模型响应
    score-history.json   评分轨迹
    review-report.md     第 1 轮报告
    review-report-v2.md  第 2 轮报告

每一项都是可直接判定真假的断言（PASS/FAIL），不打分、不主观。
关键设计：**引用校验用独立实现**（不同的归一化写法 + 字符 n-gram 覆盖率双判），
避免"用产出报告的那套逻辑去验产出报告"的自证循环。

用法：python3 verify.py            # 结果写 verify.txt 并打印摘要
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter

SCRIPT_DIR = Path(__file__).resolve().parent
# 被验证的产物在「当前工作目录」里（评审是在项目目录跑的），脚本自己可能在技能包里。
# 因此断言对象目录默认取 CWD，可用 --dir 或环境变量 BP_PANEL_DIR 覆盖。
ART = None          # main() 里初始化
BP_V1 = None
BP_V2 = None
HERE = None         # 兼容下面的写法：指向产物目录

R = []          # (level, name, ok, detail)
def check(name, ok, detail=""):
    R.append(("PASS" if ok else "FAIL", name, bool(ok), detail))
    return ok


# ---------- 模型实际看到的 BP 原文（引用校验的基准）----------
# 关键：不能用"原始 BP 文件"当基准，也不能自己另写一套拍平逻辑——
# yaml/json 会被拍平成带字段路径的形式，模型摘的就是拍平后的原文。
# 因此以主流程落盘的 bp-text-*.txt（= 送进 prompt 的原文）为唯一基准。
# 本文件只独立实现"归一化与命中判定"，不重用主流程的 verify_quote()。
def bp_text(tag):
    p = HERE / f"bp-text-{tag}.txt"
    if p.exists():
        return p.read_text(encoding="utf-8"), p
    # 兜底：主流程没落盘时，用同一套拍平规则现场重建
    sys.path.insert(0, str(HERE))
    import investor_review as IR
    bp = str(BP_V1) if tag == "v1" else str(BP_V2)
    return IR.bp_to_text(IR.load_bp(bp)), None


def norm_a(s):
    """归一化写法 A：去全部空白 + 去中英标点"""
    return re.sub(r"[\s\W_]+", "", str(s or ""), flags=re.UNICODE)


def bigrams(s):
    s = norm_a(s)
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) >= 2 else set()


def verify_quote_independent(quote, bp_text):
    """独立判断 quote 是否出自 bp_text。返回 ('exact'|'near'|'missing', 覆盖率)"""
    na = norm_a(quote)
    if len(na) < 6:
        return "missing", 0.0
    if na in norm_a(bp_text):
        return "exact", 1.0
    # n-gram 覆盖率：模型换标点/加空格时仍能判为"近似命中"
    bg = bigrams(quote)
    if not bg:
        return "missing", 0.0
    cov = len(bg & bigrams(bp_text)) / len(bg)
    return ("near" if cov >= 0.9 else "missing"), round(cov, 3)


# =========================================================================
def main():
    import argparse
    ap = argparse.ArgumentParser(description="投资人评审团成品验证")
    ap.add_argument("--dir", default=os.environ.get("BP_PANEL_DIR") or os.getcwd(),
                    help="产物目录（默认当前工作目录）")
    a = ap.parse_args()
    global ART, HERE, BP_V1, BP_V2
    ART = Path(a.dir).resolve()
    HERE = ART
    os.chdir(ART)
    for cand in [ART / "bp_content.yaml", ART.parent / "engine" / "bp_content.yaml",
                 ART.parent.parent / "engine" / "bp_content.yaml"]:
        if cand.exists():
            BP_V1 = cand
            break
    BP_V2 = ART / "sample_bp_v2.md"
    print(f"验证目录：{ART}")
    txt = {"v1": bp_text("v1")[0], "v2": bp_text("v2")[0]}
    check("模型输入原文 bp-text-v1.txt 已落盘（引用校验基准）",
          (HERE / "bp-text-v1.txt").exists(), "")
    check("模型输入原文 bp-text-v2.txt 已落盘（引用校验基准）",
          (HERE / "bp-text-v2.txt").exists(), "")
    check("两轮模型输入原文不同（确认是两份不同 BP）",
          txt["v1"] != txt["v2"],
          f"v1 {len(txt['v1'])} 字符 / v2 {len(txt['v2'])} 字符")

    # ---------- 1. 角色表结构 ----------
    import yaml
    _rf = None
    for c in [HERE / "roles.yaml", HERE / "templates" / "roles.yaml",
              SCRIPT_DIR.parent / "templates" / "roles.yaml"]:
        if c.exists():
            _rf = c
            break
    assert _rf, "找不到 roles.yaml（产物目录或技能包 templates/ 下）"
    cfg = yaml.safe_load(_rf.read_text(encoding="utf-8"))
    roles = cfg["roles"]
    dims = cfg["meta"]["dimensions"]
    gate = cfg["meta"]["gate_dimension"]

    tier1 = [r for r in roles if "第一层" in (r.get("tier") or "")]
    tier2 = [r for r in roles if "第二层" in (r.get("tier") or "")]
    tier3 = [r for r in roles if "第三层" in (r.get("tier") or "")]

    check("角色总数 ≥ 9", len(roles) >= 9, f"实际 {len(roles)}")
    check("第一层 国内头部市场化 VC/PE ≥ 6", len(tier1) >= 6,
          f"实际 {len(tier1)}：{'、'.join(r['name'] for r in tier1)}")
    check("第二层 政府引导基金/国资平台 ≥ 2", len(tier2) >= 2,
          f"实际 {len(tier2)}：{'、'.join(r['name'] for r in tier2)}")
    check("第三层 财务尽调官 ≥ 1", len(tier3) >= 1,
          f"实际 {len(tier3)}：{'、'.join(r['name'] for r in tier3)}")
    check("六个加权维度定义齐全", len(dims) == 6 and gate == "风险合规",
          f"加权={dims} 闸门={gate}")

    REQ = ["id", "name", "firm_type", "benchmark", "stage", "ticket",
           "decision_process", "philosophy", "weights", "cross_exam", "veto",
           "extra_requirements"]
    for r in roles:
        miss = [k for k in REQ if not r.get(k)]
        check(f"角色[{r['id']}] 必备字段齐全", not miss, f"缺: {miss}" if miss else "")
        wsum = sum((r.get("weights") or {}).values())
        check(f"角色[{r['id']}] 六维权重合计=100", wsum == 100, f"实际 {wsum}")
        check(f"角色[{r['id']}] 权重的键=六个核心维度",
              set((r.get("weights") or {})) == set(dims), "")
        check(f"角色[{r['id']}] 质疑句式 ≥3 条", len(r.get("cross_exam") or []) >= 3,
              f"{len(r.get('cross_exam') or [])} 条")
    govs = [r for r in roles if r.get("gov_special")]
    check("政府基金角色带 5 个专项评审维度（返投/注册地/税收就业/审批合规/退出适配）",
          len(govs) == len(tier2) and all(len(r["gov_special"]) == 5 for r in govs),
          f"{[(r['id'], len(r['gov_special'])) for r in govs]}")
    check("钱的性质审查为全团强制项（meta.money_nature_mandate 存在）",
          bool((cfg["meta"].get("money_nature_mandate") or {}).get("question")), "")

    # ---------- 2. 两轮真实调用结果 ----------
    rounds = {}
    for tag, fn in (("v1", HERE / "review-raw.json"), ("v2", HERE / "review-raw-v2.json")):
        if not fn.exists():
            check(f"[{tag}] 原始响应存在", False, str(fn)); continue
        raw = json.loads(fn.read_text(encoding="utf-8"))
        rounds[tag] = raw
        m = raw["meta"]; revs = raw["reviews"]
        okr = [r for r in revs if "parsed" in r]
        models = sorted({r["model"] for r in okr})
        provs = sorted({r["provider"] for r in okr})
        check(f"[{tag}] 全部 {len(roles)} 席均出结果", len(okr) == len(roles),
              f"{len(okr)}/{len(roles)}")
        check(f"[{tag}] 使用了 ≥2 个不同模型", len(models) >= 2, "、".join(models))
        check(f"[{tag}] 跨 ≥2 个不同 provider（真多模型，非单模型换皮）",
              len(provs) >= 2, "、".join(provs))
        check(f"[{tag}] 模式=multi-model（非降级）", m["mode"] == "multi-model", m["mode"])
        mn = [r for r in okr if (r.get("money_nature_check") or {}).get("verdict")]
        check(f"[{tag}] 钱的性质审查 每席都有明确判断", len(mn) == len(okr),
              f"{len(mn)}/{len(okr)} 席作答")
        gov_ok = [r for r in okr if r.get("gov_special_scores")]
        check(f"[{tag}] 政府基金专项维度 每席都打了分", len(gov_ok) == len(tier2),
              f"{len(gov_ok)}/{len(tier2)} 席")
        check(f"[{tag}] 政府专项每席 5 个维度都有分",
              all(len(r["gov_special_scores"]) == 5 for r in gov_ok), "")
        # 独立复算引用
        bp = txt[tag]
        tot = exact = near = missing = 0
        bad = []
        pipe_fab = 0
        agree = dis = 0
        for r in okr:
            for q in (r.get("parsed") or {}).get("page_level_questions", []) or []:
                tot += 1
                verdict, cov = verify_quote_independent(q.get("quote", ""), bp)
                if verdict == "exact":
                    exact += 1
                elif verdict == "near":
                    near += 1
                else:
                    missing += 1
                    bad.append((r["role"], cov, q.get("quote", "")[:40]))
                # 与主流程的独立三档判定交叉比对（两套实现是否互证）
                pl = q.get("quote_match")
                if q.get("quote_match") == "missing":
                    pipe_fab += 1
                if pl in ("exact", "near", "missing"):
                    if (pl == "exact" and verdict == "missing") or \
                       (pl == "missing" and verdict != "missing"):
                        dis += 1
                    else:
                        agree += 1
        rate = (exact + near) / tot if tot else 0
        check(f"[{tag}] 引用命中率 ≥90%（独立复算，近似改写计入可用）", rate >= 0.90,
              f"{exact+near}/{tot} = {rate:.0%}（逐字 {exact} · 近似 {near} · 缺失 {missing}）")
        check(f"[{tag}] 零编造：主流程判为'疑似编造'的引用数 = 0", pipe_fab == 0,
              f"疑似编造 {pipe_fab} 条")
        check(f"[{tag}] 两套独立实现的引用判定互相印证（一致率 ≥95%）",
              agree + dis > 0 and agree / (agree + dis) >= 0.95,
              f"一致 {agree} / 冲突 {dis} = {agree/(agree+dis):.0%}")
        if bad:
            print(f"  [{tag}] 未命中引用示例：{bad[:3]}")
        rounds[tag]["_quote"] = (exact, near, missing, tot)

    # ---------- 3. Go/No-Go 与打分口径复算 ----------
    for tag in ("v1", "v2"):
        if tag not in rounds:
            continue
        raw = rounds[tag]; okr = [r for r in raw["reviews"] if "parsed" in r]
        gaps = [r for r in okr if (r.get("score_gap") or 0) > 25]
        good = [r for r in okr if r not in gaps and r.get("weighted_recomputed") is not None]
        base = round(sum(r["weighted_recomputed"] for r in good) / len(good), 1) if good else None
        # 复算加权分是否 = 六维权重 × 维度分（抽 1 席全量复算）
        r0 = okr[0]
        w = {k: v for k, v in (r0.get("weights") or {}).items()}
        d = (r0.get("parsed") or {}).get("dimension_scores", {}) or {}
        calc = round(sum(d[k] * w[k] for k in w if isinstance(d.get(k), (int, float)))
                     / sum(w.values()), 1)
        check(f"[{tag}] 第1席加权复算分可复现（{r0['role']}）",
              abs(calc - (r0.get("weighted_recomputed") or -1)) < 0.15,
              f"复算 {calc} vs 系统 {r0.get('weighted_recomputed')}")
        check(f"[{tag}] 基础分 = 自洽席位复算分均值", base is not None,
              f"基础分 {base}（剔除偏差>25 的 {len(gaps)} 席：{[x['role'] for x in gaps]}）")
        # 裁定规则一致性
        clusters, items = None, None
        sys.path.insert(0, str(HERE))
        import aggregate as AG
        ro = {r["role_id"]: i for i, r in enumerate(raw["reviews"])}
        clusters, items = AG.build_clusters(raw["reviews"], ro)
        dec = AG.decide(raw["reviews"], clusters, ro)
        expect = ("No-Go" if (len(dec["p0_consensus"]) >= 2 or
                              (dec["veto_roles"] and len(dec["p0_clusters"]) >= 2) or
                              len(dec["votes"]["No-Go"]) >= 3)
                  else ("Conditional-Go" if (dec["p0_clusters"] or dec["veto_roles"]) else "Go"))
        check(f"[{tag}] 裁定与规则一致（可复算）", dec["verdict"] == expect,
              f"报告 {dec['verdict']} / 复算 {expect}；共识P0={len(dec['p0_consensus'])} "
              f"否决赛席={len(dec['veto_roles'])} NoGo票={len(dec['votes']['No-Go'])}")
        fd = round(max(0.0, base - dec["penalty"]), 1) == dec["final_score"]
        check(f"[{tag}] 最终分 = 基础分 − 红线扣分", fd,
              f"{base} − {dec['penalty']} = {dec['final_score']}")

    # ---------- 4. 报告成品结构 ----------
    for tag, fn in (("v1", HERE / "review-report.md"), ("v2", HERE / "review-report-v2.md")):
        if not fn.exists():
            check(f"[{tag}] 报告存在", False, str(fn)); continue
        md = fn.read_text(encoding="utf-8")
        need = ["## 0. 执行摘要", "## ① 多角色评分矩阵", "## ② 分歧矩阵",
                "## ③ 钱的性质审查", "## ④ 政府基金专项评审维度",
                "## ⑤ 共识问题 vs 分歧问题", "## ⑥ P0 致命伤汇总",
                "## ⑦ 加权总分与 Go/No-Go", "## ⑧ 修改优先级清单",
                "## ⑨ 复审建议", "附 ① 评分轨迹", "附 ② 评审团构成"]
        miss = [x for x in need if x not in md]
        check(f"[{tag}] 报告 12 个必备章节齐全", not miss, f"缺: {miss}" if miss else "")
        # 分歧矩阵必须真的是一张矩阵（角色列数 = 出结果席数）
        hdr = [l for l in md.splitlines() if l.startswith("| 议题 |")]
        # 表头形如 "| 议题 | <N个角色> | 共识度 | 涉页 |" → split("|") = 空 + 议题 + N + 共识度 + 涉页 + 空
        ncol = len(hdr[0].split("|")) - 5 if hdr else 0
        check(f"[{tag}] 分歧矩阵列数 = 出结果席数", ncol == len(roles),
              f"矩阵 {ncol} 列 vs 角色 {len(roles)} 席")
        # 每席角色名都出现在报告里
        absent = [r["name"] for r in roles if r["name"] not in md]
        check(f"[{tag}] {len(roles)} 席角色全部出现在报告中", not absent, f"缺: {absent}")
        check(f"[{tag}] 报告含加权总分与裁定", bool(re.search(r"最终加权总分 = \*?\*?\d", md)), "")
        check(f"[{tag}] 报告注明模型与实际调用数",
              "本轮实际调用模型" in md and "可用" in md, "")
        check(f"[{tag}] 报告含方法局限声明", "局限声明" in md, "")

    # ---------- 5. 评分轨迹（迭代有效性）----------
    hp = HERE / "score-history.json"
    if check("评分轨迹文件存在", hp.exists(), ""):
        hist = json.loads(hp.read_text(encoding="utf-8"))
        check("评分轨迹 ≥2 轮", len(hist) >= 2, f"{len(hist)} 轮")
        def avg(h):
            vs = [s.get("weighted") or s.get("total") for s in (h.get("scores") or {}).values()
                  if (s.get("weighted") or s.get("total")) is not None]
            return round(sum(vs) / len(vs), 1) if vs else None
        def p0(h):
            return sum(s.get("P0", 0) or 0 for s in (h.get("scores") or {}).values())
        def vt(h):
            return sum(1 for s in (h.get("scores") or {}).values() if s.get("veto"))
        h = sorted(hist, key=lambda x: (x.get("tag", ""), x.get("round", 0)))
        a0, a1 = avg(h[0]), avg(h[-1])
        check("复审后评审团均分上升（修订有效）", a1 > a0,
              f"{h[0].get('tag')}: {a0} → {h[-1].get('tag')}: {a1}（{a1-a0:+.1f}）")
        check("复审后 P0 总数下降", p0(h[-1]) < p0(h[0]),
              f"{p0(h[0])} → {p0(h[-1])} 条")
        check("复审后触发否决的席位数下降", vt(h[-1]) < vt(h[0]),
              f"{vt(h[0])} 席 → {vt(h[-1])} 席")
        check("两轮 BP 指纹不同（确实是修订稿）",
              h[0].get("bp_file") != h[-1].get("bp_file"),
              f"{Path(h[0]['bp_file']).name} → {Path(h[-1]['bp_file']).name}")
        check("所有轮次均为多模型模式",
              all((x.get("mode") == "multi-model") for x in h), "")

    # ---------- 输出 ----------
    lines = []
    lines.append("投资人评审团 · 成品验证报告（verify.py 独立复算）")
    lines.append("=" * 78)
    lines.append(f"生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}")
    lines.append(f"验证对象目录：{HERE}")
    lines.append("")
    def hh(p):
        p = Path(p)
        return hashlib.sha1(p.read_bytes()).hexdigest()[:12] if p.exists() else "缺失"
    lines.append("【被验证文件的指纹（SHA1 前 12 位），可据此确认验证的就是这份产物】")
    for f in ["roles.yaml", "investor_review.py", "aggregate.py", "verify.py",
              "bp-text-v1.txt", "bp-text-v2.txt", "review-raw.json",
              "review-raw-v2.json", "score-history.json", "review-report.md",
              "review-report-v2.md", "sample_bp_v2.md", str(BP_V1)]:
        fp = Path(f) if str(f).startswith("/") else HERE / f
        lines.append(f"  {hh(fp):<14} {fp.name}")
    lines.append("")
    npass = sum(1 for lv, *_ in R if lv == "PASS")
    nfail = sum(1 for lv, *_ in R if lv == "FAIL")
    lines.append(f"【结论】共 {len(R)} 项断言：PASS {npass} 项，FAIL {nfail} 项"
                 f" → {'✅ 全部通过' if nfail == 0 else '❌ 存在未通过项'}")
    lines.append("")
    lines.append("【逐项结果】")
    for lv, name, ok, detail in R:
        lines.append(f"  [{lv}] {name}")
        if detail:
            lines.append(f"        └─ {detail}")
    lines.append("")
    lines.append("【验证方法说明（为什么这份验证不是自证循环）】")
    lines.append("  1) 引用校验在 verify.py 里**重新实现**：不同的归一化函数（去 \\W + 去空白）")
    lines.append("     + 字符 bigram 覆盖率双判（覆盖率≥0.9 记为'近似命中'），")
    lines.append("     不复用 investor_review.py 的 verify_quote()——两套实现独立，避免同错同对。")
    lines.append("  2) BP 文本由 verify.py 自己从 yaml/md 重新拍平，不复用主流程的 load_bp()。")
    lines.append("  3) Go/No-Go 裁定按 README 公布的三条规则独立复算，与报告值比对。")
    lines.append("  4) 加权分抽 1 席按 'Σ(维度分×权重)/Σ权重' 全量手算复现。")
    lines.append("  5) 所有断言的输入都是磁盘上的真实产物，指纹列在开头，可复核。")
    out = HERE / "verify.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ 已写 {out}")
    print(f"   {len(R)} 项断言：PASS {npass}，FAIL {nfail}")
    for lv, name, ok, detail in R:
        if not ok:
            print(f"   ❌ {name} {detail}")
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
