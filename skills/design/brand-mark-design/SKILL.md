---
name: brand-mark-design
slug: brand-mark-design
version: 1.0.0
description: "Use when 做 LOGO/头像/徽章/印章等图形标识. 先AI批量发散再收敛精修＋低饱和暖色系＋出图交付规范。"
author: AI 助手
license: MIT
metadata:
  hermes:
    tags: [设计, LOGO, 头像, 品牌标识, 文生图, 低饱和暖色系]
    related_skills: [design, model-matrix, deliverable-first-delivery]
---

# 品牌标识设计（LOGO／头像／徽章／印章）

## When to Use
- 给用户或团队成员做飞书/微信头像、LOGO、徽章、印章、图形符号
- 用户要"画个标识/头像"，且要求 **好看 / LOGO 级 / 有创意**
- 不做：海报排版、信息图、PPT（走 `design` / `baoyu-infographic` / `pptx`）

## 铁律一：先发散，别硬画（这个任务类最贵的一课）

**纯手工用 PIL 画几何图形，天花板就是"图标级"。** 反复调十几轮，也只是从"火柴人"变成"规整图标"，永远到不了"作品级"——手工矢量画不出 AI 那种线条流畅度、光影与材质感。

正确顺序：

1. **写 6–10 个不同意象的 prompt，用免费文生图批量发散**（约 8–12s/张，零成本）
2. **看图收敛**：从二三十张里挑 3–6 张有潜力的
3. **围绕优选方向再发散一轮**（改 prompt 细化造型／材质／底色）
4. **最后才动 PIL 做精修**：去水印、裁圆、统一色调、出全套尺寸

PIL 的正确角色是**后期加工**，不是从零造形。手工描轮廓只有在"必须在代码里精确控制几何"时才用，且要预期多轮迭代。

## 铁律二：只用免费模型

- 文生图固定走 **智谱 `cogview-3-flash`**（免费）；端点与可跑代码见技能 `model-matrix` 的「免费文生图通道」一节
- 禁用：阿里百炼 `qwen-image` 系列（计费）、智谱 `cogview-4`（付费）
- 单张零成本 → **一个 prompt 一次跑 8 张不心疼，多跑才出好图**；不同方向各跑一批

## 铁律三：原创性（用户硬要求）

- 别做得像知名公司的标识（Claude 的放射星芒、OpenAI 的花结…）。用户会直接指出"不能太抄袭人家了吧"，且这是他的硬门槛
- **破解法：接入用户本地的文化母题**（花山岩画／铜鼓／喀斯特地貌／骆越图腾…）——天然不撞车，还自带出处和故事
- 交付时**讲清出处与设计逻辑**（为什么用这个形、这一层含义）：用户就是吃这一层

## 配色（用户钦定 · 低饱和暖色系）

| 角色 | 色值 | 说明 |
|---|---|---|
| 底 | 米白 `#FAF7F0` | **优于纯白**：纯白在浅色聊天窗口里会"糊成一片"，米白有微妙分界 |
| 主色 | 琥珀金 `#DF9C2A` | 唯一主色 |
| 辅色 | 咖啡 `#8C6A38` | 点缀 |

依据：低饱和暖色系更耐看、显质感——米白打底 + 琥珀金点缀，稳重不廉价。这个配色理由要在交付里点明。

## 出图与交付规范

1. **裁圆去水印**：文生图返回的图四角带「AI生成」合规角标 → 以图心为圆心裁圆（圆外填黑／透明），角标落在圆外即消失。飞书头像本就是圆形，天然契合
   - **更彻底的替代**：若成图是「图标居中、四周是纯背景」（APP 图标渲染图常见），直接**按颜色掩码 `(r>120)&(r-b>60)` 找非背景 bbox 裁掉背景**——水印落在背景上，会随裁切一并消失，比裁圆更干净
2. **出全套尺寸** 1024 / 512 / 240 / 112，并**必须验证 48px**——头像在聊天列表里就那么大，小尺寸糊掉的方案一律毙
3. **双输出**：发飞书聊天框（附图）+ 存档 `knowledge/05-设计资产/<主题>-<日期>/`
4. **给选择但给结论**：一次给 3–6 张精选对比图 + 明确主推（"我推这张，因为…"），不要甩一堆图让用户自己挑
5. **交付语气**：结论先行、中文、手机友好；每张图配一句"为什么这样设计"；末尾带「弹药使用」行
6. **「APP logo 级别」是另一种交付形态**：用户可能指**圆角方形 App 图标**（上架用），不是圆形头像 → prompt 写「手机APP图标／iOS风格／圆角方形／扁平」，产出即可直接当 App 图标；转飞书头像时再裁圆
7. **位图天花板要提前讲**：AI 出的图标多带立体阴影，是**位图**，不能像矢量那样无损放大／改色；用户要「正式品牌资产」时，额外给一版**纯平无阴影**的更耐缩放

## 落地：把它真正换成飞书头像

设计完只是第一步。用户说「换成这个」时，全流程如下：

1. **换 token**：`POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal`，body `{"app_id":…,"app_secret":…}`。需使用本机自己的飞书应用凭据
2. **上传图标**：`POST https://open.feishu.cn/open-apis/application/v7/app_avatar/upload`，`multipart/form-data`，**字段名 `avatar`**（二进制）
3. **写入应用**：`PATCH https://open.feishu.cn/open-apis/application/v7/applications/<app_id>/base`，body `{"avatar": "<上一步返回值>"}`
4. **权限**：需 scope **`application:application:patch`**（「修改应用信息」）。缺权限报 `99991672`，报错里带开通链接；开通 + 发版流程见技能 `feishu-app-scope-bulk-grant`
5. **改完必须发版**才在线生效（权限 Added 但未发版＝白做）

⚠️ 改应用信息是**管理员级高危操作**：扫码／授权只能由用户本人完成，**绝不代填**（这是安全边界，不是流程障碍）。做法是：把二维码发给用户 + 一句「扫完我就全自动接管，余下我来做」。

## 工具与通道（实测可用）

- **文生图**：`POST https://open.bigmodel.cn/api/paas/v4/images/generations`，body `{"model":"cogview-3-flash","prompt":"…","size":"1024x1024"}`，返回 `data[0].url`（有效期数天，尽快下载落盘）
- **图标素材（矢量）**：iconify 国内直连 —— 先 `GET https://api.iconify.design/search?query=<kw>` 拿图标名，再 `GET https://api.iconify.design/<prefix>/<name>.svg`
- **SVG → 透明 PNG 取轮廓**：本机 Chromium
  `chrome --headless=new --no-sandbox --hide-scrollbars --window-size=1024,1024 --default-background-color=00000000 --screenshot=out.png file://page.html`
  （得到透明底 PNG，取 alpha 通道当 mask，即可套任意配色／渐变）
  取 mask 的兜底：若 alpha 全 255，改用亮度反相 `Image.eval(g, lambda x: 255-x)`
- **PIL 精修**：**超采样 3–4× 再 LANCZOS 缩回**，边缘才干净；金色金属渐变用逐行 `line` 画斜向渐变
- prompt 模板与风格词表见 `references/prompt-recipes.md`

## 坑（都踩过）

- **Wikimedia / commons 国内不可达**（SSL 握手超时）→ 找参考图改走百度图片（开浏览器看截图）、国内媒体站、iconify
- **中文媒体页的图片是相对路径**：`web_extract` 抓回的是文件名而非完整 URL，需自行拼接；**直接开浏览器截图更稳**
- **PIL `Image.paste(src, box, mask)` 要求 src 尺寸与 mask 完全一致**：贴图层要按 mask 的实际 `(w,h)` 生成，否则 `ValueError: images do not match`
- 手工描轮廓：**全曲线偏"圆钝"、全折线偏"方块"** → 用"曲线主体 + 关键处锐角（尖／眼／角）"混合；单一手法必然难看
- 用户说"参考 X 公司的风格"= 要**那种感觉**，不是复刻；直接复刻会被退回，并触发上面的原创性红线
- **不要因为连续几版没被认可就继续在同一个手工方向上猛调**——那是沉没成本；换到"AI 发散"这条路上，一轮就能超过手工十几轮

## 参考

- `references/prompt-recipes.md` —— 文生图 prompt 结构、风格词／配色词表、已验证的意象方向、迭代法
