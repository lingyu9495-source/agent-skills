# 反爬类型与对策（通道选择）

> 原则：**先用成本最低的通道，挡住再升级**。别一上来就开浏览器。

## 分层通道

```
L0  web_search / web_extract          静态页、公开文章、API、RSS     ~0 成本
L1  curl / requests + 伪装头           简单接口、无反爬              低
L2  curl_cffi / scrapling impersonate  TLS 指纹（JA3/JA4）校验       低
L3  scrapling fetch / 本机 CDP 浏览器   JS 渲染、动态参数            中
L4  本技能 revkit（逆向签名）           签名参数、加密接口             中
L5  scrapling stealthy-fetch            Cloudflare / 强风控          高
L6  用户真机 + 接管（persistent-browser-automation）  人机验证/登录态  最高
```

## 按类型对策

| 反爬类型 | 识别特征 | 对策 |
|---|---|---|
| **User-Agent / Referer 校验** | 直接 403，换 UA 就好 | L1 |
| **TLS 指纹（JA3/JA4）** | curl/requests 必被拒，浏览器正常 | L2 `curl_cffi` 或 `scrapling impersonate='chrome'` |
| **签名参数（sign/w_rid/x-sign）** | 少参数或多参数都 403 | **L4 本技能** |
| **JS 挑战 / 动态 cookie** | 首次返回一段 JS 设 cookie | L3 CDP 真浏览器跑一遍拿 cookie |
| **Cloudflare / Turnstile** | "Just a moment..." 5 秒盾 | L5 `scrapling stealthy-fetch --solve-cloudflare`；强验证 → L6 用户真机 |
| **行为风控** | 访问频率/轨迹异常后封 | 限速 + 随机间隔 + 复用登录态；别多开并发 |
| **验证码（滑块/点选/极验）** | 出现图形验证 | 不硬破；L6 让用户在真机过一次，再复用登录态 |
| **设备/浏览器指纹** | canvas/webgl/audio 采集 | `scrapling` 的 `--hide-canvas`、CDP 用真实 profile |
| **IP 限制** | 换 IP 就好 | 代理池（`scrapling` 支持轮换）；注意合规 |

## 关键判断：**先看是不是"签名"，再谈别的**
- 少一个参数就 403、多一个参数也 403、参数都对但不带 `sign` 也 403 → **是签名**，走 L4。
- 直接 403 且响应头有 `cf-ray` / `server: cloudflare` → **是 WAF**，走 L5/L6。

## 合规提醒
- 所有通道都受同一红线约束：**只抓你有权访问的数据**。
- 风控/验证码是对方明确的拒绝信号，**不要"硬破"**；有合法需求就走开放平台 API 或商业数据源。
