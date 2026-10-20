"""绘制指令 → TSPL。语法依据 TSPL/TSPL2 手册，改动后先打一张测试。

返回 bytes：文字指令是 ASCII，BITMAP 后面跟二进制位图数据。
"""

from PIL import Image


def _quote(s):
    return '"' + s.replace('"', '\\["]') + '"'


def _header(label):
    return [
        "SIZE {:g} mm,{:g} mm".format(label["width_mm"], label["height_mm"]),
        "GAP {:g} mm,0 mm".format(label["gap_mm"]),
        "DIRECTION {}".format(label["direction"]),
        "REFERENCE 0,0",
    ]


def _bitmap(op):
    """BITMAP x,y,每行字节数,高,0,数据。位为 1 = 不印（白），0 = 印（黑）。"""
    img = op["img"]
    wb = (img.width + 7) // 8
    if img.width % 8:
        padded = Image.new("1", (wb * 8, img.height), 1)  # 补齐的位填白
        padded.paste(img, (0, 0))
        img = padded
    head = "BITMAP {},{},{},{},0,".format(op["x"], op["y"], wb, img.height).encode("ascii")
    return head + img.tobytes()


def _body(ops, copies, display=False):
    lines = ["CLS"]
    for op in ops:
        kind = op["op"]
        if kind == "text":
            lines.append("TEXT {},{},{},0,{},{},{}".format(
                op["x"], op["y"], _quote(op["font"]), op["mx"], op["my"], _quote(op["s"])))
        elif kind == "qrcode":
            lines.append("QRCODE {},{},{},{},A,0,{}".format(
                op["x"], op["y"], op["ecc"], op["cell"], _quote(op["data"])))
        elif kind == "barcode":
            # 128M + !104：强制 Code 128 B，与预览的模块数一致
            lines.append('BARCODE {},{},"128M",{},{},0,{},{},{}'.format(
                op["x"], op["y"], op["h"], 1 if op["readable"] else 0,
                op["narrow"], op["narrow"], _quote("!104" + op["data"])))
        elif kind == "box":
            lines.append("BOX {},{},{},{},{}".format(
                op["x"], op["y"], op["x"] + op["w"], op["y"] + op["h"], op["t"]))
        elif kind == "bar":
            lines.append("BAR {},{},{},{}".format(op["x"], op["y"], op["w"], op["h"]))
        elif kind == "bitmap":
            if display:
                wb = (op["img"].width + 7) // 8
                lines.append("BITMAP {},{},{},{},0,<{} 字节位图>".format(
                    op["x"], op["y"], wb, op["img"].height, wb * op["img"].height))
            else:
                lines.append(_bitmap(op))
    lines.append("PRINT 1,{}".format(int(copies)))
    return lines


def render(label, ops, copies=1, display=False):
    return render_many(label, [(ops, copies)], display)


def render_many(label, jobs, display=False):
    """jobs：[(ops, 张数), ...]，同一模板的多种标签放进一个打印任务。

    display=True 时返回给人看的文本，位图只显示字节数。
    """
    lines = _header(label)
    for ops, copies in jobs:
        lines.extend(_body(ops, copies, display))
    if display:
        return "".join(x + "\n" for x in lines)
    return b"".join((x if isinstance(x, bytes) else x.encode("ascii")) + b"\r\n" for x in lines)
