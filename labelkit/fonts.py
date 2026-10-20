"""TrueType 字体：文字先在本机渲染成 1 位位图，再用 TSPL BITMAP 发送。

这样预览和打印用的是同一张位图，字体、字号不受打印机内置字体限制，中文也能印。
字体文件来自 Windows 自带字体；本机没有的字体不会出现在列表里。
"""

import os

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

# 键 → (显示名, 文件, Bahnschrift 这类可变字体的样式名)
FAMILIES = {
    "arial_bold": ("Arial 粗体", "arialbd.ttf", None),
    "arial": ("Arial", "arial.ttf", None),
    "arial_narrow_bold": ("Arial Narrow 粗体（窄）", "ARIALNB.TTF", None),
    "bahnschrift_bold_cond": ("Bahnschrift 粗体窄", "bahnschrift.ttf", "Bold Condensed"),
    "bahnschrift_semibold": ("Bahnschrift 半粗", "bahnschrift.ttf", "SemiBold"),
    "segoe_bold": ("Segoe UI 粗体", "segoeuib.ttf", None),
    "consolas_bold": ("Consolas 粗体（等宽）", "consolab.ttf", None),
    "impact": ("Impact（很粗）", "impact.ttf", None),
    "yahei_bold": ("微软雅黑 粗体（中文）", "msyhbd.ttc", None),
    "simhei": ("黑体（中文）", "simhei.ttf", None),
}

_cache = {}


def available():
    """[(键, 显示名), ...]，只列本机存在的字体。"""
    return [(k, v[0]) for k, v in FAMILIES.items() if os.path.exists(os.path.join(FONT_DIR, v[1]))]


def get(family, size_px):
    key = (family, size_px)
    if key not in _cache:
        if family not in FAMILIES:
            raise ValueError("未知字体：{}".format(family))
        _, filename, variation = FAMILIES[family]
        path = os.path.join(FONT_DIR, filename)
        try:
            font = ImageFont.truetype(path, size_px)
        except OSError:
            raise ValueError("本机没有字体文件 {}".format(filename))
        if variation:
            font.set_variation_by_name(variation)
        _cache[key] = font
    return _cache[key]


def measure(font, text):
    return int(round(font.getlength(text)))


def line_height(font):
    ascent, descent = font.getmetrics()
    return ascent + descent


def render(font, lines, align, width, gap_px):
    """把多行文字画成 1 位图（mode "1"：0 = 黑）。width 为整块宽度（点）。"""
    lh = line_height(font)
    height = max(1, len(lines) * lh + (len(lines) - 1) * gap_px)
    img = Image.new("L", (max(1, width), height), 255)
    d = ImageDraw.Draw(img)
    ascent = font.getmetrics()[0]
    for i, line in enumerate(lines):
        w = measure(font, line)
        x = {"right": width - w, "center": (width - w) // 2}.get(align, 0)
        d.text((x, i * (lh + gap_px) + ascent), line, fill=0, font=font, anchor="ls")
    # 热敏只有黑白：按 50% 灰度二值化，不做抖动，边缘更干净
    return img.point(lambda v: 0 if v < 128 else 255).convert("1")
