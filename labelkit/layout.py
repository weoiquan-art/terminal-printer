"""读取模板、填变量、排版，输出以「点」为单位的绘制指令。

TSPL 和预览都只读这里的结果，保证两边位置一致。
"""

import json
import string

import qrcode

from . import code128, fonts

# TSPL 内置字体在 203dpi 下的字符格（宽, 高），单位：点
FONTS = {
    "1": (8, 12),
    "2": (12, 20),
    "3": (16, 24),
    "4": (24, 32),
    "5": (32, 48),
    "6": (14, 19),
    "7": (21, 27),
    "8": (14, 25),
}

QR_ECC = {
    "L": qrcode.constants.ERROR_CORRECT_L,
    "M": qrcode.constants.ERROR_CORRECT_M,
    "Q": qrcode.constants.ERROR_CORRECT_Q,
    "H": qrcode.constants.ERROR_CORRECT_H,
}


def load_template(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def template_fields(tpl):
    names = set()
    for el in tpl["elements"]:
        for key in ("text", "data"):
            if key in el:
                names.update(n for _, n, _, _ in string.Formatter().parse(el[key]) if n)
    return sorted(names)


def _fill(s, values):
    missing = [n for _, n, _, _ in string.Formatter().parse(s) if n and n not in values]
    if missing:
        raise ValueError("缺少变量：" + ", ".join(missing))
    return s.format_map(values)


def _check_ascii(s):
    bad = [ch for ch in s if not (32 <= ord(ch) <= 126)]
    if bad:
        # 中文位图渲染是 M3 的可选项，暂不支持
        raise ValueError("暂只支持 ASCII 文字：{!r}".format(s))


def _wrap(text, fits):
    """按空格换行；fits(行) 判断一行放不放得下。中文等无空格的长词按字拆。"""
    lines, cur = [], ""
    for word in text.split():
        if not fits(word):
            if all(ord(ch) < 128 for ch in word):
                raise ValueError("单词太长，放不下一行：{!r}".format(word))
            for ch in word:
                cand = cur + ch
                if fits(cand):
                    cur = cand
                else:
                    lines.append(cur)
                    cur = ch
            continue
        cand = word if not cur else cur + " " + word
        if fits(cand):
            cur = cand
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def build(tpl, values, strict=True):
    """返回 (label, ops)。label 含尺寸等参数，ops 为绘制指令列表，坐标单位：点。

    每个 op 带 "el"（来自第几个元素）。strict=False 时（编辑器用）某个元素出错
    或越界不抛异常，记到 label["warnings"]：[(元素序号, 说明), ...]，出错的元素不画。
    """
    dpm = tpl.get("dots_per_mm", 8)
    w = round(tpl["width_mm"] * dpm)
    h = round(tpl["height_mm"] * dpm)

    def dots(mm):
        return round(mm * dpm)

    ops = []
    warnings = []
    prev_bottom = 0  # 上一个元素的下边，供 "y": "after" 使用
    for i, el in enumerate(tpl["elements"]):
        try:
            new_ops = _element(el, values, dots, w, prev_bottom)
        except (ValueError, KeyError) as e:
            if strict:
                raise
            msg = str(e) if isinstance(e, ValueError) else "缺少参数 {}".format(e)
            warnings.append((i, msg))
            continue
        for op in new_ops:
            op["el"] = i
        ops.extend(new_ops)
        if new_ops:
            prev_bottom = max(bbox(op)[3] for op in new_ops)
        elif el.get("y") != "after":
            prev_bottom = dots(el["y"])

    for op in ops:
        x0, y0, x1, y1 = bbox(op)
        if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
            msg = "元素超出标签范围：{}".format(describe(op))
            if strict:
                raise ValueError(msg)
            warnings.append((op["el"], msg))

    label = {
        "width_mm": tpl["width_mm"],
        "height_mm": tpl["height_mm"],
        "gap_mm": tpl.get("gap_mm", 2),
        "direction": tpl.get("direction", 1),
        "w": w,
        "h": h,
        "warnings": warnings,
    }
    return label, ops


def _element(el, values, dots, label_w, prev_bottom):
    kind = el["type"]
    if kind == "text":
        return _text(el, values, dots, prev_bottom)
    if kind == "qrcode":
        return [_qrcode(el, values, dots)]
    if kind == "barcode":
        return [_barcode(el, values, dots, label_w)]
    if kind == "box":
        return [{"op": "box", "x": dots(el["x"]), "y": dots(el["y"]),
                 "w": dots(el["w"]), "h": dots(el["h"]),
                 "t": dots(el.get("thickness", 0.25))}]
    if kind == "bar":
        return [{"op": "bar", "x": dots(el["x"]), "y": dots(el["y"]),
                 "w": dots(el["w"]), "h": dots(el["h"])}]
    raise ValueError("未知元素类型：" + kind)


def _text(el, values, dots, prev_bottom=0):
    if "family" in el:
        return _ttext(el, values, dots, prev_bottom)
    s = " ".join(_fill(el["text"], values).split())
    _check_ascii(s)
    font = str(el.get("font", "3"))
    mx, my = el.get("scale", [1, 1])
    cw, ch = FONTS[font][0] * mx, FONTS[font][1] * my
    pitch = ch + dots(el.get("line_gap", 0))
    if el["y"] == "after":
        y = prev_bottom + dots(el.get("gap", 0))
    else:
        y = dots(el["y"])

    max_lines = el.get("max_lines", 1)
    if "max_bottom" in el:
        # 行数由剩余高度决定：最后一行的下边不超过 max_bottom
        fit = (dots(el["max_bottom"]) - y - ch) // pitch + 1
        max_lines = min(el.get("max_lines", fit), fit)

    if "max_width" in el:
        max_chars = dots(el["max_width"]) // cw
        lines = _wrap(s, lambda line: len(line) <= max_chars)
        if len(lines) > max_lines:
            raise ValueError("文字放不下（这里最多 {} 行，每行 {} 字，共 {} 字）：{!r}".format(
                max(max_lines, 0), max_chars, max(max_lines, 0) * max_chars, s))
    else:
        lines = [s] if s else []

    x = el["x"]
    ops = []
    for line in lines:
        width = len(line) * cw
        if x == "center":
            raise ValueError("文字暂不支持 center，请用 align")
        left = dots(x)
        align = el.get("align", "left")
        if align == "right":
            left -= width
        elif align == "center":
            left -= width // 2
        ops.append({"op": "text", "x": left, "y": y, "font": font,
                    "mx": mx, "my": my, "cw": cw, "ch": ch, "s": line})
        y += pitch
    return ops


def _ttext(el, values, dots, prev_bottom):
    """TrueType 文字：整块渲染成一张位图。size 为字号（mm，约等于大写字母高度的 1.4 倍）。"""
    s = " ".join(_fill(el["text"], values).split())
    font = fonts.get(el["family"], max(4, dots(el.get("size", 3))))
    gap = dots(el.get("line_gap", 0))
    lh = fonts.line_height(font)
    y = prev_bottom + dots(el.get("gap", 0)) if el["y"] == "after" else dots(el["y"])

    max_lines = el.get("max_lines", 1)
    if "max_bottom" in el:
        fit = (dots(el["max_bottom"]) - y - lh) // (lh + gap) + 1
        max_lines = min(el.get("max_lines", fit), fit)
    if "max_width" in el:
        limit = dots(el["max_width"])
        lines = _wrap(s, lambda line: fonts.measure(font, line) <= limit)
        if len(lines) > max_lines:
            raise ValueError("文字放不下（这里最多 {} 行，宽 {}mm）：{!r}".format(
                max(max_lines, 0), el["max_width"], s))
    else:
        lines = [s] if s else []
    if not lines:
        return []

    align = el.get("align", "left")
    width = max(fonts.measure(font, line) for line in lines)
    left = dots(el["x"])
    if align == "right":
        left -= width
    elif align == "center":
        left -= width // 2
    img = fonts.render(font, lines, align, width, gap)
    return [{"op": "bitmap", "x": left, "y": y, "w": img.width, "h": img.height,
             "img": img, "s": " / ".join(lines)}]


def _qrcode(el, values, dots):
    data = _fill(el["data"], values)
    _check_ascii(data)
    ecc = el.get("ecc", "M")
    qr = qrcode.QRCode(error_correction=QR_ECC[ecc], box_size=1, border=0)
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    return {"op": "qrcode", "x": dots(el["x"]), "y": dots(el["y"]), "ecc": ecc,
            "cell": el.get("cell", 4), "data": data, "matrix": matrix,
            "version": qr.version}


def _barcode(el, values, dots, label_w):
    data = _fill(el["data"], values)
    narrow = el.get("narrow", 2)
    pattern = code128.modules(data)
    width = len(pattern) * narrow
    x = (label_w - width) // 2 if el["x"] == "center" else dots(el["x"])
    return {"op": "barcode", "x": x, "y": dots(el["y"]), "h": dots(el["height"]),
            "narrow": narrow, "data": data, "pattern": pattern,
            "readable": el.get("readable", False)}


def bbox(op):
    kind = op["op"]
    x, y = op["x"], op["y"]
    if kind == "text":
        return x, y, x + len(op["s"]) * op["cw"], y + op["ch"]
    if kind == "qrcode":
        n = len(op["matrix"]) * op["cell"]
        return x, y, x + n, y + n
    if kind == "barcode":
        extra = 30 if op["readable"] else 0  # 可读文字约占高度，粗略估计
        return x, y, x + len(op["pattern"]) * op["narrow"], y + op["h"] + extra
    return x, y, x + op["w"], y + op["h"]


def describe(op):
    x0, y0, x1, y1 = bbox(op)
    what = op.get("s") or op.get("data") or ""
    return "{} {!r} @ ({},{})-({},{}) 点".format(op["op"], what, x0, y0, x1, y1)
