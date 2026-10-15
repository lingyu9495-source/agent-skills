# DeepSeek Harness（dsh）已核实事实

来源：官方站点 / GitHub 仓库 / 第三方横评 **+ 本机实机部署验证**。迁往/评估 dsh 前先读这里，省一轮重复调研。

## 是什么
- DeepSeek 开源（MIT）的 agent harness，官方明确对标 Claude Code。
- 基于 Cordis 的「一切皆插件」：模型适配器、工具注册表、会话日志、沙箱、**agent 循环本身**都是可替换插件，没有需要打补丁的特权内核。
- 定位是**框架/底座**，不是开箱即用的产品（Codex / Claude Code 是产品）。同任务实测更慢（125s vs 55s），优势在可编排、可审计（model-visible means logged）、可任意换模型（任何 OpenAI 兼容端点）。

## 运行与依赖
- 运行时 Node.js（需 ≥22.19 或 24+），插件增删另需 pnpm；`npm install -g @deepseek-ai/dsh` 实测 540 包 / 约 2 分钟（0.2.0-rc.2）。
- **实测资源占用：web profile 常驻约 200 MB**；`npm install` 期间峰值 1 GB+。**瓶颈是内存不是 CPU**——推理在云端 API，本地只是瘦客户端。
- 启动硬要求 `DEEPSEEK_API_KEY`，缺了直接退出（`MISSING_CREDENTIAL`）；只验证技能识别时占位值也能通过启动检查（模型调用会失败）。
- **Web UI 有访问令牌，不是「无鉴权」**：直接访问 3080 得 **401**（browser-trust fence），页面提示 `dsh web authentication required; reopen the URL printed by dsh web.`。令牌只在启动输出里，形如 `http://127.0.0.1:3080/?token=...`——**必须把启动输出重定向/tee 后再抓，不能猜也不能缓存**（每次重启都变）：
  ```bash
  dsh web --no-open 2>&1 | tee /tmp/dsh-web.log
  grep -oE "http://127\.0\.0\.1:[0-9]+[^[:space:]]*" /tmp/dsh-web.log
  ```
  默认只绑回环；远程访问走 `ssh -L 3080:127.0.0.1:3080 <user>@<host>`。**在 agent 的 background terminal 里起的实例会随会话结束而停**（令牌也再变一次），要常驻必须 systemd。
- **一次性执行：`dsh headless "任务描述"`** 跑完打印结果并退出——验证与自动化的主力，不必开 UI。
- 四种模式：**Standard**（完整编码 agent：文件/shell/搜索/技能/规划/子 agent）/ **PTC(Code)**（先生成 TypeScript 程序再执行，适合批量）/ **Minimal**（仅 bash + 文件编辑，跑 benchmark 用）/ **Creator**（改运行时、造新预设）。
- **基准成绩不可跨模式比较**：官方分数用 Minimal 模式跑出，不代表 Standard。
- 配置两层：`~/.dsh/settings.yaml` 用户设置（**首次启动会自动导入**成 `~/.dsh/profiles/<name>/cordis.patch.yml`，**此后改原文件不再生效**，要改 patch 文件）；`~/.dsh/.credentials.yaml` 凭据（0531 600，别把密钥写进 settings）。

## 子代理与多模型（原生支持，不是插件才有）
- `dsh-tool-subagent` 接受 `{provider, model}` 子路由（`lib/types/model-selection.d.ts`）；设置项 `subagent-model-selection` 是 allow-list，授权哪些 provider/model 能被显式选中；内置 `list_subagent_models` 让主脑看到候选；UI 有子代理设置卡（模型候选 / maxDepth / maxActive）。
- 增强插件 `dsh-multi-model-orchestrator`：给每个模型写 strengths/weaknesses 备注，主脑据此派活。
- 分工范式：**主脑用 flash 调度，子代理按活挑 pro / 其他厂商**。

## 沙箱（实测：有效）
- Linux 上用 bwrap/Landlock；默认权限模式 `workspace-write`（`DSH_PERMISSION_MODE` 可覆盖）。
- 实测：工作区外写文件被拦（`Permission denied` + `[sandbox: file access denied under workspace-write mode]`），**独立核对该文件确实不存在**（用文件查找工具，不要只信 agent 自报）。
- 日志出现 `landlock-run: partial enforcement (older Landlock ABI)` **不代表拦截失效**（只表示接口版本老），以实测结果为准。
- 边界测试有额外信息量：系统提示「可申请提权」时，**主动拒绍无法理据提权的 agent 才适合托管生产资产与凭据**。

## 技能契约（与 Hermes 兼容 —— 迁移关键）
- 契约 = Anthropic Agent Skills：`<技能名>/SKILL.md` + YAML frontmatter（至少 `name`、`description`），目录名 kebab-case。
- 发现根按优先级（数字小优先）：项目 `/.dsh/skills`(100) < 项目 `/.agents/skills`(200) < `Config.customSkillDirs`(300) < `~/.dsh/skills`(400) < **`~/.agents/skills`(500)** < bundled(600)。
- `~/.agents/skills` 是**跨 agent 公共根**（Claude Code 等同读），同时用两个 agent 时性价比最高。
- **递归发现不生效**：只认发现根下的直接子目录与扁平 md，藏进二级子目录就找不到。
- ⚠️ **所以「把技能目录软链进 `~/.agents/skills`」这句是错的，实施时会漏一大半**：Hermes 技能库本身就是**混合结构**——同级的 `skills/<名>/SKILL.md` 与分类层的 `skills/<分类>/<名>/SKILL.md` 并存（实测全库 139 个，一级仅 36、二级 56）。直接把技能根目录链过去，二级的全部扫不到。正确做法是**扁平化软链**，逐个把真实技能目录链成发现根下的一级入口：
  ```bash
  for s in <技能名...>; do
    p=$(find -L ~/.hermes/skills -maxdepth 3 -type d -name "$s" | head -1)
    [ -n "$p" ] && ln -sfn "$p" ~/.agents/skills/"$s"
  done
  ```
  `find` 必须带 `-L`（相当一部分技能本身就是软链，`-type d` 不跟随会漏掉）。挂完**让 dsh 自己列出可见技能做验收**——它能读到正文与 `references/` 子目录才算真生效。
- **挂载前先清点引用断口**：技能正文常点名「配合 X 使用」，而 X 可能并不在库里（或已被改名/已被取代）。软链前扫一遍引用，把断口记下来；这些多是「建议配合」而非硬依赖，不致命但影响执行质量。
- 技能可打包成插件分发（`dsh plugin add`），但那会把技能绑死到 dsh、放弃跨 agent 复用——稳定不动的私人技能做插件是过度工程。

## 状态与风险
- developer preview，官方明说会有兼容性破坏变更：锁版本、升级前读 changelog。
- 配置有学习成本（要理解 Cordis 插件机制与 profile/组合包概念）。

## 与本团队的适配结论（已定）
- **不搬迁**：dsh 无 IM 网关（老板用不了手机）、无跨会话记忆注入、无 cron、无多 profile 团队编制——按 SKILL.md 第 0 步走「双栈并行」。
- **技能可零改动共享**：技能**正文**零改动，但入口要**扁平化软链**进 `~/.agents/skills`（见上），新技能两边都能用。
- 服务器侧按需启动、不写 systemd；本地设备先装一台试，别三台齐上（配置/key/技能同步都要各自维护）。

## 操作坑（实测）
- `pkill -f "dsh web"` **会把执行它的 shell 自己也杀了**（命令行字符串被自己匹配上，SIGTERM 自杀）→ 用 `pgrep -af "[d]sh"` 拿 PID 再 kill。
- 用浏览器工具访问本机端口会被安全策略拦（private/internal address）→ 改用本机 headless Chrome 截图验收：`google-chrome --headless=new --no-sandbox --disable-gpu --user-data-dir=/tmp/cs --window-size=1600,1000 --screenshot=/tmp/x.png "http://127.0.0.1:3080/?token=..."`。
- `dsh --dump-config` 看不到插件不等于插件不存在：profile 的 bundle 在 `profiles/<name>/package.json` 的 `dsh.profile.bundles`，直接 `find <dsh>/node_modules/@deepseek-ai -iname "*subagent*"` 更可靠。

## 验收（装完必做）
1. `ss -lntp | grep 3080` —— 确认监听且只在回环。
2. `dsh headless "写个脚本算 X 并运行，报实际输出"` —— 端到端真实任务。
3. **独立复核它报的数字**（自己再算一遍）——子代理的报告是自述，不是已验证的事实。
4. **越界写测试验沙箱**（见上），agent 自报与独立核对两处都对才算过。
