#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把网址生成二维码，存到 assets/qr.png 和 assets/qr.svg。

样式：琥珀黄圆角模块 + 奶油底，定位框为大圆角同心环（与参考图逐像素对齐）。
整个图是一次画出来的——直接按矩阵画圆角模块、颜色一次给上，
不需要“先出黑白图再染色、再覆盖定位框”那套绕路。

用法：
    python3 make_qr.py https://你的用户名.github.io/仓库名/
    python3 make_qr.py <网址> --dark "#ffc02e" --light "#fff9ec"

第一次运行前需要装依赖：
    python3 -m pip install -r requirements.txt
"""

import argparse
import math
import os
import sys

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_Q
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("缺少依赖，先执行：python3 -m pip install -r requirements.txt")

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

# ---- 与参考图对齐的几何参数（单位：模块） ----
RATIO = 0.95        # 数据模块自由角圆角 = RATIO * 0.5（0.5 = 正圆角）
R_OUT = 1.90        # 定位框外环圆角
R_HOLE = 1.15       # 定位框白圈圆角
R_IN = 0.65         # 定位框内芯圆角
SS = 4              # PNG 超采样倍数（先画 4 倍大再缩小，边缘平滑）
FINDER = 7          # 定位框尺寸（模块）


def finder_origins(n):
    """三个定位框的矩阵坐标原点"""
    return [(0, 0), (n - FINDER, 0), (0, n - FINDER)]


def _poly(x0, y0, s, r_tl, r_tr, r_br, r_bl, seg=18):
    """单模块轮廓：四角圆角半径可分别指定（0 = 直角）"""
    pts = []

    def arc(cx, cy, r, a0, a1):
        for i in range(seg + 1):
            a = a0 + (a1 - a0) * i / seg
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    if r_tl:
        arc(x0 + r_tl, y0 + r_tl, r_tl, math.pi, 1.5 * math.pi)
    else:
        pts.append((x0, y0))
    if r_tr:
        arc(x0 + s - r_tr, y0 + r_tr, r_tr, 1.5 * math.pi, 2 * math.pi)
    else:
        pts.append((x0 + s, y0))
    if r_br:
        arc(x0 + s - r_br, y0 + s - r_br, r_br, 0, 0.5 * math.pi)
    else:
        pts.append((x0 + s, y0 + s))
    if r_bl:
        arc(x0 + r_bl, y0 + s - r_bl, r_bl, 0.5 * math.pi, math.pi)
    else:
        pts.append((x0, y0 + s))
    return pts


def render_png(matrix, box, dark, light, border):
    """一次成图：圆角数据模块 + 大圆角定位框，颜色直接画上去"""
    n = len(matrix)                     # 含 border
    inner = n - 2 * border
    size = n * box
    big = size * SS

    img = Image.new("RGB", (big, big), light)
    d = ImageDraw.Draw(img)

    fi = set()
    for ox, oy in finder_origins(inner):
        for yy in range(FINDER):
            for xx in range(FINDER):
                fi.add((border + ox + xx, border + oy + yy))

    dark_at = lambda x, y: 0 <= x < n and 0 <= y < n and matrix[y][x]
    r_free = RATIO * 0.5 * box * SS

    for y in range(border, n - border):
        for x in range(border, n - border):
            if not matrix[y][x] or (x, y) in fi:
                continue
            up, dn = dark_at(x, y - 1), dark_at(x, y + 1)
            lf, rt = dark_at(x - 1, y), dark_at(x + 1, y)
            d.polygon(_poly(
                x * box * SS, y * box * SS, box * SS,
                r_free if (not up and not lf) else 0,
                r_free if (not up and not rt) else 0,
                r_free if (not dn and not rt) else 0,
                r_free if (not dn and not lf) else 0,
            ), fill=dark)

    f = FINDER * box * SS
    for ox, oy in finder_origins(inner):
        x0, y0 = (border + ox) * box * SS, (border + oy) * box * SS
        d.rounded_rectangle([x0, y0, x0 + f, y0 + f], radius=R_OUT * box * SS, fill=dark)
        d.rounded_rectangle([x0 + box * SS, y0 + box * SS, x0 + f - box * SS, y0 + f - box * SS],
                            radius=R_HOLE * box * SS, fill=light)
        d.rounded_rectangle([x0 + 2 * box * SS, y0 + 2 * box * SS,
                             x0 + f - 2 * box * SS, y0 + f - 2 * box * SS],
                            radius=R_IN * box * SS, fill=dark)

    return img.resize((size, size), Image.LANCZOS)


def cell_path(x, y, r_tl, r_tr, r_br, r_bl):
    """单模块 SVG 路径；四角半径可分别指定（0 = 直角）"""
    d = "M%.3f,%.3f" % (x + r_tl, y)
    d += "H%.3f" % (x + 1 - r_tr)
    if r_tr:
        d += "A%.3f,%.3f 0 0 1 %.3f,%.3f" % (r_tr, r_tr, x + 1, y + r_tr)
    d += "V%.3f" % (y + 1 - r_br)
    if r_br:
        d += "A%.3f,%.3f 0 0 1 %.3f,%.3f" % (r_br, r_br, x + 1 - r_br, y + 1)
    d += "H%.3f" % (x + r_bl)
    if r_bl:
        d += "A%.3f,%.3f 0 0 1 %.3f,%.3f" % (r_bl, r_bl, x, y + 1 - r_bl)
    d += "V%.3f" % (y + r_tl)
    if r_tl:
        d += "A%.3f,%.3f 0 0 1 %.3f,%.3f" % (r_tl, r_tl, x + r_tl, y)
    return d + "Z"


def _rr_path(x0, y0, size, rad):
    x1, y1 = x0 + size, y0 + size
    p = "M%.3f,%.3f" % (x0 + rad, y0)
    p += "H%.3f A%.3f,%.3f 0 0 1 %.3f,%.3f" % (x1 - rad, rad, rad, x1, y0 + rad)
    p += "V%.3f A%.3f,%.3f 0 0 1 %.3f,%.3f" % (y1 - rad, rad, rad, x1 - rad, y1)
    p += "H%.3f A%.3f,%.3f 0 0 1 %.3f,%.3f" % (x0 + rad, rad, rad, x0, y1 - rad)
    p += "V%.3f A%.3f,%.3f 0 0 1 %.3f,%.3f" % (y0 + rad, rad, rad, x0 + rad, y0)
    return p + "Z"


def render_svg(matrix, dark, light, border):
    """矢量版：与 PNG 同一套几何参数，印刷放大不糊"""
    n = len(matrix)
    inner = n - 2 * border
    dark_at = lambda x, y: 0 <= x < n and 0 <= y < n and matrix[y][x]

    covered = set()
    for ox, oy in finder_origins(inner):
        for yy in range(FINDER):
            for xx in range(FINDER):
                covered.add((border + ox + xx, border + oy + yy))

    R = RATIO * 0.5
    paths = []
    for y in range(n):
        for x in range(n):
            if not dark_at(x, y) or (x, y) in covered:
                continue
            up, dn = dark_at(x, y - 1), dark_at(x, y + 1)
            lf, rt = dark_at(x - 1, y), dark_at(x + 1, y)
            paths.append(cell_path(
                x, y,
                R if (not up and not lf) else 0,
                R if (not up and not rt) else 0,
                R if (not dn and not rt) else 0,
                R if (not dn and not lf) else 0,
            ))

    for ox, oy in finder_origins(inner):
        ox, oy = ox + border, oy + border
        paths.append(_rr_path(ox, oy, FINDER, R_OUT))
        paths.append(_rr_path(ox + 1, oy + 1, FINDER - 2, R_HOLE))
        paths.append(_rr_path(ox + 2, oy + 2, FINDER - 4, R_IN))

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %(n)d %(n)d" '
        'width="%(mm).1fmm" height="%(mm).1fmm">'
        '<rect width="%(n)d" height="%(n)d" fill="%(light)s"/>'
        '<path fill-rule="evenodd" d="%(path)s" fill="%(dark)s"/>'
        "</svg>\n"
        % {"n": n, "mm": n * 1.0, "light": light, "dark": dark,
           "path": "".join(paths)}
    )


def main():
    ap = argparse.ArgumentParser(description="为网页生成二维码")
    ap.add_argument("url", help="要生成二维码的完整网址")
    ap.add_argument("--dark", default="#ffc02e", help="模块颜色（默认琥珀黄）")
    ap.add_argument("--light", default="#fff9ec", help="底色（默认奶油白）")
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
    matrix = qr.get_matrix()

    dark_rgb = tuple(int(args.dark[i:i + 2], 16) for i in (1, 3, 5))
    light_rgb = tuple(int(args.light[i:i + 2], 16) for i in (1, 3, 5))

    png_path = os.path.join(ASSETS, args.name + ".png")
    svg_path = os.path.join(ASSETS, args.name + ".svg")

    img = render_png(matrix, args.box, dark_rgb, light_rgb, args.border)
    img.save(png_path, optimize=True)
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(render_svg(matrix, args.dark, args.light, args.border))

    print("\n" + "=" * 46)
    qr.print_ascii(invert=True)
    print("=" * 46)
    print("网址 : " + url)
    print("模块 : %d x %d" % (qr.modules_count, qr.modules_count))
    print("样式 : %s on %s（圆角模块 + 大圆角定位框）" % (args.dark, args.light))
    print("图片 : assets/%s.png" % args.name)
    print("矢量 : assets/%s.svg  （印刷用，放大不糊）" % args.name)
    print("\n把改动 push 到 GitHub，页脚就会显示这张二维码。")


if __name__ == "__main__":
    main()
