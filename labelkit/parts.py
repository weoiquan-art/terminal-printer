"""按货号查零件名称。数据来自 data/parts.csv（tools/import_parts.py 生成）。

Green 的 Description：第一行是名称（DESC），第二行起是车型、尺寸等（MODEL），
这里只做拆分，不删改内容，打印前由用户自己核对修改。
"""

import csv
import os

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "parts.csv")


def _squash(s):
    return " ".join(s.split())


def _key(code):
    return "".join(code.split()).upper()


def split_description(desc):
    lines = [_squash(x) for x in desc.splitlines()]
    lines = [x for x in lines if x]
    if not lines:
        return "", ""
    return lines[0], " ".join(lines[1:])


class Parts:
    def __init__(self, path=DEFAULT_PATH):
        if not os.path.exists(path):
            raise FileNotFoundError("找不到零件数据 {}，先运行 tools/import_parts.py".format(path))
        self.exact = {}
        self.loose = {}
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                code = r["code"]
                self.exact.setdefault(code, r["description"])
                self.loose.setdefault(_key(code), []).append(code)

    def lookup(self, code):
        """返回 (找到的货号, DESC, MODEL, 备注)。找不到时货号为 None。"""
        code = code.strip()
        if code in self.exact:
            desc, model = split_description(self.exact[code])
            return code, desc, model, ""
        candidates = self.loose.get(_key(code), [])
        if len(candidates) == 1:
            found = candidates[0]
            desc, model = split_description(self.exact[found])
            return found, desc, model, "按去空格匹配到 {}".format(found)
        if candidates:
            return None, "", "", "多个货号匹配：" + " | ".join(candidates)
        return None, "", "", "数据里没有这个货号"
