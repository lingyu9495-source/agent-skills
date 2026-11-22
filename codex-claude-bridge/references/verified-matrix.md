# 实测矩阵（本包发版前的真跑记录）

原则：没跑过的不写进「已验证」。下表每一行都对应一次真实执行，
带日期、版本、端点，可复现。

## 环境

```
OS      Ubuntu 24.04.2 LTS
Node    v22.22.1
npm     10.9.4
Python  3.11+
```

## 2026-11-23 · 全链路（install → doctor → smoke-test）

| 组件 | 版本 | 端点 | 模型 | 结果 | 耗时 |
|---|---|---|---|---|---|
| Claude Code | 2.1.330 | `https://token-plan-cn.xiaomimimo.com/anthropic` | `mimo-v2.6-flash` | 对话 OK / 写文件 OK | 1.2–3.3s |
| Codex CLI | 0.171.0 | `https://api.deepseek.com`（`wire_api=responses`） | `deepseek-flash` | 对话 OK / 写文件 OK | 11s |

`smoke-test.sh` 汇总：**PASS=4 FAIL=0 SKIP=0**。

写文件验证方式：让模型在临时目录创建 `claude-ok.txt` / `codex-ok.txt`，
再用 shell 检查文件存在且内容含预期标记——**不看模型自述，看磁盘**。

## 鉴权方式验证

MiMo 的 Anthropic 端点两种头都接受：

```bash
# x-api-key 方式
curl -s https://token-plan-cn.xiaomimimo.com/anthropic/v1/messages \
  -H "x-api-key: $KEY" -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"mimo-v2.6-flash","max_tokens":40,"messages":[{"role":"user","content":"只回两个字：可以"}]}'
# → 200, content[0].text = "可以"

# Bearer 方式同样 200
```

说明：`ask-claude.sh` 同时设 `ANTHROPIC_AUTH_TOKEN` 与 `ANTHROPIC_API_KEY`，
两种规格的端点都能吃。

## 已知边界（实测发现）

1. **Claude Code 对非 Claude 模型名会打警告**
   `[claude-code:unrecognized_model] {"model":"mimo-v2.6-flash"}`
   只是提示，不影响执行，不必去改客户端。
2. **Codex 会尝试在临时目录建 PATH 别名并拒绝**
   在临时 HOME 下出现 `Refusing to create helper binaries under temporary dir`，
   正常用户 HOME 下不出现。测试时用真实 HOME 才不会误判为失败。
3. **Codex 首次运行较慢（约 10s）**，之后快。别用 5 秒超时判定挂了。
4. **模型名写错会 400**，且部分端点不会回显可用模型列表。改配置前先单独 curl 一次确认。

## 复现命令

```bash
cd codex-claude-bridge
MIMO_API_KEY='tp-...' DEEPSEEK_API_KEY='sk-...' \
  bash scripts/install.sh --target all --yes

bash ~/.codex-claude-bridge/app/scripts/doctor.sh
bash ~/.codex-claude-bridge/app/scripts/smoke-test.sh
```

## 未验证项（诚实标注）

- macOS 实机未跑（脚本按 POSIX 写，理论一致）
- Windows 原生路径（`references/windows.md`）未在实机跑通，属推导步骤
- 智谱 / Kimi / 阿里 的 Anthropic 兼容端点未逐个实测
- 图片输入、thinking 输出在两个 CLI 下的表现未测

以上任一项在被验证前，不要在客户面前说「支持」。
