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

## Install

Drop any skill folder into your agent's skills directory, e.g. `~/.claude/skills/`,
`~/.codex/skills/`, `~/.cursor/skills/`, or wherever your agent loads skills from.

Each skill folder contains a `SKILL.md` (the definition your agent reads) plus any
`scripts/` and `references/` it needs.

## License

MIT

## Channels

- Tencent SkillHub: published as free skills
- ModelScope (Alibaba): https://modelscope.cn/skills/ly5419495
- ClawHub: coming soon
