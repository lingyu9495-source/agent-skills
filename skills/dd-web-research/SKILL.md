---
name: dd-web-research
description: "Use when 尽调/投研联网取数. 三档抓取(含反爬绕过)→Markdown入库。"
version: 1.0.0
---

# 尽调联网取数

尽调的取数需求：**站点多、反爬强、要长期盯、结果要能喂模型**。快通道（`web_search` / `web_extract`）能解决的先用快通道——**本技能是它们失败时的重武器**。

## 工具一：`dd` 命令（推荐入口，已封装）
```bash
dd <url> [输出名]          # 自动三档升级，落盘 LLM-ready Markdown
```
- 产物目录：`~/projects/dd-cache/<输出名>.md`
- **自动升级链**：`get`（静态）→ `fetch`（JS 渲染）→ `stealthy-fetch`（过反爬/Cloudflare）
- 判定标准：输出 > 300 字节才算成功，否则升级下一档

## 工具二：Scrapling 直用
装在独立 venv（**不污染 Hermes 生产环境**）：
```bash
~/.venvs/scrapling/bin/scrapling extract get|fetch|stealthy-fetch <url> out.md --ai-targeted
~/.venvs/scrapling/bin/python your_script.py   # 写代码时
```
**`--ai-targeted` 必带**：抽取正文 + 清洗隐藏元素，防提示注入 + 自动屏蔽 ~3500 广告域名（省 token）。

**选哪一档**：
| 场景 | 命令 |
|---|---|
| 博客 / 新闻 / 政府文书 | `get` |
| 现代 Web 应用、动态内容 | `fetch` |
| 有反爬、Cloudflare | `stealthy-fetch` |

不确定就先 `get`，失败或返回空则升档（`fetch` 与 `stealthy-fetch` 速度几乎一样，升档不亏）。

## 尽调常用目标站点（按抓法分类）
| 类别 | 站点 | 注意 |
|---|---|---|
| 上市公司公告 | 巨潮资讯 `cninfo.com.cn` | 列表页静态可抓；公告详情/PDF 要拼接接口 |
| 交易所监管 | 深交所/上交所/北交所（问询函/监管措施/纪律处分） | 静态为主 |
| 宏观数据 | 国家统计局 `stats.gov.cn`、央行、海关总署 | 静态可抓，数据表常需点进子页 |
| 政策文件 | 中国政府网 `gov.cn` | 政策详情页静态；列表页 JS 加载需 `fetch` |
| 企业工商 | 企查查/天眼查 | **强反爬 + 登录墙**，公开页 1-2 个字段可抓，深度数据不逾线 |
| 司法 | 裁判文书网、执行信息公开网 | 反爬较强，需 `stealthy-fetch` |
| 招投标 | 中国政府采购网、公共资源交易平台 | 分页多，适合 Spider 批量 |
| 行业数据 | 行业协会、券商研报页、垂直行业站 | 多为 PDF，抓下来再用 PDF 工具解析 |

## 输出规范（取数即沉淀）
1. 先落盘 `dd-cache/`（原件不动，可复查）
2. 有价值的转进 `ObsidianVault/知识沉淀/`（带来源 URL + 抓取日期，过 knowledge-sinking 四关）
3. 喂模型做长文考证时**只喂相关章节**，别整站塞（Kimi 整本 5-9 分钟）

## 合规红线（必守）
- 只抓**公开信息**，不绕登录墙、不做个人隐私数据抓取
- 尊重 `robots.txt`；控制频率（Scrapling 的 AutoThrottle 会自动降速，别手动关）
- 不抓取、不存储违反 ToS 的批量商业数据；敏感客户数据不入公共目录

## 何时用快通道而不是本技能
- `web_search` 找线索、`web_extract` 读单个普通页面 → **优先**（快、免费、无依赖）
- 本技能专治：403/429、Cloudflare 挑战、JS 渲染空壳、需要批量/定时监控
- 相关技能：`blocked-page-recovery`（失败恢复策略）、`scrapling-official`（库的完整文档与 API）

## 实战记录（2026-09-10 装库当日实测）
**已验证可用**：
- 国家统计局 `get`：200 / 0.56s / 398 链接
- 巨潮资讯网 `get`：200 / 0.42s / **16,941 字符 Markdown**
- 新华网 `get`：200 / **54,615 字符**
- 浏览器档 `fetch`（DynamicFetcher）：example.com 200 / **2.9s** 正常
- `dd` 命令实抓：巨潮首页 20,042 字节落盘

**已知边界（实测事实，别过度承诺）**：
1. **国内重资源站必须屏蔽资源（2026-09-10 踩坑后解决）**：`www.gov.cn` 纯 HTTP 档只得 638 字符壳；`fetch` 档**裸跑必超时**（`waiting until "load"` 等外部图片/字体/第三方脚本永远等不到）。**解法：`--disable-resources --wait 3000`** → 实测 **5.9s / 17,008 字节** 成功。
2. **CLI 的 `--timeout` 单位是【毫秒】不是秒（极易踩）**：写 `--timeout 60` 实际等于 60ms，报错会显示 `Timeout 90ms exceeded`（数字很小=就是踩了这个坑）。正确值：静态 `30000`、浏览器档 `60000~90000`。`dd` 已内置正确值。
2. **`stealthy-fetch` 对 Cloudflare 极端演示站未过**：`nopecha.com/demo/cloudflare` 上能识别 Turnstile 并自动求解（日志：turnstile version discovered → 3 轮尝试），最终 **403**。成因：演示站故意极难 + 腾讯云数据中心 IP 信誉偏低。**普通 Cloudflare 站成功率未验证——未经实测不得向老板/客户承诺“必过 Cloudflare”。** 真需要时备选：住宅代理（`--proxy`）、真人浏览器 CDP 接管。
3. 需要 JS 渲染的页一定要升到 `fetch` 档（纯 HTTP 会得到“导航壳”如 638 字符的假成功）；**用字数判断比看状态码更可靠**。

