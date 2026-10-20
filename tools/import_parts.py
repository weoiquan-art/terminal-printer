"""从零件主档/Green 报表 CSV 里只取「货号 + 名称」两列，写到 data/parts.csv。

成本、售价、价格暗号等列一律不带过来。data/ 不进 git。

用法：
    python tools/import_parts.py 零件主檔_v4.csv
    python tools/import_parts.py export.csv --code-col "Stock Code" --desc-col "Description"
"""

import argparse
import csv
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "parts.csv")


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="导入零件货号和名称")
    parser.add_argument("src", help="源 CSV")
    parser.add_argument("--code-col", default="Stock Code")
    parser.add_argument("--desc-col", default="Description")
    parser.add_argument("--source-name", help="记录在输出里的来源说明，默认用文件名")
    args = parser.parse_args()

    with open(args.src, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in (args.code_col, args.desc_col) if c not in reader.fieldnames]
        if missing:
            sys.exit("源文件缺少列：{}（现有列：{}）".format(", ".join(missing), ", ".join(reader.fieldnames)))
        rows = [(r[args.code_col].strip(), r[args.desc_col]) for r in reader if r[args.code_col].strip()]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "description"])
        w.writerows(rows)
    with open(OUT + ".source.txt", "w", encoding="utf-8") as f:
        f.write((args.source_name or os.path.basename(args.src)) + "\n")
    print("已写入 {} 条到 {}".format(len(rows), OUT))


if __name__ == "__main__":
    main()
