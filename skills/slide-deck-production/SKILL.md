---
name: slide-deck-production
description: "Use when 做 PPT/演示稿/汇报 deck. 本机出 .pptx 流水线：生成+预览+交付。"
version: 1.0.0
author: AI 助手
license: MIT
metadata:
  hermes:
    tags: [ppt, slides, pptx, 幻灯片, 演示稿, python-pptx, 交付]
    related_skills: [design, pptx]
---

# 在本机产出演示稿（PPT / .pptx）

把「设计规则」落成**可交付的幻灯片文件**的工程流水线。

**分工（别重复造）**：
- `design` 技能 = 设计方法论（`slides.md` 幻灯片专章、8 条核心规则、输出四门禁）——**排版/字号/配色/层级的判据以它为准**，本技能不重述。
- `pptx` 技能 = 通用 .pptx 读写工具集。
- 本技能 = **本机的具体做法**：用什么生成、怎么预览、字体怎么取、低饱和暖色系怎么落、交付怎么打包。

## When to Use
- 用户要一份 PPT / 演示稿 / 可研或尽调汇报 deck。
- 要把已有内容（报告、方案）转成幻灯片。

## 流程

### ① 定内容（先于排版）
逐页写：**assertion 标题（写结论不写主题）＋ 每页一个观点 ＋ 正文 ≤6 行**。遵守 `design/slides.md`。
把内容抽成一份**结构化数据**（每页 `{type, title, lines…}`），后续两个渲染器共用它。

### ② 生成可编辑稿（python-pptx）
```bash
python3 -m pip install python-pptx -i https://pypi.tuna.tsinghua.edu.cn/simple
```
- 16:9 画布 = `Inches(13.3333) × Inches(7.5)`；用空白版式 `prs.slide_layouts[6]` 自绘。
- 背景色：`slide.background.fill.solid(); …fore_color.rgb = RGBColor(...)`。
- 形状去阴影：`shape.shadow.inherit = False`（默认阴影最毁观感）。
- 中文字体名设 `微软雅黑`（目标机 Windows/WPS 常见）；字号见下「版式基线」。

### ③ 渲 PNG 预览（本机关键一步）
本机**未装** LibreOffice/soffice/pdftoppm，无法从 pptx 转图片 → **用 Pillow 按 1920×1080 直渲一版**供手机预览。
- 装了 LibreOffice 的机器可直接 `soffice --convert-to pdf` 再 `pdftoppm`；本机走 Pillow 路线。
- **同一份内容数据同时喂两个渲染器**，别各写一套——否则 PNG 与 PPTX 对不上。
- **中文字体**：`/usr/share/fonts/google-noto-cjk/NotoSansCJK-{Regular,Bold,Medium,Black}.ttc`。⚠️ `.ttc` 是字体集合，**`index=2` 才是简体中文 SC**（0/1 是 JP/KR），用错出异体字。取法：`fc-match "Noto Sans CJK SC:style=Bold" -f "%{file}#%{index}\n"`。
- **缺字自检**：`font.getmask(ch).getbbox()` 为 `None` 才算豆腐块；`✓ ✗ → ≥ ≤ ｜ ／` 在 Noto CJK 里都有字形——缩略图看不清 ≠ 缺字，别据此改文案。
- 多页拼一张**联系表**（缩略网格）给用户一眼看全。

### ④ 门禁自检（交付前）
跑 `design/slides.md` 四道门禁：灰度 / 眯眼 / 竖线 ≤3 / 对比度 4.5:1。自己先用 `vision_analyze` 看联系表，确认无溢出/重叠/缺字再交付。

### ⑤ 交付
- 交付物 = **PNG 总览 ＋ `.pptx` 可编辑稿**；先发飞书聊天框（正文里放生成脚本与要点），再归档到 `knowledge/05-设计资产/<名称>/`（**连生成脚本一起存**，便于复现与改版）。

## 低饱和暖色系 → 幻灯片
底 `#FAF9F5`｜主字 `#141413`｜次字 `#3D3D3A`｜弱字 `#73726C`｜强调/装饰线 `#D4A853`。每页一条琥珀金短线做标题锚点；强调色只给装饰线与关键数字，绝不铺大。

## 版式基线
- 画布 1920×1080：边距 150px、左对齐；封面 96px / 页标题 58px / 正文 34px / 页脚 24px。
- 对应 PPT（13.33in 宽）：封面 40pt / 页标题 28pt / 正文 18pt / 页脚 11pt。
- 页脚只放品牌＋页码；**封面与结尾不放页码**。

## 用 ppt-master 引擎（专业路线）

`design` 是方法论、`pptx` 是通用工具、**`ppt-master`（`<HERMES_HOME>/skills/ppt-master`，v6.7.0）是本机的专业生成引擎**：自绘 SVG → 导出**原生 DrawingML 可编辑 .pptx**（形状/文本在 PowerPoint/WPS 里可直接改）。

**依赖**（已装）：`PyYAML python-pptx XlsxWriter skia-pathops uharfbuzz Pillow numpy`；导入名注意 `pptx` / `xlsxwriter` / `pathops`。

**安装/补全捷径**：GitHub API 常限流、raw 不通 → 直接下整包 `curl -sL -o pm.zip https://codeload.github.com/hugohe3/ppt-master/zip/refs/heads/main`（约 56MB），解压其中 `skills/ppt-master/` 到技能目录，务必跑 `python3 <SKILL_DIR>/scripts/attribution_guard.py`——**exit 0 才算完整官方发行版**（缺 LICENSE/SPONSORS/gate 文件会拒跑）。

**Quick 最小流程（本机复现验证过）**：
```bash
SKILL=<HERMES_HOME>/skills/ppt-master
python3 $SKILL/scripts/project_manager.py init <name> --quick-generate   # 建到 <HERMES_HOME>/projects/<name>_<YYYYMMDD>
# 手写 flat SVG 进 svg_output/：root viewBox="0 0 1280 720" + data-pptx-page-role="cover|toc|section|content|ending"
python3 $SKILL/scripts/svg_quality_checker.py <proj> --quick-generate --canonical-authoring --stage final --json
python3 $SKILL/scripts/svg_to_pptx.py <proj> --quick-generate --no-notes   # -o 指定输出；产物落 exports/
```

**坑**：
- checker 的 WARN **不阻断导出**——只要报告 `blocking: 0` 就能 export；要更干净跑 `compact_svg_styles.py <svg_output> --inplace`（把 font-family 提到 root）。
- 首页 root 建议加 `lang="zh-CN"`（导出读它定校对语言）。
- 顶层散元素建议收进 `<g id>`；纯背景 rect 可标 `data-pptx-role="background"`。
- 更复杂路线（Beautify / Image→PPTX / Create Template / Edit Native）在 `workflows/routing.md` 选路，**一次只加载一条**；非路由资产（templates 1.2 万文件）不影响技能索引成本。

## Pitfalls
- **先定内容再排版**：一上来就调样式会把扁平层级焊死；先做内容清单 + 1–3 分级（`design` 的层级流程）。
- **两个渲染器共用一份数据**：分别手写 PNG 与 PPTX 内容 = 两份必然漂移。
- **`.ttc` 不指定 index 会取到日/韩字形**：简体必须 `index=2`。
- **别把「本机没装 soffice」写成结论**：那只是本机的路径选择；有 LibreOffice 的机器照样能转 PDF。
- **交付不带可编辑稿 = 只做了一半**：PNG 给手机看，`.pptx` 给用户改，两个都要。
