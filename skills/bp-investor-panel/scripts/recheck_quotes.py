#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
recheck_quotes.py — 对已落盘的原始评审结果**重算引用命中级别**（不调用任何大模型）

背景：早先的引用校验只有"通过/不通过"两档，把"模型轻微改写原文"也标成了
"未通过原文校验"，措辞上容易被读成"模型编造原文"。改为三档后，需要把已有产物
按同一标准重算一遍。本脚本是**纯确定性重算**：输入是磁盘上的 quote 与 BP 原文，
输出只有 quote_match / quote_verbatim 等校验字段，不产生任何新的模型内容。

用法：python3 recheck_quotes.py            # 重算并回写 review-raw.json / review-raw-v2.json
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import investor_review as IR  # noqa: E402

TARGETS = [("review-raw.json", "v1"), ("review-raw-v2.json", "v2")]


def recheck(raw_path):
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    bp_file = raw["meta"]["bp_file"]
    pages = IR.load_bp(bp_file)
    agg = {"total": 0, "exact": 0, "near": 0, "missing": 0}
    for rec in raw["reviews"]:
        p = rec.get("parsed")
        if not p:
            continue
        st = {"total": 0, "exact": 0, "near": 0, "missing": 0}
        for q in p.get("page_level_questions", []) or []:
            level, real_page = IR.verify_quote(q.get("quote", ""), pages)
            st["total"] += 1
            st[level] += 1
            q["quote_match"] = level
            q["quote_verified"] = level in ("exact", "near")
            q["quote_verbatim"] = (level == "exact")
            q["quote_real_page"] = real_page
            if level != "missing" and real_page and real_page != q.get("page"):
                q["page_mismatch"] = True
            elif level == "missing":
                q.pop("page_mismatch", None)
        st["usable"] = st["exact"] + st["near"]
        rec["quote_stats"] = st
        rec["quote_fabricated"] = st["missing"]
        for k in agg:
            agg[k] += st[k]
    agg["usable"] = agg["exact"] + agg["near"]
    raw["meta"]["quote_check"] = {
        "method": "exact=归一化子串命中；near=字符bigram覆盖率≥0.90；missing=其余",
        "totals": agg,
        "note": "由 recheck_quotes.py 确定性重算，不含任何新的模型调用",
    }
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return agg, len(pages)


def main():
    for name, tag in TARGETS:
        fp = HERE / name
        if not fp.exists():
            print(f"跳过（不存在）：{name}")
            continue
        agg, npages = recheck(fp)
        rate = agg["usable"] / agg["total"] if agg["total"] else 0
        print(f"{name}（BP {npages} 页）：{agg['total']} 条引用 → "
              f"逐字 {agg['exact']} · 近似 {agg['near']} · 未命中 {agg['missing']} "
              f"| 可用率 {rate:.0%}")
    print("\n完成。请重新运行 aggregate.py 以让报告采用三档口径。")


if __name__ == "__main__":
    main()
