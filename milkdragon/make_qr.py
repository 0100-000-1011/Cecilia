#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把网址生成二维码，存到 assets/qr.png 和 assets/qr.svg。
网页会自动在页脚显示 qr.png。

默认样式：琥珀黄圆角模块 + 奶油底（圆点风）。

用法：
    python3 make_qr.py https://你的用户名.github.io/仓库名/
    python3 make_qr.py <网址> --dark "#ffc02e" --light "#fff9ec"

第一次运行前需要装依赖：
    python3 -m pip install -r requirements.txt
"""

import argparse
import os
import sys

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_Q
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("缺少依赖，先执行：python3 -m pip install -r requirements.txt")

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

# 三个 7x7 定位框在矩阵中的原点（border 已含在矩阵里，border=3 时从 3 开始）
FINDER_OFF = 7          # 定位框尺寸
R_OUT, R_HOLE, R_IN = 3.0, 2.0, 1.4   # 外环 / 白圈 / 内芯的圆角（模块单位）


def finder_origins(n, border):
    """返回三个定位框的矩阵坐标原点（假设 border>=3）"""
    edge = n - border - FINDER_OFF
    return [(border, border), (edge, border), (border, edge)]


def cell_path(x, y, r_tl, r_tr, r_br, r_bl):
    """单个模块的圆角路径；四角半径可分别指定（0 = 直角）"""
    d = "M%.2f,%.2f" % (x + r_tl, y)
    d += "H%.2f" % (x + 1 - r_tr)
    if r_tr:
        d += "A%.2f,%.2f 0 0 1 %.2f,%.2f" % (r_tr, r_tr, x + 1, y + r_tr)
    else:
        d += "V%.2f" % (y + r_tr)
    d += "V%.2f" % (y + 1 - r_br)
    if r_br:
        d += "A%.2f,%.2f 0 0 1 %.2f,%.2f" % (r_br, r_br, x + 1 - r_br, y + 1)
    else:
        d += "H%.2f" % (x + 1)
    d += "H%.2f" % (x + r_bl)
    if r_bl:
        d += "A%.2f,%.2f 0 0 1 %.2f,%.2f" % (r_bl, r_bl, x, y + 1 - r_bl)
    else:
        d += "V%.2f" % (y + 1 - r_bl)
    d += "V%.2f" % (y + r_tl)
    if r_tl:
        d += "A%.2f,%.2f 0 0 1 %.2f,%.2f" % (r_tl, r_tl, x + r_tl, y)
    else:
        d += "H%.2f" % x
    return d + "Z"


def rounded_svg(matrix, dark, light, border):
    """圆角模块 SVG：定位框画成大圆角同心环，其余模块邻居感知圆角（孤点成圆）"""
    n = len(matrix)
    dark_at = lambda x, y: 0 <= x < n and 0 <= y < n and matrix[y][x]
    R, r = 0.5, 0.0  # 无邻居侧圆角半径 / 有邻居侧的小倒角

    # 定位框覆盖范围（跳过这些格子，改画整体圆角环）
    covered = set()
    for ox, oy in finder_origins(n, border):
        for yy in range(FINDER_OFF):
            for xx in range(FINDER_OFF):
                covered.add((ox + xx, oy + yy))

    paths = []
    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            if not cell or (x, y) in covered:
                continue
            up, dn = dark_at(x, y - 1), dark_at(x, y + 1)
            lf, rt = dark_at(x - 1, y), dark_at(x + 1, y)
            paths.append(cell_path(x, y,
                                   R if (not up and not lf) else r,   # 左上
                                   R if (not up and not rt) else r,   # 右上
                                   R if (not dn and not rt) else r,   # 右下
                                   R if (not dn and not lf) else r))  # 左下

    # 定位框：外环(带白圈洞) + 内芯，用 evenodd 挖洞
    def _rr_path(x0, y0, size, rad):
        x1, y1 = x0 + size, y0 + size
        d = "M%.2f,%.2f" % (x0 + rad, y0)
        d += "H%.2f A%.2f,%.2f 0 0 1 %.2f,%.2f" % (x1 - rad, rad, rad, x1, y0 + rad)
        d += "V%.2f A%.2f,%.2f 0 0 1 %.2f,%.2f" % (y1 - rad, rad, rad, x1 - rad, y1)
        d += "H%.2f A%.2f,%.2f 0 0 1 %.2f,%.2f" % (x0 + rad, rad, rad, x0, y1 - rad)
        d += "V%.2f A%.2f,%.2f 0 0 1 %.2f,%.2f" % (y0 + rad, rad, rad, x0 + rad, y0)
        return d + "Z"

    for ox, oy in finder_origins(n, border):
        paths.append(_rr_path(ox, oy, FINDER_OFF, R_OUT))          # 外环
        paths.append(_rr_path(ox + 1, oy + 1, 5, R_HOLE))          # 白圈（洞）
        paths.append(_rr_path(ox + 2, oy + 2, 3, R_IN))            # 内芯

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

    png_path = os.path.join(ASSETS, args.name + ".png")
    svg_path = os.path.join(ASSETS, args.name + ".svg")

    # PNG：圆角模块。这版 qrcode 的 StyledPilImage 会忽略颜色参数，
    # 先生成黑白圆角图，再按明暗重新上色（LUT 插值，抗锯齿边缘同样平滑）
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
    ).convert("RGB")
    img.save(png_path)
    dark_rgb = tuple(int(args.dark[i:i + 2], 16) for i in (1, 3, 5))
    light_rgb = tuple(int(args.light[i:i + 2], 16) for i in (1, 3, 5))
    lut = []
    for d, l in zip(dark_rgb, light_rgb):
        lut += [round(d + (l - d) * i / 255) for i in range(256)]
    img = img.point(lut)  # LUT 重上色（返回新图，要接住）

    # 三个定位框叠成大圆角同心环（这版 qrcode 没有独立的眼睛绘制器）。
    # 注意底层绘制器画的定位框是方角，必须先用底色擦掉一块更大的圆角区域
    b = args.box
    d = ImageDraw.Draw(img)
    for ox, oy in finder_origins(qr.modules_count + 2 * args.border, args.border):
        x0, y0 = ox * b, oy * b
        s = FINDER_OFF * b
        d.rounded_rectangle([x0 - 2, y0 - 2, x0 + s + 2, y0 + s + 2],
                            radius=b * 0.5, fill=light_rgb)  # 擦掉方角（小圆角，确保盖住角落）
        d.rounded_rectangle([x0, y0, x0 + s, y0 + s], radius=R_OUT * b,
                            fill=dark_rgb)   # 外环
        g = b
        d.rounded_rectangle([x0 + g, y0 + g, x0 + s - g, y0 + s - g],
                            radius=R_HOLE * b, fill=light_rgb)  # 白圈
        d.rounded_rectangle([x0 + 2 * g, y0 + 2 * g, x0 + s - 2 * g, y0 + s - 2 * g],
                            radius=R_IN * b, fill=dark_rgb)     # 内芯
    img.save(png_path)

    # SVG：矢量圆角版，放大印刷不糊
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(rounded_svg(qr.get_matrix(), args.dark, args.light, args.border))

    print("\n" + "=" * 46)
    qr.print_ascii(invert=True)
    print("=" * 46)
    print("网址 : " + url)
    print("模块 : %d x %d" % (qr.modules_count, qr.modules_count))
    print("样式 : %s on %s（圆角模块）" % (args.dark, args.light))
    print("图片 : assets/%s.png" % args.name)
    print("矢量 : assets/%s.svg  （印刷用，放大不糊）" % args.name)
    print("\n把改动 push 到 GitHub，页脚就会显示这张二维码。")


if __name__ == "__main__":
    main()
