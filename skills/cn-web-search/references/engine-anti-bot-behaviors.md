# 引擎反爬行为实测（2026-08，Windows + git-bash + curl）

实测环境：curl -sL + UA "Mozilla/5.0 ... Chrome/120" + Accept-Language zh-CN。
结论随时效变化——被拦就换下一个，别把"某引擎不可用"当永久事实。

## 360搜索 so.com（首选）
- `https://www.so.com/s?q=<urlencode>` 直接可用，页面约 300-400KB，纯 HTML
- 结果块稳定结构：`<h3 class="res-title ..."><a href="https://www.so.com/link?m=...">标题</a></h3>` + `<p class="res-desc ...">摘要</p>`
- 提取正则（已验证）：
  - 标题+摘要块：`<h3[^>]*class="[^"]*res-title[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>\s*</h3>(.*?)(?=<h3|$)`
  - 摘要：`class="[^"]*res-desc[^"]*"[^>]*>(.*?)</p>`（兜底 `</div>`）
- 注意：
  - 提问式关键词会插入 AI 问答块（链接 src 含 `ai.so.com` 或 `so_result_natural_ask`），是 AI 生成摘要，权威性低
  - 结果链接为跳转 `/link?m=...`，要读正文需再 curl 一次
  - 连续快速查询会限流：返回 NO RESULTS → 两条之间 sleep 3
  - 页面混入广告/引流站（教程站、资源站），按域名和日期判断可信度

## 百度 baidu.com（不稳定）
- 首次请求偶能成功（结果正文约 300KB+），但 HTML 中结果大量嵌在 JSON 结构里
- 常见反爬：返回 ~1.4KB 的「百度安全验证 网络不给力，请稍后重试」页
- `<h3 class="c-title">` + `<div class="c-abstract">` 结构已不稳定，解析易失配
- 策略：别依赖百度做批量检索；一次失败就换 so.com

## 搜狗 sogou.com（通常被拦）
- 返回 ~5.4KB 验证页：`SourceVerifyCode：xxxx From：www.sogou.com 此验证码用于确认这些请求是您的正常行为`

## 必应 cn.bing.com（有坑）
- curl 不带 -L 返回 "Object moved" 重定向页
- 带 -L 后内容可能是 GB2312/非 UTF-8：`'utf-8' codec can't decode byte 0xb2`（0xb2 是 GBK 常见首字节）
- 如需用：以 gb18030 解码再处理

## 内置浏览器 browser_navigate
- 可能 auto-launch 失败：`Chrome exited early (exit code: 0) without writing DevToolsActivePort`
- 属环境问题，重试或改用 curl 方案，不要下"浏览器不可用"结论

## 备选：搜索引擎响应时间参考
- 成功抓取耗时：so.com 一次约 2-10s；脚本 fetch 超时设 25s、subprocess timeout 40s 合理
- 批量调研时每条输出到独立文件（s1.txt, s2.txt...），避免上下文膨胀
