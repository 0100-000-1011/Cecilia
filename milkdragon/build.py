#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 content.md 编译成页面内容；若 keys.txt 里给本子页面设了密码，
则正文和所有图片/音频会用 AES-GCM 加密，云端只留密文。

用法：
    python3 build.py

content.md 结构：
    ---            ← 头部配置（可选，但建议写）
    title: 标题
    cover: assets/cover.jpg
    ...
    ---            ← 头部结束，下面是正文 Markdown

    正文（标准 Markdown）：
    - # ## ###     标题
    - **粗体** *斜体* `代码` [链接](https://...)
    - > 引文
    - - 列表 / 1. 列表
    - ---          分隔线
    - ![说明](assets/a.jpg "图注")   单张 → 大图+图注
    - 连续多行图片                    → 自动拼成网格
    - ::: audio ... :::             音频，每行：文件 | 标题 | 说明
    - 行尾 {居中}/{靠右}/{靠左}      该行对齐（也认 center/right/left/c/r/l）；
                                    双空格硬换行的段落里只管所在那一行
    - ::: center ... :::            多行内容整块对齐（也认 left/right）

图片放 HEIC 也可以：build 时会自动转成同名 .jpg（浏览器不认 HEIC），
并把 content.md 里的引用一起改过来。原 .HEIC 保留在本地。

微信表情：正文写 [微笑] [旺柴] [Doge] 等会内联显示微信自带表情，
图片在仓库主目录 shared/emoji/（各子页面共享，公开不加密），
新表情直接把 png 放进那个目录（文件名 = 表情名）即可。

加密（keys.txt 中 子页面名=密码 时自动启用）：
    - access.json     盐 + 迭代次数 + 校验哈希（公开，不含密码）
    - enc/page.enc    加密的整页内容与资源清单
    - enc/assets/*.enc 加密后的图片音频
    - 原始 content.md 与 assets 原件只留本地，自动加进 .gitignore 并移出 git 索引
"""

import base64
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import sys

try:
    import markdown
except ImportError:
    sys.exit("缺少依赖：python3 -m pip install markdown")

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    sys.exit("缺少依赖：python3 -m pip install cryptography")

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.path.basename(HERE)
ROOT = os.path.abspath(os.path.join(HERE, ".."))
MD_PATH = os.path.join(HERE, "content.md")
OUT_PATH = os.path.join(HERE, "content.js")
KEYS_PATH = os.path.join(ROOT, "keys.txt")
STATE_PATH = os.path.join(ROOT, ".keys-state.json")
GITIGNORE_PATH = os.path.join(ROOT, ".gitignore")

PBKDF2_ITERS = 150000
BLOCK_START = "# >>> protected (build.py auto-managed) <<<"
BLOCK_END = "# <<< protected <<<"


# ---------- 基础工具 ----------

def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(
        ">", "&gt;").replace('"', "&quot;")


def b64(b):
    return base64.b64encode(b).decode()


def cap_html(s):
    """图注支持 \n 换行（写成字面的 \n 即可），也支持微信表情 [Cry] [Blush]。"""
    return replace_emojis(esc(s).replace("\\n", "<br>"))


def sha256_hex(b):
    return hashlib.sha256(b).hexdigest()


def derive_key(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, PBKDF2_ITERS, dklen=32)


def seal(raw, plaintext):
    """AES-GCM 加密，输出 IV(12B) + 密文+Tag，与浏览器 WebCrypto 解密格式一致"""
    iv = os.urandom(12)
    return iv + AESGCM(raw).encrypt(iv, plaintext, None)


def unseal(raw, blob):
    return AESGCM(raw).decrypt(blob[:12], blob[12:], None)


def mime_of(path):
    if path.endswith(".m4a"):
        return "audio/mp4"
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


# ---------- 密钥文件 ----------

def read_keys():
    keys = {}
    if os.path.exists(KEYS_PATH):
        for line in open(KEYS_PATH, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip()
    return keys


def load_state():
    if os.path.exists(STATE_PATH):
        try:
            return json.load(open(STATE_PATH, encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------- gitignore 管理段 ----------

def write_gitignore(protected):
    lines = []
    if os.path.exists(GITIGNORE_PATH):
        lines = open(GITIGNORE_PATH, encoding="utf-8").read().splitlines()
    out, in_block = [], False
    for ln in lines:
        if ln.strip() == BLOCK_START:
            in_block = True
            continue
        if ln.strip() == BLOCK_END:
            in_block = False
            continue
        if not in_block:
            out.append(ln)

    if protected:
        block = [BLOCK_START,
                 "%s/content.md" % FOLDER,
                 "%s/content.local.js" % FOLDER,
                 "%s/assets/*" % FOLDER,
                 "!%s/assets/qr.png" % FOLDER,
                 "!%s/assets/favicon.png" % FOLDER,
                 "!%s/assets/dino.png" % FOLDER,
                 BLOCK_END]
        out = [l for l in out if l.strip()] + [""] + block + [""]
    with open(GITIGNORE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(out).rstrip() + "\n")


def git_untrack(paths):
    try:
        subprocess.run(
            ["git", "rm", "-r", "--cached", "--ignore-unmatch", "--quiet"] + paths,
            cwd=ROOT, capture_output=True, timeout=30)
    except Exception as e:
        print("⚠️  git 操作失败（不影响本地构建）: %s" % e)


# ---------- Markdown 编译 ----------

def split_front_matter(text):
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n?", text, re.S)
    meta = {}
    if not m:
        return meta, text
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, text[m.end():]


def extract_audio(text):
    groups = []

    def repl(m):
        items = []
        for line in m.group(1).strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split("|")]
            src = parts[0]
            items.append({
                "src": src,
                "title": parts[1] if len(parts) > 1 else os.path.basename(src),
                "desc": parts[2] if len(parts) > 2 else "",
            })
        groups.append(items)
        return "\n\nMDAUDIO%d\n\n" % (len(groups) - 1)

    text = re.sub(r":::\s*audio\s*\n(.*?)\n:::", repl, text, flags=re.S)
    return text, groups


HEIC_EXT = (".heic", ".heif")


def convert_heic(src, out):
    """HEIC/HEIF → JPG。除 Safari 外浏览器都不认 HEIC，直接引用会白图。"""
    import shutil
    args = None
    if shutil.which("sips"):
        args = ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82"]
        info = subprocess.run(["sips", "-g", "pixelWidth", src],
                              capture_output=True, text=True).stdout
        m = re.search(r"pixelWidth:\s*(\d+)", info)
        if m and int(m.group(1)) > 1600:
            args += ["--resampleWidth", "1600"]
        args += [src, "--out", out]
    elif shutil.which("magick"):
        args = ["magick", src, "-auto-orient", "-resize", "1600x>", "-quality", "82", out]
    if not args:
        sys.exit("转换 %s 失败：需要 macOS 自带的 sips 或 ImageMagick" % src)
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        sys.exit("转换失败: %s\n%s" % (src, (r.stderr or "").strip()))


def normalize_heic(raw):
    """把 assets/ 下所有 HEIC/HEIF 转成同名 .jpg，并把 content.md 里的引用改成 .jpg。"""
    assets_dir = os.path.join(HERE, "assets")
    if not os.path.isdir(assets_dir):
        return raw
    for dirpath, _dirs, files in os.walk(assets_dir):
        for name in files:
            stem, ext = os.path.splitext(name)
            if ext.lower() not in HEIC_EXT:
                continue
            src = os.path.join(dirpath, name)
            out = os.path.join(dirpath, stem + ".jpg")
            if not (os.path.exists(out)
                    and os.path.getmtime(out) >= os.path.getmtime(src)):
                convert_heic(src, out)
                print("🖼  HEIC → JPG: %s" % os.path.relpath(out, HERE).replace(os.sep, "/"))
            rel_src = os.path.relpath(src, HERE).replace(os.sep, "/")
            rel_out = os.path.relpath(out, HERE).replace(os.sep, "/")
            raw = re.sub(re.escape(rel_src), rel_out, raw, flags=re.I)
    return raw


IMG_ATTRS = re.compile(r'([\w-]+)="([^"]*)"')


# ---------- 对齐 ----------
# 单行：行尾写 {居中} / {靠右} / {靠左}（也认 {center} {right} {left} {c} {r} {l}）
# 多行：::: center … ::: 容器

ALIGN_CLASS = {
    "左": "al-left", "靠左": "al-left", "left": "al-left", "l": "al-left",
    "中": "al-center", "居中": "al-center", "center": "al-center", "c": "al-center",
    "右": "al-right", "靠右": "al-right", "right": "al-right", "r": "al-right",
}

# 只认行尾，避免把正文中间的 {xxx} 吃掉；末尾的空格要留住（双空格 = 硬换行）
ALIGN_TOKEN = re.compile(
    r"[ \t]*\{[ \t]*(左|靠左|中|居中|右|靠右|left|center|right|l|c|r)[ \t]*\}([ \t]*)$",
    re.I)

ALIGN_MARK = '<span class="al-end" data-al="%s"></span>'
LINE_MARK = re.compile(r'<span class="al-end" data-al="(al-[a-z]+)"></span>[ \t]*$')


def inject_align_marks(text):
    """行尾的 {居中} 之类的标记换成隐藏 span，留给 Markdown 之后的阶段识别。"""
    out, fence = [], None
    for line in text.splitlines():
        s = line.lstrip()
        if s.startswith("```") or s.startswith("~~~"):
            fence = None if fence else s[:3]
            out.append(line)
            continue
        if not fence:
            m = ALIGN_TOKEN.search(line)
            if m:
                cls = ALIGN_CLASS[m.group(1).lower()]
                # 标记放在行尾空格之前，双空格的硬换行才不会被吃掉
                line = line[:m.start()] + ALIGN_MARK % cls + m.group(2)
        out.append(line)
    return "\n".join(out)


def apply_linewise(html, tag):
    """块里用了双空格/反斜杠换行时，标记只管它所在的那一行。

    把 <p>a<br>b<mark>…</p> 拆成若干 block 级 span，标记行单独对齐，
    其余行保持左对齐。
    """
    pat = re.compile(r"<%s(?=[\s>])([^>]*)>((?:(?!</%s>)[\s\S])*?)</%s>"
                     % (tag, tag, tag))

    def repl(m):
        attrs, inner = m.group(1), m.group(2)
        if "<br" not in inner:
            return m.group(0)
        segs = re.split(r"<br\s*/?>", inner)
        if not any(LINE_MARK.search(s) for s in segs):
            return m.group(0)
        parts = []
        for seg in segs:
            mm = LINE_MARK.search(seg)
            cls = mm.group(1) if mm else ""
            seg = seg[:mm.start()] if mm else seg
            parts.append('<span class="%s">%s</span>'
                         % (("al-line " + cls).strip(), seg.strip()))
        return "<%s%s>%s</%s>" % (tag, attrs, "".join(parts), tag)

    return pat.sub(repl, html)


def apply_align(html):
    """把带标记的块元素换成带 al-* 类，并清掉标记。"""
    html = apply_linewise(html, "p")
    html = apply_linewise(html, "li")

    tags = ["p", "li", "blockquote"] + ["h%d" % i for i in range(1, 7)]
    for tag in tags:
        pat = re.compile(
            r"<%s(?=[\s>])([^>]*)>((?:(?!</%s>)[\s\S])*?)"
            r'<span class="al-end" data-al="(al-[a-z]+)"></span>\s*</%s>'
            % (tag, tag, tag))

        def repl(m, tag=tag):
            attrs, inner, cls = m.group(1), m.group(2), m.group(3)
            if 'class="' in attrs:
                attrs = attrs.replace('class="', 'class="%s ' % cls, 1)
            else:
                attrs += ' class="%s"' % cls
            return "<%s%s>%s</%s>" % (tag, attrs, inner, tag)

        html = pat.sub(repl, html)
    # 落单的标记（比如写在表格/代码里）直接丢掉
    return re.sub(r'<span class="al-end"[^>]*></span>', "", html)


def extract_align_blocks(text):
    """::: center / ::: right / ::: left 多行容器。"""
    groups = []

    def repl(m):
        name = m.group(1).strip().lower()
        cls = ALIGN_CLASS.get(name)
        if not cls:
            return m.group(0)
        groups.append((cls, m.group(2)))
        return "\n\nMDALIGN%d\n\n" % (len(groups) - 1)

    text = re.sub(r":::[ \t]*([A-Za-z\u4e00-\u9fff]+)[ \t]*\r?\n([\s\S]*?)\r?\n:::", repl, text)
    return text, groups


def restore_align(html, groups):
    def repl(m):
        cls, inner = groups[int(m.group(1))]
        body = render_md(inner)
        return '<div class="align-block %s">%s</div>' % (cls, body)

    return re.sub(r"<p>\s*MDALIGN(\d+)\s*</p>", repl, html)


def render_md(text):
    """Markdown → HTML，顺带处理对齐标记和图片排版。"""
    html = markdown.markdown(inject_align_marks(text),
                             extensions=["extra", "sane_lists"])
    html = apply_align(html)
    html = transform_images(html)
    html = replace_emojis(html)
    return html


# ---------- 微信表情 ----------
# 共享资源放在仓库主目录 shared/emoji/（各子页面通用，公开不加密）
# 正文里写 [微笑] [旺柴] 就会内联显示；别名见 EMOJI_ALIASES

EMOJI_SRC = "../shared/emoji"   # HTML 里的引用路径（相对子页面）
EMOJI_LOCAL = os.path.join(ROOT, "shared", "emoji")   # 本地磁盘位置

# 别名：微信官方英文短代码（wxNew 2021 全集，含全角变体）+ 手写别名 + QQ 拼音简码
EMOJI_ALIASES = {
    # 官方英文短代码（wxNew 2021 全集）
    "smile": "微笑", "grimace": "撇嘴", "drool": "色", "scowl": "发呆",
    "coolguy": "得意", "sob": "流泪", "shy": "害羞", "silent": "闭嘴",
    "sleep": "睡", "cry": "大哭", "awkward": "尴尬", "angry": "发怒",
    "tongue": "调皮", "grin": "呲牙", "surprise": "惊讶", "frown": "难过",
    "blush": "囧", "scream": "抓狂", "puke": "吐", "chuckle": "偷笑",
    "joyful": "愉快", "slight": "白眼", "smug": "傲慢", "drowsy": "困",
    "panic": "惊恐", "大笑": "憨笑", "laugh": "憨笑", "commando": "悠闲",
    "scold": "咒骂", "shocked": "疑问", "shhh": "嘘", "dizzy": "晕",
    "toasted": "衰", "skull": "骷髅", "hammer": "敲打", "bye": "再见",
    "speechless": "擦汗", "nosepick": "抠鼻", "clap": "鼓掌", "trick": "坏笑",
    "bah!l": "左哼哼", "bah! l": "左哼哼", "bah！l": "左哼哼", "bah！ l": "左哼哼", "bah!r": "右哼哼", "bah! r": "右哼哼", "bah！r": "右哼哼", "bah！ r": "右哼哼",
    "pooh-pooh": "鄙视", "shrunken": "委屈", "tearingup": "快哭了", "sly": "阴险",
    "kiss": "亲亲", "whimper": "可怜", "sick": "生病", "flushed": "脸红",
    "lol": "破涕为笑", "terror": "恐惧", "letdown": "失望", "duh": "无语",
    "hey": "嘿哈", "facepalm": "捂脸", "smirk": "奸笑", "smart": "机智",
    "concerned": "皱眉", "yeah!": "耶", "onlooker": "吃瓜", "goforit": "加油",
    "sweats": "汗", "omg": "天啊", "respect": "社会社会", "doge": "旺柴",
    "noprob": "好的", "mybad": "打脸", "wow": "哇", "boring": "翻白眼",
    "awesome": "666", "letmesee": "让我看看", "sigh": "叹气", "hurt": "苦涩",
    "broken": "裂开", "lips": "嘴唇", "heart": "爱心", "brokenheart": "心碎",
    "hug": "拥抱", "thumbsup": "强", "thumbsdown": "弱", "shake": "握手",
    "peace": "胜利", "salute": "抱拳", "beckon": "勾引", "fist": "拳头",
    "worship": "合十", "beer": "啤酒", "coffee": "咖啡", "cake": "蛋糕",
    "rose": "玫瑰", "wilt": "凋谢", "cleaver": "菜刀", "bomb": "炸弹",
    "poop": "便便", "moon": "月亮", "sun": "太阳", "party": "庆祝",
    "gift": "礼物", "packet": "红包", "rich": "發", "blessing": "福",
    "fireworks": "烟花", "firecracker": "爆竹", "pig": "猪头", "waddle": "跳跳",
    "tremble": "发抖", "twirl": "转圈", "keepfighting": "加油加油", "ruthless": "酷",
    "hungry": "饥饿", "sweat": "流汗", "determined": "奋斗", "tormented": "折磨",
    "shame": "糗大了", "yawn": "哈欠", "wrath": "吓", "watermelon": "西瓜",
    "basketball": "篮球", "pingpong": "乒乓", "rice": "饭", "lightning": "闪电",
    "dagger": "刀", "soccer": "足球", "ladybug": "瓢虫", "pinky": "差劲",
    "rockon": "爱你", "nuh-uh": "NO", "inlove": "爱情", "blowkiss": "飞吻",
    "aaagh!": "怄火", "kotow": "磕头", "dramatic": "回头", "surrender": "投降",
    "hooray": "激动", "meditate": "乱舞", "smooch": "献吻", "taichi l": "左太极",
    "taichi r": "右太极",
    # 手写别名
    "笑cry": "笑哭", "斜眼": "翻白眼", "捂脸哭": "破涕为笑", "happy": "高兴",
    "sad": "悲伤",
    # QQ 拼音简码（/jy 这套）
    "jy": "惊讶", "pz": "撇嘴", "se": "色", "fd": "发呆",
    "dy": "得意", "ll": "流泪", "hx": "害羞", "bz": "闭嘴",
    "shui": "睡", "dk": "大哭", "gg": "尴尬", "fn": "发怒",
    "tp": "调皮", "cy": "呲牙", "ng": "难过", "j": "囧",
    "zk": "抓狂", "t": "吐", "tx": "偷笑", "k": "愉快",
    "by": "白眼", "am": "傲慢", "kun": "困", "jk": "惊恐",
    "lh": "流汗", "hanx": "憨笑", "zm": "咒骂",
}

EMOJI_TOKEN = re.compile(r"\[([^\[\]<>]{1,12})\]")


def _emoji_file(name):
    key = name.strip()
    return EMOJI_ALIASES.get(key.lower()) or \
        (key if os.path.isfile(os.path.join(EMOJI_LOCAL, key + ".png")) else None)


def _emoji_repl(m):
    fname = _emoji_file(m.group(1))
    if not fname:
        return m.group(0)
    # alt 不带方括号：全局替换会扫整段 HTML，alt 里留着 [Cry] 会被再替换一层
    return ('<img class="wx-emoji" src="%s/%s.png" alt="%s">'
            % (EMOJI_SRC, fname, esc(m.group(1))))


def replace_emojis(html):
    """把正文里的 [微笑] 之类换成内联表情图；代码块里不动。"""
    parts = re.split(r"(<pre[\s\S]*?</pre>|<code[\s\S]*?</code>)", html)
    for i in range(0, len(parts), 2):   # 偶数段是普通文本
        parts[i] = EMOJI_TOKEN.sub(_emoji_repl, parts[i])
    return "".join(parts)


def img_attrs(tag):
    return dict(IMG_ATTRS.findall(tag))


def transform_images(html):
    """单张图片段落 → 大图；连续多张图片段落（中间只隔空行）→ 同一个网格，
    空行处另起一排（gal-start），格子大小不变。"""
    para = re.compile(r"<p(?=[\s>])([^>]*)>\s*((?:<img\s[^>]*>\s*)+)</p>")
    blocks = []   # [start, end, [(段落属性, [img 标签])]]

    for m in para.finditer(html):
        attrs = m.group(1)
        imgs = re.findall(r"<img\s[^>]*>", m.group(2))
        if blocks and not html[blocks[-1][1]:m.start()].strip():
            blocks[-1][1] = m.end()
            blocks[-1][2].append((attrs, imgs))
        else:
            blocks.append([m.start(), m.end(), [(attrs, imgs)]])

    out, last = [], 0
    for start, end, paras in blocks:
        out.append(html[last:start])
        infos = [img_attrs(t) for _, imgs in paras for t in imgs]
        # 段落上的对齐类（al-*）要带到 figure/gallery 上，否则换标签就丢了
        extra = ""
        for attrs, _ in paras:
            cm = re.search(r'class="([^"]*)"', attrs)
            if cm:
                extra = " " + cm.group(1)
                break

        if len(infos) == 1:
            i = infos[0]
            src, cap = i.get("src", ""), i.get("title", "")
            fig = ('<figure class="block-figure%s">'
                   '<a href="%s" data-full="%s" data-cap="%s">'
                   '<img src="%s" alt="%s" loading="lazy" decoding="async"></a>'
                   % (extra, esc(src), esc(src), esc(cap_html(cap)), esc(src), esc(i.get("alt", ""))))
            if cap:
                fig += "<figcaption>%s</figcaption>" % cap_html(cap)
            fig += "</figure>"
            out.append(fig)
        else:
            # 有空行分段（len(paras) > 1）→ has-break：按排排版，排宽由该排张数决定
            gcls = "block-gallery" + (" has-break" if len(paras) > 1 else "")
            g = '<div class="%s%s">' % (gcls, extra)
            idx = 0
            for p, (_, imgs) in enumerate(paras):
                for k in range(len(imgs)):
                    i = infos[idx]
                    idx += 1
                    src, cap = i.get("src", ""), i.get("title", "") or i.get("alt", "")
                    cls = ""
                    if len(paras) > 1:
                        if len(imgs) == 1:
                            # 该排只有一张 → 通栏（不留右侧空位）
                            cls = "gal-solo" if not p else "gal-start gal-solo"
                        else:
                            if k == 0 and p:
                                cls = "gal-start"           # 每排第一张：另起一排
                            if len(imgs) == 2:
                                cls += (" " if cls else "") + "gal-r2"   # 该排两张 → 各占半行
                    g += ('<a%s href="%s" data-full="%s" data-cap="%s">'
                          '<img src="%s" alt="%s" loading="lazy" decoding="async"></a>'
                          % (' class="%s"' % cls if cls else "",
                             esc(src), esc(src), esc(cap_html(cap)), esc(src), esc(i.get("alt", ""))))
            g += "</div>"
            out.append(g)
        last = end

    out.append(html[last:])
    return "".join(out)


def restore_audio(html, groups):
    def repl(m):
        items = groups[int(m.group(1))]
        payload = json.dumps(items, ensure_ascii=False).replace("'", "&#39;")
        return "<div class=\"block-audio\" data-items='%s'></div>" % payload

    return re.sub(r"<p>\s*MDAUDIO(\d+)\s*</p>", repl, html)


def compile_page():
    if not os.path.exists(MD_PATH):
        sys.exit("找不到 content.md")

    raw = open(MD_PATH, encoding="utf-8").read()
    fixed = normalize_heic(raw)
    if fixed != raw:
        open(MD_PATH, "w", encoding="utf-8").write(fixed)
        print("✎ content.md 里的 HEIC 引用已改写为 JPG")
        raw = fixed
    meta, body = split_front_matter(raw)
    body, audio_groups = extract_audio(body)
    body, align_groups = extract_align_blocks(body)

    html = render_md(body)
    html = restore_align(html, align_groups)
    html = restore_audio(html, audio_groups)
    html = re.sub(r'<a href="(https?:[^"]*)"',
                  r'<a href="\1" target="_blank" rel="noopener"', html)

    page = {
        "siteTitle": meta.get("title", "我的页面"),
        "description": meta.get("description", ""),
        "hero": {
            "cover": meta.get("cover", ""),
            # 封面文案支持微信表情（render.js 用 innerHTML 渲染）
            "kicker": replace_emojis(meta.get("kicker", "")),
            "title": meta.get("title", ""),
            "subtitle": replace_emojis(meta.get("subtitle", "").replace("\\n", "\n")),
            "meta": replace_emojis(meta.get("meta", "")),
        },
        "html": html,
        "footer": {
            "note": replace_emojis(meta.get("footer_note", "")),
            "qr": "assets/qr.png",
        },
    }

    refs = sorted(set(
        re.findall(r'src="(assets/[^"]+)"', html)
        + [i["src"] for g in audio_groups for i in g]
        + ([page["hero"]["cover"]] if page["hero"]["cover"] else [])))
    # qr.png 是公开的二维码；../ 开头的是主目录共享资源（如微信表情），都不加密
    refs = [r for r in refs if r != "assets/qr.png" and not r.startswith("../")]

    missing = [f for f in refs if not os.path.exists(os.path.join(HERE, f))]
    for f in missing:
        print("⚠️  缺少文件: %s" % f)

    return page, refs, missing


# ---------- 加密构建 ----------

def build_protected(page, refs):
    pw = read_keys().get(FOLDER, "").strip()
    state = load_state()
    st = state.get(FOLDER, {})
    pw_fingerprint = sha256_hex(pw.encode("utf-8"))

    # 密码没变就沿用旧盐，保住已登录设备的缓存；改密码才换盐
    if st.get("salt") and st.get("pw") == pw_fingerprint:
        salt = base64.b64decode(st["salt"])
    else:
        salt = os.urandom(16)
        print("… 密码有变化，生成新盐并重新加密全部资源")

    raw = derive_key(pw, salt)
    verifier = sha256_hex(raw)

    enc_dir = os.path.join(HERE, "enc")
    os.makedirs(enc_dir, exist_ok=True)

    # 资源 → enc/
    manifest = []
    for f in refs:
        data = open(os.path.join(HERE, f), "rb").read()
        enc_rel = os.path.join("enc", f + ".enc").replace(os.sep, "/")
        enc_path = os.path.join(HERE, enc_rel)
        os.makedirs(os.path.dirname(enc_path), exist_ok=True)
        with open(enc_path, "wb") as fh:
            fh.write(seal(raw, data))
        manifest.append({"p": f, "f": enc_rel, "t": mime_of(f)})

    # 清掉不再被引用的旧密文（比如把 .HEIC 换成 .jpg 之后留下的 .HEIC.enc）
    keep = {m["f"] for m in manifest}
    for dp, _dns, fns in os.walk(enc_dir):
        for fn in fns:
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, HERE).replace(os.sep, "/")
            if rel == "enc/page.enc" or rel in keep:
                continue
            os.remove(p)
            print("🧹 删除过期密文: %s" % rel)

    # 本地明文副本：双击 index.html（file://）时直接显示，不走密码。
    # 只留在本地——gitignore 里已排除，永远不会上传
    with open(os.path.join(HERE, "content.local.js"), "w", encoding="utf-8") as f:
        f.write("/* 本地明文副本（build.py 自动生成，不上传云端）——"
                "改内容请编辑 content.md 后重新 build */\nwindow.PAGE = "
                + json.dumps(page, ensure_ascii=False, indent=2) + ";\n")

    # 整页（含 manifest）→ enc/page.enc
    page["manifest"] = manifest
    page_blob = json.dumps(page, ensure_ascii=False).encode("utf-8")
    with open(os.path.join(enc_dir, "page.enc"), "wb") as fh:
        fh.write(seal(raw, page_blob))

    # access.json：只有盐/迭代次数/校验哈希，不含密码
    access = {"protected": True, "salt": b64(salt), "iter": PBKDF2_ITERS,
              "verifier": verifier}
    with open(os.path.join(HERE, "access.json"), "w", encoding="utf-8") as f:
        json.dump(access, f, ensure_ascii=False)

    # content.js 只留锁标记，不含任何内容
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("/* 已加密：内容在 enc/page.enc，此文件不含明文 */\n"
                "window.PAGE = { locked: true };\n")

    # 自检：用派生密钥把整页和第一个资源解回来
    unseal(raw, open(os.path.join(enc_dir, "page.enc"), "rb").read())
    if manifest:
        unseal(raw, open(os.path.join(HERE, manifest[0]["f"]), "rb").read())

    st.update({"salt": b64(salt), "pw": pw_fingerprint})
    state[FOLDER] = st
    save_state(state)

    write_gitignore(protected=True)
    git_untrack([FOLDER + "/content.md", FOLDER + "/assets"])

    n = sum(os.path.getsize(os.path.join(dp, fn)) for dp, _, fns in os.walk(enc_dir)
            for fn in fns)
    print("🔒 已加密：%d 个资源 + 整页内容 → enc/（密文共 %.1f KB）"
          % (len(manifest), n / 1024))
    print("🔒 content.md 与 assets 原件已从 git 索引移除，只保留在本地")


def build_public(page, missing):
    import shutil
    enc_dir = os.path.join(HERE, "enc")
    removed = []
    if os.path.isdir(enc_dir):
        shutil.rmtree(enc_dir)
        removed.append("enc/")
    if os.path.exists(os.path.join(HERE, "access.json")):
        os.remove(os.path.join(HERE, "access.json"))
        removed.append("access.json")

    banner = ("/* 本文件由 build.py 自动生成——要改内容请编辑 content.md，"
              "然后运行 python3 build.py（或 ./deploy.sh） */\n")
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(banner + "window.PAGE = "
                + json.dumps(page, ensure_ascii=False, indent=2) + ";\n")

    write_gitignore(protected=False)

    n_img = len(re.findall(r"block-(?:figure|gallery)", page["html"]))
    print("✓ 公开模式：content.js 已生成（%d 处图组/大图、正文 %d 字符）"
          % (n_img, len(page["html"])))
    if removed:
        print("✓ 已清理旧加密产物: %s" % ", ".join(removed))
    if missing:
        print("⚠️  有 %d 个引用的文件不存在，记得放进 assets/ 再推送" % len(missing))


def main():
    page, refs, missing = compile_page()
    if read_keys().get(FOLDER, "").strip():
        build_protected(page, refs)
    else:
        build_public(page, missing)


if __name__ == "__main__":
    main()
