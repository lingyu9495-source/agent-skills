# Windows 原生路径（不装 WSL）

客户大概率是 Windows。原包说「Windows 走 WSL」，但真实客户多半不会装 WSL，
所以这里给一条纯 PowerShell 的路。CLI 本身就是 Node 程序，Windows 原生能跑。

## 需要什么

- Windows 10/11
- Node.js 18+（https://nodejs.org 下 LTS，或用 `winget install OpenJS.NodeJS.LTS`）
- 一个国内模型 Key（MiMo `tp-...` 或 DeepSeek `sk-...`）

## 装（PowerShell，逐条执行）

```powershell
# 1. 确认 Node
node -v          # 要 v18 以上

# 2. 装两个官方 CLI
npm install -g @anthropic-ai/claude-code @openai/codex --registry=https://registry.npmmirror.com

# 3. 确认装上了
claude --version
codex --version
```

## 配后端（关键：Claude Code）

```powershell
# 当前窗口生效
$env:ANTHROPIC_BASE_URL   = "https://token-plan-cn.xiaomimimo.com/anthropic"
$env:ANTHROPIC_AUTH_TOKEN = "tp-你的key"
$env:ANTHROPIC_MODEL      = "mimo-v2.6-flash"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = "mimo-v2.6-flash"
$env:ANTHROPIC_DEFAULT_OPUS_MODEL   = "mimo-v2.6-flash"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL  = "mimo-v2.6-flash"

# 永久生效（写进用户环境变量，重开终端仍在）
setx ANTHROPIC_BASE_URL   "https://token-plan-cn.xiaomimimo.com/anthropic"
setx ANTHROPIC_AUTH_TOKEN "tp-你的key"
setx ANTHROPIC_MODEL      "mimo-v2.6-flash"
```

> `setx` 写的是**用户级**环境变量，值会留在注册表里。共享电脑别这么干。

## 配后端（Codex）

Codex 读 `%USERPROFILE%\.codex\config.toml`。不想动用户原有配置就单开一个目录：

```powershell
$env:CODEX_HOME = "$env:USERPROFILE\.codex-bridge"
New-Item -ItemType Directory -Force $env:CODEX_HOME | Out-Null

@'
model = "deepseek-flash"
model_provider = "bridge"
forced_login_method = "api"

[model_providers.bridge]
name = "deepseek"
base_url = "https://api.deepseek.com"
wire_api = "responses"
requires_openai_auth = true
'@ | Set-Content -Encoding utf8 "$env:CODEX_HOME\config.toml"

'{"auth_mode":"apikey","OPENAI_API_KEY":"sk-你的key"}' |
  Set-Content -Encoding utf8 "$env:CODEX_HOME\auth.json"
```

DeepSeek 实测支持 `wire_api = "responses"`；若某个兼容端点只支持 chat，
改成 `wire_api = "chat"` 再试。

## 验证（两边都真跑一遍）

```powershell
claude -p "只回答两个字：可以"
codex exec --skip-git-repo-check -C . "只回答两个字：可以"
```

要看到「可以」。再让它写个文件，确认工具调用通：

```powershell
mkdir $env:TEMP\cc-test -Force; cd $env:TEMP\cc-test
claude -p "在当前目录创建 ok.txt，内容写 WIN-OK" --permission-mode acceptEdits
type ok.txt      # 应看到 WIN-OK
```

## Windows 特有的坑

| 坑 | 表现 | 解法 |
|---|---|---|
| 中文路径 | CLI 读不到工作目录 | 工作目录用纯英文路径 |
| 执行策略 | 跑 `.ps1` 被拦 | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| PATH 没刷新 | 装了但 `claude` 找不到 | 重开终端；或 `npm bin -g` 看真实路径 |
| 公司代理 | npm ERR! / 请求超时 | `npm config set proxy http://...`，或换国内源 |
| 杀软拦 npm | 安装卡住或文件被删 | 加白名单再装 |

## 给客户的一句话

Windows 客户只需要三步：装 Node → 跑一条 npm 命令 → 设三个环境变量。
**不需要 WSL，不需要 Docker，不需要改系统设置。**
