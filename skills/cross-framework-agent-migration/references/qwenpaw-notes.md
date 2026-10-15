# QwenPaw 作为迁移目标 — 实证笔记

QwenPaw（AgentScope 团队开源，Apache 2.0，个人智能体框架）是跨框架迁移的一个常见目标。
本文件记录经官方文档核实 **并已实机验证** 的框架事实，避免下次重复调研或重复踩坑。

---

## 一、已核实（官方文档）

| 项 | 事实 |
|---|---|
| 版本 / 运行时 | v2.2.0 时期；Python 3.10–3.13；基础是 AgentScope + AgentScope Runtime + ReMe |
| 安装 | `pip install qwenpaw` 或一键脚本（自动装 uv、建虚环境）；桌面端可用 Tauri 包 |
| 启动 / 控制台 | `qwenpaw init --defaults` → `qwenpaw app`；Web 控制台默认 `127.0.0.1:8088` |
| 工作目录 | 默认 `~/.qwenpaw`（环境变量 `QWENPAW_WORKING_DIR`）；密钥默认 `~/.qwenpaw.secret/providers.json`（`QWENPAW_SECRET_DIR`） |
| 配置两层 | 全局 `config.json`（模型提供商 + 智能体列表）+ 每 agent 的 `workspaces/{agent_id}/agent.json`（频道/心跳/工具/MCP/安全）。同名字段 agent.json 覆盖 config.json；**agent.json 2 秒热加载，改频道无需重启** |
| 多智能体 | 原生支持；每个 agent 独立 workspace、配置、记忆、技能本地副本、对话历史；CLI 全命令带 `--agent-id`（默认 default） |
| IM 频道 | 飞书/DingTalk/Discord/Telegram 等为内置一等频道；填 App ID + App Secret 到该 agent 的配置即可 |
| **飞书接入方式** | 走 **WebSocket 长连接**，**不需要公网回调地址** → 现有飞书自建 App 可直接复用；IM 后台只需启用机器人能力 + 订阅「接收消息 v2.0」事件 |
| 模型接入 | 支持任意 OpenAI 兼容端点：添加提供商 → 协议选 OpenAI 兼容(Chat Completions) → 基础 URL + API Key → 添加模型 ID → 设为默认 LLM。也支持 Ollama/LM Studio/本地模型 |
| 定时能力 | 两类：Scheduled tasks（多任务各自 cron 配置，可定时发消息到频道或提问后把答案回推）+ Heartbeat（固定间隔执行预设问题，发到最近活跃频道） |
| 记忆 | 基于 ReMe，本地存储、数据不出本机 |
| 技能 | 技能池（共享仓库）+ 工作区技能（agent 运行时的本地副本）；切换用 Console / CLI / skill 配置；带技能安全扫描 |
| 工具 | 内置文件读写、命令执行、浏览器等，可逐个启停；MCP（stdio/HTTP/SSE）在 agent 配置的 mcp 段接 |
| CLI 子命令 | `init` / `app` / `cron` / `skills` / `models` / `channels` / `env` / `doctor` / `daemon` / `tui` |
| 旁路 | 云C有一键部署渠道（计算巢 / ECS / PAI-EAS），但托管路径定制灵活度低；自建 pip + 常驻更可控 |

---

## 二、实机验证结论（做迁移方案前先读这节）

### 技能格式：可直接搬，不用重写
- 技能 = **`SKILL.md`（YAML frontmatter + markdown 正文）+ 可选辅助资产**，就是 Hermes/Anthropic 风格，**原生识别**。`skill.json` 是 workspace 级**清单**（记 `enabled`/`channels`/`preload`/`config`），不是每技能文件。
- frontmatter 只校验三处：`name`、`description` 非空且 `metadata` 是 dict。多余键（`author`/`license` 等）忽略。
- 目录两层：`skill_pool/`（共享池，不直接执行）+ `workspaces/{agent_id}/skills/`（运行时真加载的副本，只改这里无效——要同步 skill.json）。
- **`metadata.requires` 的命名空间只认 `openclaw`/`qwenpaw`/`clawdbot`**：源框架的 `metadata.hermes.requires` 不会被读，依赖声明要挪到 `metadata.requires.{bins,env}`。

### 子代理：有，SOUL 的「重活派子代理」可以照搬
- `spawn_subagent(task=…, fork=False|True, background=False|True)`：后台模式拿 `[TASK_ID]`，用 `check_agent_task(task_id)` 回收；`fork=True` 继承全部对话上下文。
- 跨 agent 互调：内置技能 `multi_agent_collaboration` + CLI `qwenpaw agents chat --from-agent A --to-agent B`。
- 外挂编码 agent（ACP）：`delegate_external_agent`，支持 qwen_code/claude_code/codex/opencode，默认关闭需手动开。

### shell：能执行
- 内置 `execute_shell_command`（参数 `command`/`timeout` 默认 60s/`cwd` 默认工作区）；技能正文写 `python script.py` 由模型当 shell 命令执行。
- 内置工具全景：`read_file` `write_file` `edit_file` `append_file` `grep_search` `glob_search` `execute_shell_command` `delegate_external_agent` `browser` `desktop_screenshot` `view_image` `send_file_to_user` `memory_search` `get_current_time` `set_user_timezone` `get_token_usage`。
- **没有 `web_search`**：联网检索走 `browser`。源技能里的 `web_search` 要映射过去。

### cron：能推 IM 会话，但**没有「写文件」字段**
- 定义存 `workspaces/{agent_id}/jobs.json`；`qwenpaw cron create -f <spec.json> --agent-id X` 或直接改 jobs.json。
- dispatch 只能投 `channel`（`target.{user_id,session_id}`）或 `save_result_to_inbox`；**要落盘就在提示词里让 agent 自己调 `write_file`**。
- 5 字段 cron（无秒）；`schedule.timezone` **必须每条显式指定**（框架默认 UTC）。

---

## 三、迁移后运维实战坑

### cron 的 `request.input` 必须是 `List[Message]`，不是字符串
写 `{"request": {"input": "一段提示词"}}` 会在执行时报 `1 validation error for AgentRequest / input: Input should be a valid list`，**任务创建成功但一跑就 error**（静默失败）。正确形状：
```json
"request": {"input": [{"role": "user", "type": "message",
                        "content": [{"type": "text", "text": "<提示词>"}]}]}
```
对应源码 `agentscope_runtime.engine.schemas.agent_schemas.AgentRequest.input: List[Message]`。建完任务必须 `cron run` 真跑一次看 `cron state` 的 `last_status`，别只看创建成功。

### 容器化部署的时区三重坑
新框架跑在 Docker 里时，容器默认 UTC：`execute_shell_command` 跑 `date` 拿到 UTC，agent 据此命名的文件/日志行会**差 8 小时**（凌晨跑会差一整天），而 cron 的调度语义又各自独立。修法三处一起做，缺一处就仍有错位：
1. 容器时区：`ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime; echo Asia/Shanghai > /etc/timezone`
2. 框架全局 `config.json` 的 `user_timezone`
3. **每条 cron 任务的 `schedule.timezone`**
并在任务提示词里写明「日期一律取 `date` 命令的返回值，不要用对话内容的时间戳推断」。

### 主动推消息前，必须有人先跟 bot 聊过
框架拿投递目标靠 `workspaces/{agent_id}/chats.json`。**没有真实会话记录时该文件为空**，无法凭空构造 `user_id`/`session_id`。所以：切完通道后先让老板给每个 bot 发一条消息，再读 chats.json 取真实标识去建 cron。

### 容器内 agent 的远程管理通道
目标框架跑在容器里时，容器内的 agent 要 SSH 管其他机器，**不能只看宿主机能不能连**：
- 容器 `/root` ≠ 宿主机 `/root`，容器有自己的一份 `.ssh`；宿主机 root 常被挂到容器内其他路径（如 `/hostroot`），`docker inspect --format '{{range .Mounts}}…'` 看实际映射。
- 两条路都可用：容器自有密钥（`/root/.ssh/id_*`）或宿主机密钥（`/hostroot/.ssh/id_*`），**两条都要在目标机 authorized_keys 里注册**才叫配好，选一条主用、另一条兜底。
- 容器里已挂载的共享目录（知识库/数据卷）**免 SSH 直接读写**，比绕 SSH 更省事，先查挂载表再决定要不要开通道。
- 验证必须在**容器内**执行一次真登录（`docker exec <c> ssh -i … user@host whoami`），宿主机的成功不算数。
- 给外部机器开 root 直连是安全边界决策，必须让老板拍板；配完提醒收紧安全组来源 IP。

---

## 四、仍未成熟、需按环境实测
- **第三方模型在目标框架下的工具调用/流式表现**：换框架后单独跑一遍真任务验证，别默认原模型行为一致（本框架对 OpenAI 兼容端点支持良好，但带工具调用的长任务要实测）。
- 会话历史（state.db 等）是否重建：体积大、格式不通用，默认丢弃，仅在老板明确要求时迁移。

---

## 来源
- 官方文档 https://qwenpaw.agentscope.io/ （docs/deploy、docs/config、docs/channels、docs/multi-agent、docs/skills、docs/heartbeat）
- 云C帮助文档 https://help.aliyun.com/zh/model-studio/qwenpaw
- GitHub https://github.com/agentscope-ai/QwenPaw
