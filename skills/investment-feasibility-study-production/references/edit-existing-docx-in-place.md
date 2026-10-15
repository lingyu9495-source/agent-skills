# 就地修订已有 Word 报告：注入「编制说明」/改封面（python-docx 实测配方，2026-09-07）

> 场景：给客户/用户交付一份修订版报告，要在**现成可研 docx 上就地改**——改封面标题、在正文头注入一段「编制说明」、保留全文原有格式。不是从零重建，所以核心是**不破坏原有段落/表格格式**。

## 两步配方

### 1) 复制原文件（不破坏原件）
```python
import shutil
src = r"...源.docx"
out = r".../XX项目可行性研究报告.docx"   # 客户版用干净文件名
shutil.copy(src, out)
```

### 2) 改封面版本字样（清空该 run 文本）
```python
import docx
d = docx.Document(out)
for p in d.paragraphs:
    if p.text.strip() == "（报批稿）":
        for r in p.runs:
            r.text = ""          # 清空，不标版本；客户版不挂状态标签
        break
```

### 3) 在指定段落前「插入新段落」且复用原有格式
关键点：用 `insert_paragraph_before()` + **深拷贝模板段落的 pPr（段落格式）+ 首个 run 的 rPr（字体格式）**，这样插入的段落跟正文长得一模一样，不会格式怪。
```python
import copy
from docx.shared import Pt
from docx.oxml.ns import qn

paras = d.paragraphs
# 定位插入锚点（如 "第一卷 总报告"）
anchor = next(p for p in paras if p.text.strip() == "第一卷 总报告")
# 选一个模板段落（正文/标题）来借用格式
body_p = next(p for p in paras if p.text.strip().startswith("本项目为超大型海洋产业集群"))

def insert_para(before_p, text, template_p, size=11, bold=False):
    new_p = before_p.insert_paragraph_before()
    if template_p._p.pPr is not None:                       # 段落格式
        new_p._p.insert(0, copy.deepcopy(template_p._p.pPr))
    run = new_p.add_run(text)
    if template_p.runs:                                     # 字体格式
        tpl = template_p.runs[0]
        if tpl._r.rPr is not None:
            run._r.insert(0, copy.deepcopy(tpl._r.rPr))
    run.font.size = Pt(size); run.font.bold = bold
    run.font.name = '微软雅黑'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    return new_p
```

## ⚠️ 避坑
- **内部引号冲突**：Python 字符串里再写中文引号 `"待尽调"` 会报 `SyntaxError: invalid character` —— 改用**外层单引号**包字符串，内层用中文引号。
- **插入点顺序**：先插标题（编制说明，加粗大字号），再插空行，再逐段插正文。要保证「在锚点之前、按顺序出现」。
- **验证**：`d.save(out)` 后用 `docx.Document(out)` 重开，打印锚点前后几段确认顺序/无误。

## 这是内参版还是客户版？
先根据 `investment-feasibility-study-production` SKILL.md 的 9/9a/9b 铁律定版本属性——给客户的删干净（无评审痕迹、无版本标签），给用户自己的保留评审底稿。方向先定，再动手改。
