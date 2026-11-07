#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把网址生成二维码，存到 assets/qr.png 和 assets/qr.svg。
网页会自动在页脚显示 qr.png，不需要改 content.js。

用法：
    python3 make_qr.py https://你的用户名.github.io/仓库名/
    python3 make_qr.py https://你的用户名.github.io/仓库名/ --dark "#1c1a17"

第一次运行前需要装依赖：
    python3 -m pip install -r requirements.txt
"""

import argparse
import os
import sys

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_Q
except ImportError:
    sys.exit("缺少依赖，先执行：python3 -m pip install -r requirements.txt")

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")


def main():
    ap = argparse.ArgumentParser(description="为网页生成二维码")
    ap.add_argument("url", help="要生成二维码的完整网址")
    ap.add_argument("--dark", default="#1c1a17", help="二维码颜色（默认近黑 #1c1a17）")
    ap.add_argument("--light", default="#ffffff", help="底色（默认白）")
    ap.add_argument("--box", type=int, default=12, help="每个模块的像素（默认 12）")
    ap.add_argument("--border", type=int, default=3, help="四周留白模块数（默认 3）")
    ap.add_argument("--name", default="qr", help="输出文件名（默认 qr）")
    args = ap.parse_args()

    url = args.url.strip()
    if not url.startswith(("http://", "https://")):
        sys.exit("网址要以 http:// 或 https:// 开头")

    os.makedirs(ASSETS, exist_ok=True)

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_Q,  # 25% 冗余，印小了或被压到也认得出
        box_size=args.box,
        border=args.border,
    )
    qr.add_data(url)
    qr.make(fit=True)

    png_path = os.path.join(ASSETS, args.name + ".png")
    svg_path = os.path.join(ASSETS, args.name + ".svg")

    img = qr.make_image(fill_color=args.dark, back_color=args.light)
    img.save(png_path)

    # 矢量版：直接按矩阵写 SVG，放大印刷不糊
    matrix = qr.get_matrix()  # 已包含 border
    n = len(matrix)
    path = "".join(
        "M%d,%dh1v1h-1z" % (x, y)
        for y, row in enumerate(matrix)
        for x, cell in enumerate(row) if cell
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %(n)d %(n)d" '
        'width="%(mm).1fmm" height="%(mm).1fmm" shape-rendering="crispEdges">'
        '<rect width="%(n)d" height="%(n)d" fill="%(light)s"/>'
        '<path d="%(path)s" fill="%(dark)s"/>'
        "</svg>\n" % {"n": n, "mm": n * 1.0, "light": args.light, "dark": args.dark, "path": path}
    )
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)

    print("\n" + "=" * 46)
    qr.print_ascii(invert=True)
    print("=" * 46)
    print("网址 : " + url)
    print("模块 : %d x %d" % (qr.modules_count, qr.modules_count))
    print("图片 : assets/%s.png" % args.name)
    print("矢量 : assets/%s.svg  （印刷用，放大不糊）" % args.name)
    print("\n把改动 push 到 GitHub，页脚就会显示这张二维码。")


if __name__ == "__main__":
    main()
