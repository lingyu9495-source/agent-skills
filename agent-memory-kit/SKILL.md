---
name: ai-memory-kit-shared
slug: ai-memory-kit-shared
description: 一台机器上所有智能体共用一份记忆（完整包）。豆包/WorkBuddy/Hermes/Claude Code/扣子轮流用，都往同一底座里记、都能查；含团队视图、知识点沉淀、一底座多智能体接法规约、18 个真实踩坑。
version: 1.2.0
author: 九品锦里e
license: MIT
metadata:
  tags: [共享记忆, 智能体记忆底座, 多智能体, 长期记忆, 零依赖]
---

# 共享记忆底座 · 完整包

> 单让一个 AI 有长期记忆，不值钱。值钱的是：**你所有的 AI 共用一份记忆。**

## 它是什么

一台机器（或一台服务器）上建一个记忆底座，所有智能体指向同一个目录：

- 豆包今天记的客户偏好，WorkBuddy 明天报价时能看到
- Hermes 跑流程踩的坑，写成 `knowledge` 后，Claude Code 下次开工先看到
- 团队几个智能体各记多少、最后一条是什么，`ai_mem sources` 一眼看完
- 记忆是你机器上的明文文件，能看、能删、能备份、能搬走

零依赖：只要 Python3 标准库 + SQLite FTS5，单文件，4G 小机器能跑。

## 包内有什么

| 路径 | 内容 |
|---|---|
| `scripts/ai_mem.py` | 底座本体：add / search / recall / inject / digest / **sources** / stats |
| `scripts/install.sh` | 一键安装 + 自检 |
| `scripts/memory_hook.py` | 自动召回钩子示例 |
| `docs/06-跨智能体共享SOP.md` | ★ 一底座多智能体的架构、三步接入、各工具接法、写入规约 |
| `docs/09-云端多设备部署实录.md` | ★ 云端一座：多设备/团队共用，实机勘查结论（服务/账号/限流/网络/运维/三故障） |
| `docs/07-技能-记忆底座部署.md` | 可整包转发给别的 AI 执行的部署技能 |
| `docs/08-技能-记忆修剪与归档.md` | 热层修剪与归档技能 |
| `docs/01`–`05` | 概念与判据 / 三层架构与选型 / 部署 SOP / 验收与 18 坑 / 多端架构 |
| `templates/MEMORY.template.md` | 热层模板 |
| `examples/claude-code/` | Claude Code 集成片段 |

## 五分钟上手

```bash
bash scripts/install.sh
export AI_MEM_DIR=~/.ai-memory          # 所有智能体都指这里
export AI_MEM_AGENT=hermes               # 这个智能体叫什么
ai_mem add "客户只看总价，不接受分项加价" --tags 客户 --kind pref
ai_mem recall "这客户报价有什么讲究"
ai_mem sources                           # 看底座上有谁在用
```

Windows 把 `python3` 换成 `python`，路径写正斜杠（`C:/Users/你/.ai-memory`）。

## 接进任何智能体（只要求"能读文本、能跑命令"）

1. 会话开始跑 `ai_mem inject --days 7`，追加到系统提示
2. `AGENTS.md` / `CLAUDE.md` / 自定义指令写死：开工先 inject，收尾 `add --kind knowledge`
3. 每个智能体设不同 `AI_MEM_AGENT`，团队视图才认得出谁记的

不能跑命令的封闭产品（豆包这类）：把 inject 输出手动贴到对话开头，同样算接上。

## 验收四步

写入 → 同体召回 → **换另一个智能体召回（这才是"共享"的证明）** → 指向空目录必须搜不到。

判成功的硬证据不是"它答得像"，而是会话文件里能 grep 到你注入的原文标记。

## 边界

不承诺"永不忘记"；不是向量库，不做图谱推理；**记忆怎么存我们能保证（本地明文文件），数据怎么流转由你的部署和所用工具决定，本包不对任何"数据去向"作承诺**；一客户一目录，多客户别共用底座。

MIT · 可商用 · 可交付给客户，保留版权声明即可。开源仓库：https://github.com/lingyu9495-source/agent-skills/tree/main/agent-memory-kit
