#!/usr/bin/env python3
"""技能包脱敏 + 审计（外发给外部智能体前跑）。

用法：
  python sanitize_skill_pack.py --dir <skills目录> [--dry-run]
  python sanitize_skill_pack.py --dir <skills目录> --extra-words words.txt

三件事：
  1) 改写：身份词 + 凭据/密钥/邮箱/内部路径 → 占位符
  2) 复扫：敏感模式报残留数（必须 0）
  3) 体检：frontmatter / 死链 / 图片 / 可用性分级

八类敏感（见 SKILL.md 第 3 步）：身份词、IM 凭据、密钥令牌、真实邮箱手机、
内部路径、主机名、客户项目名、旧组件名。
成员花名/品牌名/客户名因环境而异：改 DEFAULT_WORDS，或用 --extra-words 传词表
（每行 `原词\t替换词`，或只有原词则替换为空）。至少跑两轮，第二遍模式放更宽。
"""
import argparse
import os
import re

TEXTS = {'.md', '.txt', '.py', '.json', '.jsonl', '.yaml', '.yml', '.sh', '.csv',
         '.js', '.ts', '.html', '.toml', '.ini', '.cfg'}
IMG = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}

# 身份词：复合词必须排在单字之前（长词优先），每词单独列，不要用单字兜底
DEFAULT_WORDS = [
    ('主脑用户', '用户'),
    ('主脑', '顾问'),
    ('团队', '团队'),
    ('用户', '老板'),
    # 按环境补：成员花名 / 品牌名 / 旧产品名（客户与项目名建议走 --extra-words）
]

# 凭据 / 密钥 / 邮箱 / 内部路径（正则）
RES = [
    (re.compile(r'cli_[a-z0-9]{12,}'), '<APP_ID>'),
    (re.compile(r'oc_[a-z0-9]{20,}'), '<CHAT_ID>'),
    (re.compile(r'ou_[a-z0-9]{20,}'), '<OPEN_ID>'),
    (re.compile(r'om_[a-z0-9]{12,}'), '<MESSAGE_ID>'),
    (re.compile(r'on_[a-z0-9]{20,}'), '<OPEN_ID>'),
    (re.compile(r'sk-[A-Za-z0-9]{16,}'), '<API_KEY>'),
    (re.compile(r'Bearer\s+[A-Za-z0-9._-]{20,}'), 'Bearer <API_KEY>'),
    (re.compile(r'[A-Za-z0-9._%+-]+@(?!example\.com|company\.com|co\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}'), '<EMAIL>'),
    (re.compile(r'<HERMES_HOME>'), '/path/to/hermes'),
    (re.compile(r'/opt/知识库'), '/path/to/knowledge'),
    (re.compile(r'/root/'), '~/'),
    (re.compile(r'<VOLUME>'), '<本地数据目录>'),
    (re.compile(r'AppData/Local/hermes'), '<Hermes目录>'),
    (re.compile(r'AppData\\\\Local\\\\hermes'), '<Hermes目录>'),
    (re.compile(r'profiles/[a-z0-9][a-z0-9-]{2,}'), 'profiles/<profile>'),
]

# 复扫：替换后必须全部 0 命中
CHECK = [
    (re.compile(r'\b(cli_|oc_|ou_|om_|on_)[a-z0-9]{12,}'), 'IM 凭据'),
    (re.compile(r'sk-[A-Za-z0-9]{16,}|Bearer\s+[A-Za-z0-9._-]{20,}'), '密钥'),
    (re.compile(r'<HERMES_HOME>'), '内部路径'),
    (re.compile(r'[A-Za-z0-9._%+-]+@(?!example\.com|company\.com|co\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}'), '真实邮箱'),
]


def iter_texts(root):
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            if os.path.splitext(f)[1].lower() in TEXTS:
                yield os.path.join(dp, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True, help='skills 目录')
    ap.add_argument('--dry-run', action='store_true', help='只报不改')
    ap.add_argument('--extra-words', help='每行 原词[\\t替换词]，补成员/品牌/客户名')
    a = ap.parse_args()

    words = list(DEFAULT_WORDS)
    if a.extra_words:
        for line in open(a.extra_words, encoding='utf-8'):
            line = line.rstrip('\n')
            if not line.strip():
                continue
            w, _, r = line.partition('\t')
            words.append((w, r))
    # 长词优先：防短词先替换把复合词拆碎
    words.sort(key=lambda x: -len(x[0]))

    changed = 0
    for p in iter_texts(a.dir):
        try:
            t = open(p, encoding='utf-8', errors='ignore').read()
        except OSError:
            continue
        o = t
        for w, r in words:
            t = t.replace(w, r)
        for rx, r in RES:
            t = rx.sub(r, t)
        if t != o:
            changed += 1
            if not a.dry_run:
                open(p, 'w', encoding='utf-8').write(t)
    print(f"{'would change' if a.dry_run else 'changed'}: {changed} files")

    # ---- 复扫（必须 0）----
    for rx, label in CHECK:
        hits = sum(1 for p in iter_texts(a.dir)
                   if rx.search(open(p, encoding='utf-8', errors='ignore').read()))
        flag = 'OK' if hits == 0 else '!! 需重跑'
        print(f'residual [{label}]: {hits}  {flag}')

    # ---- 体检 ----
    skills = [d for d in sorted(os.listdir(a.dir)) if os.path.isdir(os.path.join(a.dir, d))]
    bad_fm, dead, with_scripts, imgs = [], [], [], []
    for name in skills:
        d = os.path.join(a.dir, name)
        if os.path.isdir(os.path.join(d, 'scripts')):
            with_scripts.append(name)
        sp = os.path.join(d, 'SKILL.md')
        if not os.path.isfile(sp):
            bad_fm.append(name + '(no SKILL.md)')
            continue
        head = open(sp, encoding='utf-8', errors='ignore').read()
        if not (re.search(r'^name\s*:', head, re.M) and re.search(r'^description\s*:', head, re.M)):
            bad_fm.append(name + '(bad frontmatter)')
        m = re.search(r'^name\s*:\s*(.+)$', head, re.M)
        if m and not m.group(1).strip().isascii():
            bad_fm.append(name + '(非 ASCII name)')
        for ref in re.findall(r'[\w\-./]+\.(?:md|py|sh|json|yaml|yml|csv)', head):
            if ('references/' in ref or 'scripts/' in ref or 'templates/' in ref) \
                    and not os.path.exists(os.path.join(d, ref)):
                dead.append(f'{name} -> {ref}')
    for dp, _dn, fn in os.walk(a.dir):
        for f in fn:
            if os.path.splitext(f)[1].lower() in IMG:
                imgs.append(os.path.join(dp, f))

    print(f'skills: {len(skills)}  | 开箱即用 {len(skills) - len(with_scripts)}'
          f'  | 需装包 {len(with_scripts)}')
    print('frontmatter issues:', bad_fm or 'none')
    print('dead links:', dead or 'none')
    print('images (必须 vision_analyze 逐张目视核验):', imgs or 'none')


if __name__ == '__main__':
    main()
