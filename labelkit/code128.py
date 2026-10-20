"""Code 128 B 编码，只用于预览和算宽度；打印时由打印机自己编码。

固定用 B 字符集（打印端用 TSPL 128M + !104），这样预览与实物的模块数一致。
"""

from barcode.charsets import code128 as _tables

START_B = 104
_STOP = _tables.STOP + "11"  # 终止符 13 个模块，码表里少了最后的终止条


def check_data(data):
    for ch in data:
        if not (32 <= ord(ch) <= 126) or ch in '!"':
            raise ValueError("条码内容只支持可打印 ASCII（不含 ! 和 \"）：{!r}".format(data))


def modules(data):
    """返回 '1'（条）/'0'（空）组成的模块串，不含静区。"""
    check_data(data)
    values = [START_B] + [_tables.B[ch] for ch in data]
    checksum = (START_B + sum(i * v for i, v in enumerate(values[1:], 1))) % 103
    values.append(checksum)
    return "".join(_tables.CODES[v] for v in values) + _STOP


def width_modules(data):
    return 11 * (len(data) + 2) + 13
