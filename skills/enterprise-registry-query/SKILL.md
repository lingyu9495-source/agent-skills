---
name: enterprise-registry-query
description: Use when 查企业工商/风险/失信/股权，或查自然人任职与个人风险. 官方通道优先，三态区分，抓取仅兜底。
version: 1.0.0
author: AI 助手
license: MIT
metadata:
  hermes:
    tags: [尽调, 工商查询, 天眼查, 风险核查, 背景核查]
    related_skills: [biz-platform-data-collection, dual-lens-business-analysis, inbound-material-briefing]
---

# 企业工商信息与风险查询（官方通道）

## When to Use（触发条件）
- 查某家**企业**的工商登记 / 股东 / 实控 / 风险 / 失信 / 被执行 / 限高 / 裁判文书 / 知识产权
- 查某个**自然人**的任职企业、关联企业与个人风险（含给老板/自己人做核查）
- 尽调、客户与供应商背景核查、投前调查的**数据取数**环节
- 不归本技能：纯商业判断与估值（→ `dual-lens-business-analysis` / `company-valuation`）

> 任务类：尽调/核查某家**企业**或某个**自然人**的工商登记、司法风险、股权关系。
> 核心纪律：**先用官方通道（有凭证、不碰密码、可复现），抓取只做兜底；输出严格区分「无记录」和「无风险」**。
>
> 另一套免 key 抓取路径（天眼查直抓正则、企查查浏览器登录绕 WAF）见技能 `biz-platform-data-collection`；本技能只管**官方通道**。

## 一、通道选择

| 通道 | 适用 | 前置 | 优先级 |
|:--|:--|:--|:--|
| **天眼查官方 CLI（`tyc`）** | 企业与自然人全维度 | 一次 Device Flow 授权 | **★★ 首选**（服务端工具最全） |
| **企查查官方 MCP** | 另一家官方源，交叉验证 | Bearer token 写入 config.yaml | ★ 次选 |
| 网页/抓取 | 无凭证、只查少量 | 无 | 兑底（有反爬） |

两家都查得上时**交叉验证**（尤其关键结论）：官方源也可能漏收录。

## 二、天眼查官方 CLI（tyc-cli）

### 安装与登录（Device Flow，必须异步）

```bash
npm install -g tyc-cli          # 依赖 Node 22.19+
tyc --version

# 先探是否已登录，别重复打扰用户：
ls ~/.tyc/config.json && echo "已登录"

tyc login --no-open --no-block  # 未登录时：返回授权 URL + 6 位 auth 码
#  → 把 URL 发成 Markdown 链接 + code block 各一次；auth 码单独放 code block
#  → 然后停下来等用户回「已授权」，不要轮询、不要刷屏

tyc login --resume              # 用户确认后执行
```

**坑（必读）**：
- **auth 码以本机命令输出为准**：用户可能报来另一个码（他在别处开过流程或看错）。不要采信用户报的码，把自己命令返回的码发给他。
- `--resume` 返回「授权尚未完成」＝用户还没在浏览器确认，**这不是错误**；让用户完成后重试，别连续刷命令。
- 未登录时 `~/.tyc/` 为空或无 `config.json`；登录成功后生成 `config.json`（600）。
- **登录一次长期有效**：先探状态，凭证有效就直接查，不要重复走授权。

### 验证接入（只跑一次，耗额度）

```bash
tyc company registration-info "北京金堤科技有限公司"   # 返回法人/成立日期/注册资本/经营状态 = 成功
```

### 常用命令（默认 JSON；要展示候选表加 `--md`）

| 意图 | 命令 |
|---|---|
| **主体锚定（永远先做）** | `tyc company companies "<简称/品牌名>" --pageNum 1 --pageSize 5 --md` |
| 工商登记 | `tyc company registration-info "<全名>"` |
| 风险总览 | `tyc risk overview "<全名>"` |
| 失信 / 被执行 / 限高 | `tyc risk dishonest-info` / `judicial-case` / `high-consumption-restriction` |
| 行政与合规 | `tyc risk administrative-penalty` / `business-exception` / `serious-violation` / `tax-violation` |
| 裁判文书 / 立案 | `tyc risk judicial-documents` / `case-filing-info` |
| 股东与实控 | `tyc company shareholder-info` / `actual-controller` / `beneficial-owners` / `equity-tree` |
| 关联关系 | `tyc company relation-path "<A>" --searchKey2 "<B>"` / `relation-graph` / `group-info` |
| 经营真实性 | `tyc operation bidding-info` / `qualifications` / `administrative-license` / `recruitment-info` / `suppliers-and-customers` |
| 知识产权 | `tyc intellectual_property ipr-score` / `patent-info` / `trademark-info` / `software-copyright-info` |
| 人员背景 | `tyc executive person-profile` / `person-risk-overview` / `personnel-positions` / `personnel-related-companies` |

**主体锚定的坑**：`company companies` 的返回会**混入非同名主体**——除「公司名称匹配」外还有「股东信息匹配」「人员信息匹配」等，指向的是**别的主体**（只是跟你查的人/公司有关联）。选主体必须看 `matchType`，只认 `公司名称匹配`；顺手取 `items[0]` 虽然常常对，但不看 `matchType` 就会把关联方当目标公司接着查下去，结论全错。

### 自然人（老板/高管/合作方）尽调

```bash
tyc executive person-profile               "<其任职公司>" --humanName "<姓名>"
tyc executive person-risk-overview         "<其任职公司>" --humanName "<姓名>"
tyc executive personnel-related-companies  "<其任职公司>" --humanName "<姓名>"
```

**坑**：
- 子命令是 **`personnel-` 前缀**（`personnel-related-companies` / `personnel-positions`），写成 `person-` 报 `unknown command`。不确定先跑 `tyc executive --help`。
- **必须「公司名 + 人名」双锚**；只给人名查不到。
- **覆盖范围有限**：只收录**工商登记层面**的任职/持股。已退出、曾任职但从未登记为高管、或挂在他人主体下的经历**查不到**。

### 额度

CLI 与 MCP **共用同一份调用额度**；`quota_exceeded` 是额度触顶**不是故障** → 转述错误体里的剩余额度/重置时间/升级方式，**不要重试烧额度**。

## 三、输出规范（给老板/客户看）

结论先行，四段：**结论（1–3 句）→ 关键信号表（主体/风险/经营/股权，标 通过｜关注｜异常）→ 依据与限制 → 下一步动作**。

**三态铁律**：严格区分 **查到记录** ／ **已查询未返回记录** ／ **未查询该维度**。绝不把「没查到」写成「没有风险」；每张表下写清本次实际查了哪几个维度。

单个主体系列查询用一段 `for` 循环批量跑，只抽取 `_empty` / `_summary` / `total` 做汇总，避免大 JSON 涂满上下文。

## 四、必须向用户说清的能力边界

查的是**公开工商与司法信息**，不是**央行个人征信**。需求涉「征信/贷款/信用卡/存款」时，**先说清第三方拿不到**，再给能查的部分（失信/限高/被执行/关联企业）。
征信报告需本人实名注册（人行），任何第三方（包括 AI）**无法代查**。

## 五、查自己人时

给老板/同事查前先确认**已获本人授权**（自然人说一句「查我」即算授权）；只走合法公开通道，不代填不代收证件号。结果属个人隐私，**只回私聊、不入对外文档、不进总桶公开区**。
