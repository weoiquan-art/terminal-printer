"""绘制指令 → TSPL。语法依据 TSPL/TSPL2 手册，改动后先打一张测试。"""


def _quote(s):
    return '"' + s.replace('"', '\\["]') + '"'


def render(label, ops, copies=1):
    lines = [
        "SIZE {:g} mm,{:g} mm".format(label["width_mm"], label["height_mm"]),
        "GAP {:g} mm,0 mm".format(label["gap_mm"]),
        "DIRECTION {}".format(label["direction"]),
        "REFERENCE 0,0",
        "CLS",
    ]
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
    lines.append("PRINT 1,{}".format(int(copies)))
    return ("\r\n".join(lines) + "\r\n").encode("ascii")
