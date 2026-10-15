---
name: github-access
description: Use when 访问/下载/操作 GitHub：拉代码、下文件、传技能。
---

# GitHub 访问与操作（国内机房实测路线）

## 一、凭据纪律
- token 存本机私有文件：`~/.github-token`（chmod 600）
- 读取：`T=$(cat ~/.github-token)`
- **绝不**：回显 token、写进日志/回复、外传、提交进仓库
- 只用 HTTPS

## 二、通道可用性（2026-10-15 实测）
| 通道 | 云C | 云A | 云B | 用途 |
|---|---|---|---|---|
| `api.github.com` | ✅200 | ✅200 | ✅200 | **主干**：读/写/搜/下载 |
| `github.com` | ❌超时 | ✅200 | ❌超时 | 网页 / git clone |
| `codeload.github.com` | ✅301 | ✅301 | ✅301 | **下整包 tarball** |
| `raw.githubusercontent.com` | ❌超时 | ❌超时 | ✅301 | 下单文件 |
| `gh-proxy.com` | — | ✅200 | ✅200 | **镜像兜底（万能）** |
| `registry.npmmirror.com` | ✅ | ✅200 | ✅200 | npm 类资源 |

**结论：API 是主干（普遍可达）；网页/raw 因机而异 → 不通时一律用镜像兜底。**

## 三、常用操作

### 1) 下载单个文件（API 最稳，任何机器可用）
```bash
T=$(cat ~/.github-token)
curl -sL -H "Authorization: Bearer $T" -H "Accept: application/vnd.github.raw" \
  "https://api.github.com/repos/<owner>/<repo>/contents/<path>?ref=main" -o <本地文件>
```

### 2) 下载整个仓库（tarball，最省流量）
```bash
curl -sL "https://codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/main" -o repo.tar.gz
tar xzf repo.tar.gz
```

### 3) 网页/raw 不通时 → 镜像兜底（gh-proxy）
```bash
# 把原 URL 直接拼在 gh-proxy.com/ 后面
curl -sL "https://gh-proxy.com/https://raw.githubusercontent.com/<owner>/<repo>/main/<file>" -o <本地文件>
git clone https://gh-proxy.com/https://github.com/<owner>/<repo>.git
```

### 4) 读仓库信息 / 列目录（API）
```bash
curl -s -H "Authorization: Bearer $T" https://api.github.com/repos/<owner>/<repo>
curl -s -H "Authorization: Bearer $T" https://api.github.com/repos/<owner>/<repo>/contents/<dir>
```

### 5) 搜索代码 / 仓库
```bash
curl -s -H "Authorization: Bearer $T" "https://api.github.com/search/code?q=<关键词>+repo:<owner>/<repo>"
curl -s -H "Authorization: Bearer $T" "https://api.github.com/search/repositories?q=<关键词>"
```
（匿名查询 10 次/分钟；带 token 30 次/分钟）

### 6) 写入 / 更新文件（需 Contents: Read and write）
```bash
SHA=$(curl -s -H "Authorization: Bearer $T" "https://api.github.com/repos/<owner>/<repo>/contents/<path>" | python3 -c "import sys,json;print(json.load(sys.stdin).get('sha',''))")
curl -s -X PUT -H "Authorization: Bearer $T" -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/<owner>/<repo>/contents/<path>" \
  -d "{\"message\":\"<提交说明>\",\"content\":\"$(base64 -w0 <本地文件>)\",\"sha\":\"$SHA\",\"branch\":\"main\"}"
```
**整目录上传（多个 SKILL.md）**：建议本地 `git clone`（走镜像）→ 复制 → `git add/commit/push`，比逐个 API PUT 稳。

## 四、红线
- 不 force push、不删仓库/分支（除非用户明示）
- token 是用户账号凭据 → **只在团队内部机器存放，绝不外传、不进聊天**
- 大文件优先 tarball/codeload，避免逐文件 API（有速率限制）
- API 非 200 时先看 `message`（404=路径/权限问题；403=速率或权限不足）
