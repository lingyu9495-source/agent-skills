# 03 · 部署 SOP（六步，照着做）

> 适用：给自己装、给客户装、把活交给别的 AI 执行（本文件可整份转发）。

## 第 0 步 · 先问清三件事（不问就是给自己挖坑）

1. **机器**：几核几 G？能不能常驻进程？有没有 sudo？
2. **谁用**：一个人，还是一个团队（决定要不要"一成员一账号"）？
3. **数据边界**：能不能出内网？embedding 用谁的 key、钱谁出？

三问定档：≤4G 或无人运维 → A 档；8G+ 要语义 → B 档；要时序图谱 → C 档。

## 第 1 步 · 落地（A 档，5 分钟）

```bash
bash scripts/install.sh          # 装到 ~/ai-memory，建 ai_mem 软链，跑自检
```

或手动：

```bash
mkdir -p ~/ai-memory/bin && cp scripts/ai_mem.py ~/ai-memory/bin/
chmod +x ~/ai-memory/bin/ai_mem.py
ln -sf ~/ai-memory/bin/ai_mem.py /usr/local/bin/ai_mem
export AI_MEM_DIR=~/ai-memory
```

Windows：放 `C:\ai-memory\bin\`，用 `py ai_mem.py ...`，环境变量 `AI_MEM_DIR`。

## 第 2 步 · 定写入规约（最容易漏，漏了就变垃圾场）

写清三条，贴在项目根目录 `MEMORY-RULES.md`：

1. **什么算"该记"**：结论、决定、口径、偏好变化、承诺时间点、客户的硬约束。
2. **什么不算**：过程闲聊、工具原始输出、可再生成的内容、一次性调试日志。
3. **写的时候带什么**：`--tags`（项目/客户/主题）、`--kind`（fact/pref/event）、`--source`（哪来的）。

模板：

```bash
ai_mem add "客户要求：报价单必须含税，付款 70/30" --tags 客户A,合同 --kind fact --source 会议
ai_mem add "老板偏好：结论先行、不要客套" --tags 用户 --kind pref
ai_mem add "2026-11-20 签约，首付 7000" --tags 客户A,回款 --kind event
```

## 第 3 步 · 接钩子（决定成败的一步）

装了不注入 = 白装。三种接法，任选其一：

**接法 A：会话启动注入（最简单）**

在 Agent 的启动脚本 / system prompt 组装处，执行：

```bash
python3 scripts/memory_hook.py --days 7
```

把输出（带 `【长期记忆·自动召回】` 标记）拼到系统提示末尾。

**接法 B：按需召回（更省上下文）**

每轮用户消息进来时：

```bash
python3 scripts/memory_hook.py --query "用户这句话"
```

只注入相关的 5-10 条。

**接法 C：做成工具（最灵活）**

把 `ai_mem recall / add` 包成工具暴露给模型，让它自己决定何时查、何时写。

### 各框架具体落点

| 框架 | 落点 | 备注 |
|---|---|---|
| **Hermes** | 自定义 memory provider（`hermes-agent/plugins/memory/` 下参照现有 provider 写），或定时把 `inject` 输出写入热层 | 不动内核，升级不易被冲 |
| **QwenPaw** | ≥2.3.0 用 `api.register_runtime_hook(HookBase 子类)` + `ctx.inject_context()`；manifest 的 `qwenpaw_version` 写 `{"min":"2.3.0"}` | 2.2.x 的 `plugins/hooks.py` / `HookSpec` 那套在 2.3 不生效，别查错文件就判"没钩子" |
| **DSH** | 会话事件流里有 `agent/inbox/spliced` 注入口，可直接塞召回块 | 现成的样板，最快 |
| **OpenClaw** | 启动脚本里拼 system prompt，或 MCP 暴露 | — |
| **Claude Code** | `CLAUDE.md` 里写"开工先跑 `memory_hook.py`"，或用 hooks（`PreToolUse`/`UserPromptSubmit`） | 见 `examples/claude-code/` |

装完插件/钩子后必须**重启服务**，并确认新进程环境变量真的带上了——只 `daemon-reload` 不重启等于没改。

## 第 4 步 · 灌第一批记忆

别从空白开始，先灌三类：

1. **用户画像**（称呼、角色、偏好、禁忌）
2. **项目现状**（在做什么、卡在哪、下一步）
3. **历史口径**（报价规则、术语、禁止事项）

20-50 条即可，宁精不滥。

## 第 5 步 · 验收（见 04 篇，四步缺一不可）

## 第 6 步 · 陪跑与养护

- **第 1 天**：让它复述三条记忆（验证召回）
- **第 3 天**：查一次写入量（是不是只写不读、或只读不写）
- **第 7 天**：问一个"两周前的事"，看它能不能自己翻出来
- **每月**：`ai_mem digest` 归档；热层 >8KB 就剪

养护三数（对客户汇报用）：**任务数 / 成事数 / 省下工时折钱**。

## 客户侧要配合的六件事

1. 提供机器与账号（或给你 SSH / 控制台）
2. 指定**一个人**拍板（多人拍板 = 需求反复）
3. 给一份"它该记住什么"的清单
4. 给 3-5 个真实问题做验收题
5. 授权装软件（安全合规要走完）
6. 定一个复盘时间（第 7 天）

## 工时参考

| 档 | 首次部署 | 接钩子 | 验收+陪跑 | 合计 |
|---|---|---|---|---|
| A | 1-2h | 1-3h | 2-4h | **4-9h** |
| B | 3-6h | 2-4h | 4-6h | **9-16h** |
| C | 6-10h | 4-8h | 6-10h | **16-28h** |

> 报工时要算上"网络与镜像"（国内拉 PyPI/GitHub 经常卡）和"客户改需求"的返工，别按顺利路径报。
