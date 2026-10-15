# 投资人评审团（Investor Panel Review）

对一份 BP 初稿做**多角色 × 多模型**的独立评审：逐页挑刺、六维打分、找致命伤，
聚合成"分歧矩阵 + 钱的性质审查 + Go/No-Go 报告"。这是 BP 初稿进入正式报告前的**强制闸门**。

评审团 = **国内知名代表性机构的画像（类型原型表述）** + **政府基金视角** + 财务尽调，共 9 席：

| 层 | 席 | 角色 | 对标公开风格 | 单笔规模 |
|---|---|---|---|---|
| 第一层 国内头部市场化 VC/PE | 1 | 国资创投原型 | 深创投 | 3,000 万 – 2 亿 |
| | 2 | 制造业深耕型 | 达晨财智 / 同创伟业 | 3,000 万 – 3 亿 |
| | 3 | 长期研究驱动型 | 高瓴 | 1 亿 – 10 亿 |
| | 4 | 赛道卡位型 | 红杉中国 | 2,000 万 – 1.5 亿 |
| | 5 | 投人型 | 经纬中国 / 启明创投 | 1,000 万 – 1 亿 |
| | 6 | 产业整合型 | 中金资本 / 复星 | 1 亿 – 20 亿 |
| 第二层 政府引导基金与国资平台 | 7 | 政府引导基金原型 | 深圳市引导基金 / 国投创合 | 子基金 5,000 万 – 5 亿 |
| | 8 | 地方产业投资平台原型 | 合肥产投 / 亦庄国投 / 苏州元禾 | 5,000 万 – 10 亿 |
| 第三层 财务尽调 | 9 | 财务尽调官 | 尽调实务通行标准 | 不投钱，可实际否决交易 |

> 机构名一律以"类型原型"表述，画像对标真实机构的**公开**投资方向与理念；
> **不编造任何机构的内部制度**（投委会人数、投票权、过会轮次均未公开，prompt 里明确禁止模型编）。

```
review/
├── investor_review.py      主引擎：多角色×多模型评审 → review-raw.json + score-history.json
├── aggregate.py            聚合器：→ review-report.md（①–⑨ 九节 + 两个附录）
├── roles.yaml              ★ 角色库（9 个角色 · 三层结构，改这里就能加角色）
├── iteration-protocol.md   迭代规程：初稿→评审→修订→复审（≤3 轮，直到无 P0）
├── review-report.md        产出：第 1 轮评审报告（初稿）
├── review-report-v2.md     产出：第 2 轮评审报告（修订稿复审，含评分轨迹对比）
├── review-raw.json         产出：原始多模型响应（含引用校验结果）
├── review-raw-v2.json      产出：第 2 轮原始响应
├── score-history.json      产出：评分轨迹（每轮追加，两轮共用）
├── verify.txt              ★ 实测证据（环境探测/逐角色结果/引用校验/轨迹，脚本自动提取）
├── verify.py               ★ 成品验证脚本（93 项断言，独立复算，不调模型）
├── recheck_quotes.py       引用命中级别确定性重算（三档口径，不调模型）
├── bp-text-v1.txt          中间产物：v1 实际送进 prompt 的 BP 原文（引用校验基准）
├── bp-text-v2.txt          中间产物：v2 同上
├── review-run.log          运行日志
└── sample_bp_v2.md         修订稿示例（演示第 2 轮复审与评分轨迹）
```

> `verify.py` 默认验证**当前工作目录**的产物（评审在项目目录跑），可用 `--dir` 指定。

---

## 一、快速开始

```bash
cd <工作目录>

# 0）看 key 与模型可用性（不会打印 key 全文）
python3 investor_review.py --list-models
python3 investor_review.py --dry-run          # 真实探测每个模型能不能调通

# 1）第 1 轮评审（9 个角色自动派单到多个模型）
python3 investor_review.py --bp ../engine/bp_content.yaml --round 1 --tag v1

# 2）聚合出报告
python3 aggregate.py --raw review-raw.json --out review-report.md

# 3）只看裁定（脚本/CI 里用）
python3 aggregate.py --raw review-raw.json --verdict-only

# 4）只跑某几个角色（例如本次融资不涉及国资）
python3 investor_review.py --bp <bp> --roles vc_state,vc_people,fdd_officer --round 1 --tag v1

# 5）复审：修订稿跑第 2 轮（同一份评分轨迹，自动出分数变化）
python3 investor_review.py --bp sample_bp_v2.md --round 2 --tag v2 --out-raw review-raw-v2.json
python3 aggregate.py --raw review-raw-v2.json --history score-history.json --out review-report-v2.md

# 6）只重算引用校验（改了 norm 规则后刷新历史数据，不花 token）
python3 investor_review.py --reverify review-raw.json
```

**依赖**：Python 3.11+、`pyyaml`。系统 python3 已带 pyyaml 可直接跑；
PEP668 环境建议建 venv：

```bash
python3 -m venv .venv && ./.venv/bin/pip install pyyaml
./.venv/bin/python investor_review.py --bp <bp> --round 1 --tag v1
```

---

## 二、环境变量怎么配（key 从环境变量读，缺失自动跳过并在报告里声明）

| Provider | 环境变量（任一即可） | base_url | 备注 |
|---|---|---|---|
| DeepSeek | `DEEPSEEK_API_KEY` | `https://api.deepseek.com/v1` | deepseek-flash / deepseek-v4-pro 都是**推理型**，输出预算必须给大（已内置 16384/32768） |
| 阿里云百炼 Qwen | `DASHSCOPE_API_KEY` 或 `QWEN_API_KEY` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | qwen-plus / qwen-max / qwen-turbo |
| Kimi / Moonshot | `MOONSHOT_API_KEY` 或 `KIMI_API_KEY` | `https://api.moonshot.cn/v1` | **kimi-k3 类模型需 `max_tokens≥32768`**，否则 400（已在注册表里配好） |
| 豆包 / 火山方舟 | `ARK_API_KEY` 或 `DOUBAO_API_KEY` | `https://ark.cn-beijing.volces.com/api/v3` | 方舟多为 **endpoint id（`ep-xxxx`）**，填模型名常报 `InvalidEndpointOrModel.NotFound`；欠费报 `AccountOverdueError` |

**两种配置方式：**

```bash
# 方式 A：临时环境变量
export DEEPSEEK_API_KEY=sk-xxxx
export DASHSCOPE_API_KEY=sk-yyyy

# 方式 B：写进 .env（脚本自动补读若干 `.env` 文件，且不覆盖已有环境变量）
#   1) 系统共享 .env
#   2) 当前 profile 的 .env
#   3) review/.env          ← 本模块自己的，优先级最低
```

**降级行为（重要）：**

- 某 provider 缺 key / 被拒 → **自动跳过**，在 `review-raw.json` 的 `meta.models_skipped`
  与报告"局限声明"第 3 条写明原因（欠费/404/无 key 原样记录）。
- **只剩 1 个可用模型** → 自动进入 `degrade-single-model` 模式：所有角色用同一个模型，
  靠 **prompt 严格隔离 + 每角色一次独立调用**保证"多角色"，并在报告的局限声明里
  **明写"分歧度会被系统性低估，建议补齐第二个 key 后重跑"**。
- **一个可用模型都没有** → 直接退出码 2，写一份带原因的 `review-raw.json`，**不产出假报告**。

---

## 三、怎么加新角色（只改 `roles.yaml`，不改代码）

在 `roles.yaml` 的 `roles:` 下追加一个条目，脚本与聚合器都会自动识别：

```yaml
  - id: vc_esg                          # 英文短标识，用于 --roles 与评分轨迹的跨轮对比
    name: "ESG 与合规审查官"
    firm_type: "受托 ESG/合规审查机构"
    benchmark: "公开 ESG 披露与合规通行标准"
    tier: "第三层｜专项审查"
    stage: "全阶段"
    ticket: "不投钱，出具审查意见作为投资前提条件"
    decision_process: "资料清单 → 合规访谈 → 出具意见 → 提交投委会作为前提条件"
    philosophy: "合规不是加分项，是入场券——有硬伤的标的我不让它上会。"
    weights: {市场: 10, 团队: 10, 产品壁垒: 10, 商业模式: 20, 财务预测: 20, 融资方案: 30}
    gate_dimension: 风险合规            # 闸门维度：不参与加权，低于阈值即一票否决
    cross_exam:
      - "数据合规做到哪一步了？涉及个人信息吗？"
      - "这个业务需要牌照吗？拿了吗？"
    veto: "总分<65；或 风险合规<60；或 存在未披露的资质/牌照硬伤"
    extra_requirements:
      - "资质证照清单与有效期"
      - "数据合规与个人信息处理说明"
    lens:
      - "牌照与资质完备性"
      - "数据合规链路"
    page_focus: [13, 14]
```

**四条硬性约定：**

1. `weights` 的**六个**维度（市场/团队/产品壁垒/商业模式/财务预测/融资方案）**必须合计 = 100**
   （脚本会 WARN 提醒）。`风险合规` 是**闸门维度**，不写进 `weights`，改成写 `gate_dimension`；
2. `veto` 里的数值阈值用固定格式，脚本会解析并**自动判定**是否触发否决：
   - 总分：`总分<65`
   - 单维度：`财务预测<60`（维度名必须是七个之一，含闸门维度 `风险合规`）
   - 定性条件写在后面（由模型自判 `go_no_go`）；
3. `id` 唯一，**不要改名已存在的 id**——`score-history.json` 按 id 做跨轮对比；
4. 若设了 `gov_special`（政府基金五个专项维度），该角色会被自动要求输出
   `gov_special_scores` 与 `gov_special_findings`，报告第 ④ 节随之生成。

改完直接重跑即可，无需改任何 Python 代码；新角色自动参与模型派单轮转。

---

## 四、模型派单规则（"多模型"是怎么保证的）

`assign_models()` 按 **provider 轮转**派单，而不是把一个 provider 的模型用完再换：

| 席位 | 1 国资创投 | 2 制造业 | 3 长期研究 | 4 赛道卡位 | 5 投人型 | 6 产业整合 | 7 引导基金 | 8 地方平台 | 9 尽调官 |
|---|---|---|---|---|---|---|---|---|---|
| provider | DeepSeek | Qwen | DeepSeek | Qwen | DeepSeek | Qwen | DeepSeek | Qwen | DeepSeek |
| model | flash | plus | v4-pro | max | flash | turbo | v4-pro | plus | flash |

相邻席位**一定是不同 provider**，所以不同角色确实由不同模型产出，分歧是真实的**跨模型分歧**。
想手动指定：`--roles vc_state,vc_people,fdd_officer`。

---

## 五、输出物与打分口径

### 报告九节 + 两附录

| 章节 | 内容 |
|---|---|
| 0 | 执行摘要（6 行读完结论） |
| ① | 多角色评分矩阵（六维 + 闸门维度）+ 维度均分（含"最严/最宽角色"）+ 自报分与复算分的**偏差** |
| ② | **分歧矩阵**：议题 × 角色命中图，一眼分清共识与单方观点 |
| ③ | **钱的性质审查（全团强制项）**：每席都必须回答"你要的是谁的钱、性质和阶段匹配吗" |
| ④ | **政府基金专项评审维度**：返投比例／注册地迁移／税收与就业贡献／国资审批与合规／退出方式对国资的适配性 |
| ⑤ | 共识问题 vs 分歧问题（分开列）+ 严重度判断分歧 |
| ⑥ | P0 致命伤汇总 + 角色原话级致命伤 + **未通过引用校验的条目单列** |
| ⑦ | 加权总分与 Go/No-Go（附**可审计的判定规则回溯**） |
| ⑧ | 修改优先级清单（每条含原文引用与修改动作）+ Top3 立即动作 |
| ⑨ | 复审建议（触发条件、复审对象、轮次、分数异常处理） |
| 附① | 评分轨迹（多轮对比）+ 逐角色首末变化 |
| 附② | 评审团构成（三层/阶段/票额/决策流程/额外材料要求）+ **方法局限声明** |

### 打分口径
- `自报总分`：模型自己给的整体分；
- `复算加权分`：我方用**角色六维 weights × 该角色维度分**重算的加权分；
- `偏差 > 10` → 该角色打分与自己的维度分不自洽，趋势比较以**复算分**为主锚。

### Go/No-Go 判定规则
```
基础分 = 各角色复算加权分的均值
红线扣分（按比例，避免评审团越大扣越狠）：
   共识 P0 议题 × 4 分        （上限 −16）
 + 否决赛席比例 × 20          （上限 −10）
 + No-Go 票比例 × 12          （上限 −6）
最终加权总分 = max(0, 基础分 − 红线扣分)

裁定：
   No-Go          ← ≥2 个共识 P0，或（有角色否决 且 ≥2 个 P0 议题），或 ≥3 票 No-Go
   Conditional-Go ← 存在 P0 或角色否决，但未达 No-Go 门槛
   Go             ← 无 P0、无否决、无 No-Go 票
```

---

## 六、常见问题（踩过的坑）

| 现象 | 原因 | 解决 |
|---|---|---|
| `响应中找不到 JSON`，`finish_reason=length` | 推理型模型（deepseek-flash 等）把输出预算烧在 `reasoning_tokens` 上，JSON 还没开始写就截断 | 脚本已内置**截断自愈**（预算翻倍重试一次）；新模型入表时 `max_tokens` 别小于 8192 |
| `InvalidEndpointOrModel.NotFound`（方舟） | 用模型名代替了 endpoint id，或账户无该模型权限 | 方舟控制台建推理接入点，把 `ep-xxxx` 填进 `PROVIDERS["ark"]["models"]` |
| `AccountOverdueError` / `余额不足或无可用资源包` | 火山方舟欠费 / 智谱余额为 0 | 充值或换 provider（脚本会自动跳过并记录原因） |
| 引用校验通过率低 | BP 以 yaml/json 传入时字段被拍平，模型摘原句时跨了嵌套层级 | 改用 md 分页稿；保持每个字段是完整句子，别把长文本拆碎 |
| 报告说"实际调用 X 个 / 可用 Y 个"不一致 | 旧版把"可用"当"已用" | 报告已拆开写这两个数 |
| 两个进程同时改 `aggregate.py` 导致章节重复 | 多人/多智能体并行改同一文件 | 提交前跑 `grep -n 'A("## ' aggregate.py` 检查章节号是否有重复 |
| 引用校验把 md 表格里的正常摘抄判成"编造" | `norm()` 没去掉 markdown 装饰符（`*` `_` `` ` `` `#` `>` `|`），BP 里写 `**176**`、模型摘成 `176` 就匹配不上 | 已修 `norm()`；历史数据用 `--reverify` 重算即可，无需重跑模型 |
| 某个角色分数极端拉低均分 | 它的自报总分与自身维度分偏差 >25（前后矛盾） | 报告的 `偏差` 列会暴露；基础分已自动剔除偏差 >25 席的整体分（维度分/提问/否决权仍计入） |
| 复审后分数涨了但 P0 变多 | 修订引入了新矛盾（常见于改了数字忘了同步改结论） | 这是有效信号不是 bug，见 `iteration-protocol.md` 第三节的判读表 |

---

## 七、实测结果（本仓库当前状态，2026-09-16）

用 `engine/bp_content.yaml`（15 页）跑第 1 轮，再用修订稿 `sample_bp_v2.md`（18 页）跑第 2 轮：

| 指标 | 第1轮 v1（初稿） | 第2轮 v2（修订稿） |
|---|---|---|
| 评审团 | 9/9 席出结果 | 9/9 席出结果 |
| 实际调用模型 | 5 个 / 2 provider | 5 个 / 2 provider |
| 评审团均分 | 54.9 | **68.9（+14.0）** |
| 加权总分（扣红线后） | 28.9 | **42.2** |
| 触发否决席位 | 8 / 9 | **3 / 9** |
| 共识 P0 议题 | 7 个 | 9 个（**打在 v2 新增内容上**） |
| 引用逐字校验通过率 | 97.3%（73 条） | 94.0%（67 条） |
| 钱的性质审查 | **9 席全判不匹配** | **0 席判不匹配（已修好）** |
| 裁定 | 🔴 No-Go | 🔴 No-Go |

**这轮实测最有价值的一点**：第 2 轮分数明显上升、否决席位从 8 降到 3，
但 P0 议题反而从 7 涨到 9——因为评审团对**修订稿独立重审**，抓到了修订本身引入的新矛盾，
例如 v2 自己写下"2026 年收入 4,600 万＝首年可获取池 4,224 万的 109%"
（3 席独立指出第一年吃掉整个池子不成立），
以及国资落地页把"本地采购/用工/纳税"三种不同量纲的投入直接加总算 1.5 倍返投（4 席指出不可加总）。
**说明评审团不是"读过就算"，也不会因为文档变长就放分。**

完整证据见 `verify.txt`；两轮报告见 `review-report.md` 与 `review-report-v2.md`。

---

## 八、边界与免责

- 评审团是**大模型扮演的角色**，不是真人。观点可作挑刺之用，
  **不能**作为投资决策、估值定价或对客承诺的依据。
- 角色画像对标各机构**公开**的投资方向与理念（依据见 `../research/A-investor-logic.md`），
  一律以"类型原型"表述；**未公开的机构内部制度不写、不引用、不代表任何机构立场**。
- 报告里标了"未通过引用校验"的条目，**不得**摘抄进对客材料。
