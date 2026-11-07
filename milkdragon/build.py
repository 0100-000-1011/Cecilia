#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 content.md 编译成 content.js（页面真正读的是 content.js）。

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
"""

import json
import os
import re
import sys

try:
    import markdown
except ImportError:
    sys.exit("缺少依赖：python3 -m pip install markdown")

HERE = os.path.dirname(os.path.abspath(__file__))
MD_PATH = os.path.join(HERE, "content.md")
OUT_PATH = os.path.join(HERE, "content.js")


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(
        ">", "&gt;").replace('"', "&quot;")


# ---------- 头部配置 ----------
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


# ---------- 音频容器 ::: audio ----------
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


# ---------- 图片：单张→figure，连续多张→gallery ----------
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


# ---------- 音频占位符还原 ----------
def restore_audio(html, groups):
    def repl(m):
        items = groups[int(m.group(1))]
        payload = json.dumps(items, ensure_ascii=False).replace("'", "&#39;")
        return "<div class=\"block-audio\" data-items='%s'></div>" % payload

    return re.sub(r"<p>\s*MDAUDIO(\d+)\s*</p>", repl, html)


def main():
    if not os.path.exists(MD_PATH):
        sys.exit("找不到 content.md")

    raw = open(MD_PATH, encoding="utf-8").read()
    meta, body = split_front_matter(raw)
    body, audio_groups = extract_audio(body)

    html = markdown.markdown(body, extensions=["extra", "sane_lists"])

    # 外链新窗口打开
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

    # 资源存在性检查
    refs = sorted(set(re.findall(r'src="(assets/[^"]+)"', html)
                      + ([page["hero"]["cover"]] if page["hero"]["cover"] else [])
                      + [i["src"] for g in audio_groups for i in g]))
    missing = [f for f in refs if not os.path.exists(os.path.join(HERE, f))]
    for f in missing:
        print("⚠️  缺少文件: %s" % f)

    banner = ("/* 本文件由 build.py 自动生成——要改内容请编辑 content.md，"
              "然后运行 python3 build.py（或 ./deploy.sh） */\n")
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(banner + "window.PAGE = "
                + json.dumps(page, ensure_ascii=False, indent=2) + ";\n")

    n_img = len(re.findall(r"block-(?:figure|gallery)", html))
    print("✓ content.js 已生成：%d 个音频、%d 处图片/图组、正文 %d 字符"
          % (sum(len(g) for g in audio_groups), n_img, len(body)))
    if missing:
        print("⚠️  有 %d 个引用的文件不存在，记得放进 assets/ 再推送" % len(missing))


if __name__ == "__main__":
    main()
