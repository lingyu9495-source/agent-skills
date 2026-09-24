# Agent Skills

A curated set of Agent Skills (`SKILL.md` format) that I actually use in daily work —
each one is distilled from real projects, not written as a textbook.

Compatible with any tool that loads Agent Skills: Claude Code, Codex CLI, Cursor,
OpenClaw / ClawHub, and other SKILL.md-compatible agents.

## Skills

| Skill | What it does |
|---|---|
| `feasibility-report-engine` | End-to-end feasibility-study report pipeline (China NDRC 2023 outline: government 11 chapters / enterprise 10 chapters) + linked financial model worksheets |
| `feasibility-study-consultant` | Decides whether a project is worth doing: screening questions, red flags, go / no-go |
| `ai-image-watermark-removal-boss` | Cleans watermarks off your own and AI-generated images, then runs a pixel-level residual check |
| `bank-scan-household-splitter` | Splits a pile of scanned IDs / forms into per-person Word files, with a "needs manual review" bucket |
| `lowvram-ai-video-comfyui` | Runs AI video generation on an 8 GB GPU (RTX 4060 tested): Wan2.1-1.3B text-to-video + LTX-2B image-to-video |
| `hermes-profile-browser-isolation` | Gives each AI agent its own persistent headless browser so parallel agents don't hijack your screen |
| `excel-keep-format-edit` | Edits numbers inside an existing Excel file without destroying its formatting |
| `novel-deai-detector` | Detects "AI-flavoured" Chinese web-novel text and rewrites it the way a human would |
| `cn-pdf-report-typeset` | Typesets Chinese reports (Word to PDF) with report-grade layout |
| `financial-statement-adjustment` | Adjusts and cross-checks the three financial statements |
| `investment-finance` | Investment & financing playbook — Valuation, term sheets, VAM/repurchase, due diligence, fund ops |
| `funding-fit-diagnosis` | **融资参谋** — Fit diagnosis for founders & small businesses raising money: dual-track scoring (market VC vs. government guidance funds, scored independently) + a named shortlist matched from 23 VC/CVC and 21 government-fund cards (why you / what you lack / how to submit) + gap list + three-route roadmap, plus a zero-dependency offline scoring engine. Keywords: 融资 / 找投资 / 风险投资 / 政府引导基金 / 项目申报 / 商业计划书 / BP / 估值 / TS 条款 |
| `gov-fund-application` | **政府基金申报** — Which level of government money to go after, and how to handle the local-investment (返投) requirement: national / provincial / municipal / district tier decision tree + 21 government-fund and guidance-fund cards (investment style, 返投 ratio, concession rules, application conditions, real cases) + application SOP with document checklist and review-cycle expectations + three compliant paths when you don't want to move your registered address. Companion to `funding-fit-diagnosis`. Keywords: 政府基金 / 政府引导基金 / 产业基金 / 项目申报 / 补贴申报 / 返投 / 招商落地 / 母基金 |
| `ts-term-review` | **TS条款审查** — Term-sheet review: 15 core clauses (valuation Pre/Post, liquidation preference, anti-dilution, drag-along, VAM/earn-out, repurchase, personal guarantees, board veto, protective provisions, non-compete/IP, information rights, closing conditions, voting, default) each graded 🔴 red line / 🟡 negotiable / 🟢 market standard, with negotiation scripts, fallback positions and a clause-level checklist that separates obligations on the company from obligations on the founder personally. Companion to `funding-fit-diagnosis`. Keywords: TS / Term Sheet / 投资条款 / 对赌 / 回购 / 清算优先权 / 反稀释 / 条款谈判 |
| `npl` | Distressed assets (NPL) full stack — Valuation, 30 disposal techniques, due diligence, bid ceiling back-calculation |
| `company-law` | Company law & governance — Equity/control design, board operations, articles clause library, 2024 Company Law |
| `ai-fingerprint-desensitizer` | AI fingerprint desensitizer — 5-dimension AI-detection scoring, layered rewriting playbook, closed-loop re-check |
| `subagent-first` | 子代理优先 · 主代理不下场 — 凡是预计要跑多轮的活（多文件 / 长研究 / 批量 / 长搜索）一律派给后台子代理并行执行，主代理只保留拆解 / 派活 / 汇总 / 对话四个动作。① 决策树四问判定轻重 ② 派活四要素（goal / context 自包含 / output_schema / 验收方式）③ 五步流程：拆解→派活→并行调度→验收→收口 ④ 四组验收清单 + 抽一处回一手来源核对 ⑤ 6 种委派模式 + 12 条反模式；附零依赖委派决策器 `scripts/delegation_planner.py`（喂任务清单直接输出「该派子代理 / 自己做 / 转定时任务」+ 并行分组）。适用平台：Claude Code / Codex / Cursor / WorkBuddy / Hermes 等一切支持子代理或后台任务的 Agent（Hermes 实况对齐见 `references/hermes-runtime-reality.md`） |
| `agent-responsiveness-delegation` | 主脑只做统筹 · 重活全派子代理 · 随时应答 — 现象是「发消息没人应、插话只能排队、等十几分钟才回一句」，根因是主脑把重活放在前台跑、整个回合被占死。① 规则块一页写清判级 / 派完立刻让出对话 / 工单四要素 / 只回收结论 / 拍板留主脑 ② 跨平台幂等落地脚本 `scripts/provision_agent_responsiveness.py`：探测本机已装的 Agent 环境（Hermes SOUL 置顶铁律块、Claude Code 全局指令文件已实测），自动备份、重复执行不重复写、绝不覆盖你已有内容；其余平台导出可直接粘贴的规则块 markdown ③ 体检脚本 `scripts/audit_agent_responsiveness.py`：逐项核对规则块是否存在、是否被后续改动覆盖。纯标准库、零依赖，Windows / macOS / Linux 通用。适用平台：Claude Code / Codex / Cursor / WorkBuddy / Hermes 等任意 Agent（无实测落点的平台走「导出可粘贴规则块」路径） |

| `doubao-account-pool` | **豆包网页版多实例工作台（免费版）** — Batch image/video generation on Doubao's web UI, zero API keys: one authorized account = one isolated browser instance (own `user-data-dir` + own CDP port) so instances never collide or kick each other offline; QR-code authorization with auto-crop so the code can be scanned straight off a phone, parallel prompt feeding with a **baseline gate** that stops you from grabbing the previous run's stale image, a video flow that reads the confirmation card and **aborts on the paywall instead of clicking upgrade**, and a re-fetch path that recovers recent images/videos after the browser was closed. Config-driven (`env > ./doubao_config.json > $DOUBAO_HOME/config.json > built-in defaults`), ships no cookies, no keys, no machine paths; long jobs land on disk first and every command prints only `@@` structured lines, so page text / DOM / screenshots never flood the agent conversation. Keywords: 豆包 / 多实例 / 扫码授权 / 批量出图 / 出视频 / 浏览器自动化 / CDP | A fuller **multi-instance production workbench** (parallel N-way runs, instance-pool management, batch spec matrices, output QC) is a separate product — see the skill footer for the purchase instruction. |
| `gzh-fullauto-publish` | Full-auto WeChat Official Account production: an AI agent drafts the piece, local scripts log in by QR, render covers, save to your draft box and verify |
## Install

Drop any skill folder into your agent's skills directory, e.g. `~/.claude/skills/`,
`~/.codex/skills/`, `~/.cursor/skills/`, or wherever your agent loads skills from.

Each skill folder contains a `SKILL.md` (the definition your agent reads) plus any
`scripts/` and `references/` it needs.

## License

MIT

## Channels

- Tencent SkillHub: https://skillhub.cn (search "九品锦锂e")
- ModelScope (Alibaba): https://modelscope.cn/profile/ly5419495
- ClawHub: coming soon
