---
name: bp-investor-panel
description: "Use when BP初稿要过投资人评审团挑刺打分. 9席国内机构角色×多模型逐页评审，出分歧矩阵与Go/No-Go。"
version: 1.0.0
author: AI 助手
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [bp-review, investor-panel, multi-model, fundraising, due-diligence]
    related_skills: [investor-pitch-materials, investment-finance, report-production-pipeline, report-reflection-review, parallel-research-synthesis, model-dispatch-playbook]
---

# 投资人评审团 (BP Investor Panel)

对一份 BP 初稿做**多角色 × 多模型**的独立评审：逐页挑刺、六维加权打分、找致命伤，
聚合成「分歧矩阵 + 钱的性质审查 + 政府基金专项 + Go/No-Go 报告」。
本技能是 BP 初稿进入正式报告前的**强制闸门**，不负责写 BP，也不负责排版交付。
脚本只依赖 Python 3.11+ 与 `pyyaml`；模型调用走各 provider 的 OpenAI 兼容 HTTP 接口。

## When to Use

- 用户／客户给来一份 BP 初稿，要「多个投资人会怎么看」「哪里会被否」「能不能过会」
- 出正式 BP／融资材料前做质量闸门（初稿必须经独立角色评审后才能定稿）
- 需要「多模型交叉验证」而不是单一模型的意见——尤其要防单一模型的系统性偏好
- 面向国资／政府引导基金募资，需要专项核对返投、落地贡献、国资保值增值
- Don't use for: 写／排版 BP 本身；对上市股票的选股打分（那是 `investor-panel` 技能）；
  纯财务建模或估值测算（用 `npa-irr-valuation` / `real-estate-investment-calculation`）

## Prerequisites

- Python 3.11+ 与 `pyyaml`：`python3 -c "import yaml"`；缺失则 `python3 -m venv .venv && ./.venv/bin/pip install pyyaml`
- 至少一个 provider 的 key（**多 provider 才能产出真实跨模型分歧**）：

| Provider | 环境变量（任一） | 备注 |
|---|---|---|
| DeepSeek | `DEEPSEEK_API_KEY` | flash / v4-pro 均为**推理型**，输出预算必须给大（注册表已配 16384／32768） |
| 阿里云百炼 Qwen | `DASHSCOPE_API_KEY` 或 `QWEN_API_KEY` | qwen-plus / qwen-max / qwen-turbo |
| Kimi | `MOONSHOT_API_KEY` 或 `KIMI_API_KEY` | kimi-k3 类需 `max_tokens≥32768`，否则 400 |
| 豆包／方舟 | `ARK_API_KEY` 或 `DOUBAO_API_KEY` | 方舟要填 **endpoint id（`ep-xxxx`）**，填模型名会报 `NotFound`；欠费报 `AccountOverdueError` |

- key 也可写进 `.env`（脚本自动补读 若干 `.env` 文件，含工作目录 `.env`，不覆盖已有环境变量）
- 先跑 `--list-models`／`--dry-run` 确认真实可用的模型，**不要假设 key 可用**（余额不足／欠费／无权限都会失败并在报告中记录原因）

## How to Run

```bash
cd <工作目录>                                   # 产物落在这里，建议独立目录
python3 <skill>/scripts/investor_review.py --list-models      # 看 key 与模型注册表
python3 <skill>/scripts/investor_review.py --dry-run          # 真实探测每个模型能否调通

# 第 1 轮：初稿评审（9 席角色自动跨 provider 轮转派单）
python3 <skill>/scripts/investor_review.py --bp <bp文件> --round 1 --tag v1
python3 <skill>/scripts/aggregate.py --raw review-raw.json --history score-history.json --out review-report.md

# 修订后第 2 轮（换 bp，写不同文件名，避免覆盖）
python3 <skill>/scripts/investor_review.py --bp <修订稿> --round 2 --tag v2 --out-raw review-raw-v2.json
python3 <skill>/scripts/aggregate.py --raw review-raw-v2.json --history score-history.json --out review-report-v2.md

python3 <skill>/scripts/verify.py              # 成品验证：93 项断言 + verify.txt
```

`<bp文件>` 支持 `.yaml` / `.json` / `.md`。yaml／json 会按顶层键切成「页」，
md 按 `#`～`###` 标题切页。页号是模型引用原文的坐标，**不要中途改切页规则**。

## Quick Reference

| 目的 | 命令 |
|---|---|
| 列出 provider 与模型 | `investor_review.py --list-models` |
| 探测可用模型 | `investor_review.py --dry-run` |
| 只跑指定角色 | `investor_review.py --bp bp.md --roles fdd_officer,gov_fund` |
| 单模型降级模式 | `investor_review.py --bp bp.md --degrade` |
| 看裁定（脚本用） | `aggregate.py --raw review-raw.json --verdict-only` |
| 重算引用命中级别 | `recheck_quotes.py`（纯确定性，不调模型） |
| 成品自检 | `verify.py` |

## 评审团构成（改 `templates/roles.yaml` 即可加角色，不用改代码）

三层 9 席，均为**国内代表性机构画像**：

| 层 | 席位数 | 角色 |
|---|---|---|
| 第一层 国内头部市场化 VC/PE | 6 | 国资创投原型、制造业深耕型、长期研究驱动型、赛道卡位型、投人型、产业整合型 |
| 第二层 政府引导基金与国资平台 | 2 | 政府引导基金原型、地方产业投资平台原型 |
| 第三层 财务尽调官 | 1 | 财务尽调官（FDD，对交易有一票否决的实际影响力） |

每个角色必须配齐八项：机构类型、投资阶段与单笔规模、决策流程（谁过会／几轮）、
投资哲学一句话、**六个核心维度权重（合计必须=100）**、典型质疑句式（中文口语，像真人说话）、
否决阈值、对 BP 材料的额外要求。角色设计依据与机构画像来源见 `references/role-design.md`。

两个跨全部角色的强制项：

1. **钱的性质审查**——全团每个角色都必须回答「你要的是谁的钱？这笔钱的性质
   （币种／期限／返投／对赌回购／考核方式）和你现在的阶段匹配吗？」。
   BP 没写明资金性质即判不匹配。这是第一性问题：美元基金看五年后退出、人民币市场化基金看对赌回购、
   国资看返投比例与保值增值，**钱的性质决定条款和整个估值故事的写法**。
2. **政府基金专项评审维度**——仅第二层角色打分：返投比例、注册地迁移、税收与就业贡献、
   国资审批与合规、退出方式对国资的适配性。这五项不进入加权平均，但任一项触发否决即 No-Go。

## Procedure

1. **确认口径**：问清这份 BP 要融**哪一轮**、**谁的钱**（美元／人民币市场化／国资）。
   口径不同，评审重点与角色配比都不同——这一步错，后面全废。
   完成判据：能明确说出「轮次 + 资金性质」，或明确记录「BP 未写明」并让它成为评审发现之一。
2. **探测模型**：`--dry-run`。完成判据：知道有几个模型可用、几个被跳过及原因。
   若只剩 1 个模型，脚本自动进入降级模式并在报告中声明局限——**不要手动绕过这个声明**。
3. **第 1 轮评审**：`investor_review.py --bp <初稿> --round 1 --tag v1`。
   完成判据：`roles_succeeded == 角色总数`（缺席位要在报告「失败席位」里被记录）。
4. **聚合出报告**：`aggregate.py`。完成判据：报告含 0／①～⑨／附①② 全部章节，
   且「钱的性质审查」「政府基金专项」两节有真实结论（不是空模板）。
5. **按修改优先级清单修订 BP**：先改共识 P0，再改单角色 P0，最后 P1。
   完成判据：每条 P0 都有对应的修改痕迹（不是改表述，是改实质）。
6. **复审**：换 BP 文件跑 `--round 2 --tag v2`。**复审必须换模型组合、整团重跑**——
   只找提问题的那个角色复核会形成确认偏误。完成判据：`score-history.json` 有两轮、
   报告「附① 评分轨迹」出对比表。
7. **收敛判定**：`aggregate.py --verdict-only` 得到 `Go`／`Conditional-Go` 即放行。
   **轮次上限 3 轮**；3 轮后仍有共识 P0，说明问题不在材料而在生意本身，停下重做商业模型。
8. **成品自检**：`verify.py`。完成判据：断言全 PASS、`verify.txt` 已生成、无「疑似编造」引用。

## Pitfalls

1. **推理型模型的输出预算被思考吃光**——`deepseek-flash` 等在 `max_tokens=4096` 时会出现
   「JSON 还没开始写就被截断」，报错形如 `响应中找不到 JSON` / `finish_reason=length`。
   脚本已内置**截断自愈**（预算翻倍重试一次）；给新模型配注册表时 `max_tokens` 别低于 8192。
2. **引用校验的基准是「模型实际看到的文本」，不是原始 BP 文件**——yaml／json 会被拍平成
   带字段路径的形式（如 `cover.metrics[2].value: 42 家`），模型摘的就是拍平后的原文。
   脚本已把该文本落盘为 `bp-text-*.txt` 作为校验基准；**自行另写一套拍平逻辑去校验会造出假报编造**。
3. **「非逐字命中」不等于「编造原文」**——三档口径：逐字命中／近似改写（bigram 覆盖率≥0.90，
   改写幅度≤10%）／疑似编造。只有第三档不得采信；把近似改写说成编造会冤枉模型、也让报告不可信。
4. **自报总分与维度分不自洽**——模型常给一个「整体印象分」，与它自己的维度分加权复算差 10 分以上。
   脚本以**复算分**为主锚并把偏差>25 的席位从基础分中剔除（维度分、P0、否决权照常计入）。
   比较趋势时不要只看自报总分，否则把「模型心情」当成「BP 变好」。
5. **评审团越大扣分越狠**——红线扣分必须按**比例**（否决赛席比例、No-Go 票比例）而非绝对票数，
   否则总分在不同规模的评审团之间不可比。
6. **单角色提出的 P0 往往最致命**——8 席里只有财务尽调官发现的 10 倍勾稽错误，别人都没看出来，
   但它足以让估值故事归零。共识度衡量的是「观点普遍性」，不是「危害大小」，别只看共识项。
7. **方舟要用 endpoint id**，填模型名必报 `InvalidEndpointOrModel.NotFound`；
   欠费报 `AccountOverdueError`，智谱余额不足报「余额不足或无可用资源包」——
   这些都是**账户问题不是代码问题**，如实记录进报告，不要伪造结果。
8. **一个可用模型都没有时脚本退出码 2**，只写一份带原因的 `review-raw.json`，不产出假报告。
9. **用了 yaml 输入就别指望「表格单元格」形态的引用**——yaml 拍平后是 `key: value` 行；
   要贴近真实 BP 阅读体验，改用 md 分页稿。

## Verification

1. `python3 scripts/verify.py` → `93 项断言全 PASS`，结果落在 `verify.txt`（含所有被验文件的 SHA1 指纹，可复核验证的就是这份产物）。
2. 报告章节齐备：`0`／`① 评分矩阵`／`② 分歧矩阵`／`③ 钱的性质审查`／`④ 政府基金专项`／`⑤ 共识vs分歧`／`⑥ P0 汇总`／`⑦ Go/No-Go`／`⑧ 修改优先级`／`⑨ 复审建议`／`附① 评分轨迹`／`附② 构成与局限`。
3. 分歧矩阵列数 = 出结果席数；每个角色名都出现在报告中。
4. 引用「疑似编造」计数必须为 0；近似改写条目已在 6.2 单列并标注须回原文核对。
5. Go/No-Go 的判定规则回溯可复算：`最终分 = 基础分 − 红线扣分`，规则命中一行行列出。
6. 两轮以上时，评分轨迹显示均分上升、P0 下降、否决赛席下降（修订有效的证据），
   并明确 BP 指纹两轮不同（确实是修订稿，不是同一份跑两次）。

## 与「写 BP」技能的分工（配套使用）

| 技能 | 管什么 | 什么时候用 |
|---|---|---|
| `investor-pitch-materials` | **怎么写**：三类钱逻辑、七阶段作业 SOP、页序模板、PPT 成品 | 从零做 BP／路演 deck |
| 本技能 `bp-investor-panel` | **怎么评**：9 席挑刺、打分、分歧矩阵、Go/No-Go | 初稿完成后、对外交付前的强制闸门 |

顺序：`investor-pitch-materials` 产出初稿 → **本技能评审出 P0 清单** → 按清单修订 → 复审 → 定稿。
**评审逻辑只在本技能里实现**，`investor-pitch-materials` 只引用不重写（避免双份实现漂移）。

## 关键设计约束（改动前先读）

- **角色隔离**：每个角色一次独立 API 调用，prompt 内不含其他角色输出，避免「串味」。
- **跨 provider 轮转派单**：相邻席位一定来自不同 provider，保证分歧是真实的跨模型分歧；
  单模型时必须走 `--degrade` 并在报告「局限声明」第 2 条明写「分歧度会被系统性低估」。
- **外部副作用要自己回读验证**：模型自报的分数／引用都是**自报**，必须用脚本回原文校验后
  才写进报告；`recheck_quotes.py` 是可重复的确定性重算，不产生任何新的模型内容。
- 角色设定只写**公开可查**的口径；机构未公开的内部规则（投委会人数、投票权、过会轮次）一律不写死。
