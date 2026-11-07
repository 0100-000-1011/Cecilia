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
                 "%s/assets/*" % FOLDER,
                 "!%s/assets/qr.png" % FOLDER,
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


IMG_ATTRS = re.compile(r'([\w-]+)="([^"]*)"')


def img_attrs(tag):
    return dict(IMG_ATTRS.findall(tag))


def transform_images(html):
    para = re.compile(r"<p>\s*((?:<img\s[^>]*>\s*)+)</p>")
    out, last = [], 0

    for m in para.finditer(html):
        out.append(html[last:m.start()])
        infos = [img_attrs(t) for t in re.findall(r"<img\s[^>]*>", m.group(1))]

        if len(infos) == 1:
            i = infos[0]
            src, cap = i.get("src", ""), i.get("title", "")
            fig = ('<figure class="block-figure">'
                   '<a href="%s" data-full="%s" data-cap="%s">'
                   '<img src="%s" alt="%s" loading="lazy" decoding="async"></a>'
                   % (esc(src), esc(src), esc(cap), esc(src), esc(i.get("alt", ""))))
            if cap:
                fig += "<figcaption>%s</figcaption>" % esc(cap)
            fig += "</figure>"
            out.append(fig)
        else:
            g = '<div class="block-gallery">'
            for i in infos:
                src, cap = i.get("src", ""), i.get("title", "") or i.get("alt", "")
                g += ('<a href="%s" data-full="%s" data-cap="%s">'
                      '<img src="%s" alt="%s" loading="lazy" decoding="async"></a>'
                      % (esc(src), esc(src), esc(cap), esc(src), esc(i.get("alt", ""))))
            g += "</div>"
            out.append(g)
        last = m.end()

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
    meta, body = split_front_matter(raw)
    body, audio_groups = extract_audio(body)

    html = markdown.markdown(body, extensions=["extra", "sane_lists"])
    html = re.sub(r'<a href="(https?:[^"]*)"',
                  r'<a href="\1" target="_blank" rel="noopener"', html)
    html = transform_images(html)
    html = restore_audio(html, audio_groups)

    page = {
        "siteTitle": meta.get("title", "我的页面"),
        "description": meta.get("description", ""),
        "hero": {
            "cover": meta.get("cover", ""),
            "kicker": meta.get("kicker", ""),
            "title": meta.get("title", ""),
            "subtitle": meta.get("subtitle", "").replace("\\n", "\n"),
            "meta": meta.get("meta", ""),
        },
        "html": html,
        "footer": {
            "note": meta.get("footer_note", ""),
            "qr": "assets/qr.png",
        },
    }

    refs = sorted(set(
        re.findall(r'src="(assets/[^"]+)"', html)
        + [i["src"] for g in audio_groups for i in g]
        + ([page["hero"]["cover"]] if page["hero"]["cover"] else [])))
    # qr.png 是公开的二维码，不加密
    refs = [r for r in refs if r != "assets/qr.png"]

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
