"""绘制指令 → PNG 预览。1 像素 = 1 点；字体用等宽 TTF 近似打印机内置字体。"""

import os

from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = [
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "consolab.ttf"),
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "consola.ttf"),
    "DejaVuSansMono-Bold.ttf",
]
_font_cache = {}


def _font(height):
    if height not in _font_cache:
        font = None
        for path in _FONT_CANDIDATES:
            try:
                font = ImageFont.truetype(path, height)
                break
            except OSError:
                continue
        _font_cache[height] = font or ImageFont.load_default()
    return _font_cache[height]


def render(label, ops, scale=2, margin=8):
    w, h = label["w"], label["h"]
    img = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(img)

    for op in ops:
        kind = op["op"]
        x, y = op["x"], op["y"]
        if kind == "text":
            font = _font(op["ch"])
            for i, ch in enumerate(op["s"]):
                cx = x + i * op["cw"] + op["cw"] / 2
                d.text((cx, y + op["ch"] / 2), ch, fill=0, font=font, anchor="mm")
        elif kind == "qrcode":
            c = op["cell"]
            for r, row in enumerate(op["matrix"]):
                for k, on in enumerate(row):
                    if on:
                        d.rectangle([x + k * c, y + r * c, x + (k + 1) * c - 1, y + (r + 1) * c - 1], fill=0)
        elif kind == "barcode":
            n = op["narrow"]
            for i, m in enumerate(op["pattern"]):
                if m == "1":
                    d.rectangle([x + i * n, y, x + (i + 1) * n - 1, y + op["h"] - 1], fill=0)
        elif kind == "box":
            t = op["t"]
            d.rectangle([x, y, x + op["w"] - 1, y + op["h"] - 1], outline=0, width=t)
        elif kind == "bar":
            d.rectangle([x, y, x + op["w"] - 1, y + op["h"] - 1], fill=0)

    # 放大并加一圈灰底，灰线即标签边缘
    big = img.resize((w * scale, h * scale), Image.NEAREST)
    out = Image.new("L", (big.width + 2 * margin, big.height + 2 * margin), 200)
    out.paste(big, (margin, margin))
    return out


def sheet(label, items, columns=3, scale=1):
    """批量总览：items 为 [(标题, ops), ...]，按网格排列。"""
    tiles = [render(label, ops, scale=scale, margin=4) for _, ops in items]
    tw, th = tiles[0].size
    cap = 22
    rows = (len(tiles) + columns - 1) // columns
    out = Image.new("L", (columns * (tw + 12) + 12, rows * (th + cap + 12) + 12), 255)
    d = ImageDraw.Draw(out)
    for i, ((title, _), tile) in enumerate(zip(items, tiles)):
        x = 12 + (i % columns) * (tw + 12)
        y = 12 + (i // columns) * (th + cap + 12)
        d.text((x, y), title, fill=0, font=_font(16))
        out.paste(tile, (x, y + cap))
    return out
