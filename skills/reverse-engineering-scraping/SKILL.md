---
name: reverse-engineering-scraping
description: Use when 数据藏在签名接口后面 / 要还原加密参数 / 抓 H5 或 App 内部 API / 反爬把常规抓取挡了（sign、token、w_rid、JS 混淆、风控）。合规逆向取数四步法：抓包→定位→还原→复现。
version: 1.0.0
author: AI 助手
license: MIT
metadata:
  hermes:
    tags: [scraping, reverse-engineering, cdp, sign, anti-bot, xhr]
    related_skills: [scrapling-official, blocked-page-recovery, dd-web-research, persistent-browser-automation]
---

# 逆向取数（Reverse-Engineering Scraping）

**定位**：常规抓取（`web_extract` / `scrapling` / `curl`）解决"页面拿得到但内容在 JS 里"；
本技能解决**更难的一层**——数据在一个 **带签名/加密参数的内部接口** 后面，你必须先**还原它的算法**才发得出请求。

## 何时用
- HTML 里没数据，数据在 XHR/fetch 接口后，且接口要 `sign / token / w_rid / timestamp / nonce`
- 要还原一段**混淆 JS** 里的签名或加密算法
- 要抓 **H5 / 小程序 / App** 的内部 API
- 被 403 / 风控挡住，需要"以真浏览器身份"发请求
- **不适用**：纯静态页 → `web_extract`；纯 Cloudflare 人机墙 → `scrapling stealthy-fetch`（或让用户在真机上过验证，参见 `persistent-browser-automation`）

## 四步法（核心方法论）

```
① 抓包（黑盒）  拿到"输入→输出"样本：请求参数 + 签名值 + 响应
② 定位（白盒）  找到签名发生在哪段 JS：源码关键词 → 断点 → 读调用帧
③ 还原          从明文/盐推出算法（自动暴力匹配 + 人工判定）
④ 复现          在 Python 里重算签名发请求；再谈稳定性/限速
```

**核心心法：不要硬啃混淆代码。** 让浏览器替你"跑"一遍，你在内核层观测它——
命中签名函数那一刻，**它的入参就是明文，连盐都不用猜**。这是本技能比"读代码猜算法"快一个数量级的原因。

## 工具：`scripts/revkit.py`（CDP 驱动，零第三方依赖）

解释器用 Hermes venv：`<HERMES_HOME>`（自带 `websockets`）。
浏览器默认用本机 Chromium：`<HERMES_HOME>`。

```bash
PY=<HERMES_HOME>
RK=<HERMES_HOME>

# ① 抓包：抓页面上所有 XHR/fetch（含参数、postData、响应体）
$PY $RK capture "https://目标站/" --eval "触发函数()" --click "#btn" --wait 3 \
       --contains api --with-body --out sample.json

# ② 定位：在含关键词的脚本行设断点，命中后读调用帧（拿明文/盐/局部变量）
$PY $RK breakread "https://目标站/" --match "md5(" --script app.js --depth 5 \
       --expr "typeof str!=='undefined'?str:''" --eval "触发函数()"

# ③ 还原：给定参数与签名值，暴力匹配算法×拼接顺序×盐
$PY $RK solve --params "sku=A1&page=1&ts=1791490344573" --sign "8e2bd78c..." --salts "盐候选"

# ④ 复现：重放抓到的请求（可自动刷新时间戳）
$PY $RK replay --file sample.json [--refresh-ts]

# 辅助：hook 加密库/网络边界（CryptoJS、js-md5、fetch、XHR、subtle）
$PY $RK hooks "https://目标站/" --eval "触发函数()"
```

子命令 `launch` 起一个带调试端口的浏览器；`--port` 决定实例，**按端口自动隔离 profile**。

## 实测坑（都是真踩过的，别重复踩）
- **别用 `pkill`**：本机安全策略会把整条命令判成自终止并杀掉。要停进程就按 **PID** `kill`。
- **profile 锁**：同一个 `--user-data-dir` 已被占用时，新 Chromium 会**静默转发到旧实例并退出**，新端口没人监听 → 表现为"启动超时"。工具已按端口隔离 profile。
- **CDP 参数名撞车**：`Runtime.evaluate` 自己就有 `timeout` 参数。写 `c.call("Runtime.evaluate", timeout=8000)` 会把 8000 当**秒**（≈2.2 小时）→ 死等。区分"Python 等待超时"与"CDP 参数"。
- **页面在断点处暂停时，`Runtime.evaluate` 永不返回** → 触发用 `send`（不等结果），再去 `wait_event("Debugger.paused")`。
- **断点按 `urlRegex` 设，不要按 `scriptId` 设**：reload 后 scriptId 会变，按 id 的断点失效。
- **善用 `locals`**：`breakread` 会打出每层作用域的变量名，比猜"该读哪个变量"靠谱得多。
- **别抓完就不关浏览器**：每实例 ~100-200MB，本机 2核/3.5G 很紧，跑完按 PID 清理。

## 算法 cookbook（常见签名长什么样）
见 `references/signature-cookbook.md`。速记：
- `MD5(sortedParams + salt)`，盐常藏在 JS 的**字符串数组**里（分片拼接）
- `HMAC-SHA256(secret)`、`AES-ECB/CBC`（key 常见硬编码）
- 时间戳 / nonce **参与签名** → 复现时必须现算，别用抓包时的旧值
- 输出变体：大小写、取前 N 位、base64、二次拼接
- 强混淆（webpack + 字符串数组 + 控制流平坦化）→ **直接上 breakread 读明文**，别硬啃
- 真实案例：bilibili **WBI**（`w_rid` + `wts`）、淘宝/京东 H5 API、抖音 `a_bogus`/`X-Bogus`

## 反爬类型与对策
见 `references/anti-bot-taxonomy.md`：TLS 指纹、JS 挑战、行为风控、验证码、设备指纹——以及各自该用哪条通道。

## 合规红线（硬）
- 只抓**你有权访问**的数据：自有店铺后台、公开页面、公开行情。
- 遵守目标站 **robots / ToS**，批量抓取必须**限速**。
- **不绕付费墙、不碰个人敏感数据、不用于攻击 / 刷量 / 薅羊毛。**
- 逆向出来的算法只用于你自己取数，不对外分发破解工具。

## 验证记录
靶场全链路与真实站点冒烟记录见 `references/case-local-target.md`（含复现命令与实测输出）。
