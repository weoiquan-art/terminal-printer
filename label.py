"""M2：按 JSON 模板生成标签，出预览图，可选打印。

用法（Windows）：
    python label.py --no "81 96020 0340" --desc "ENG MTG F RB" \\
        --model "18310 18360 22403 26414" --price "RM260+" --preview out\\preview.png
    python label.py ... --dry-run                 只输出 TSPL
    python label.py ... --print [--copies 3]      发到打印机（默认 Xprinter XP-420B）
    python label.py --list                        列出打印机

不加 --print 不会打印。
"""

import argparse
import os
import sys

from labelkit import layout, preview, printer, tspl

DEFAULT_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "templates", "default_50x40.json")


def main():
    # 输出被重定向时 Windows 默认 cp1252，中文会报错
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="按模板打印标签")
    parser.add_argument("--template", default=DEFAULT_TEMPLATE, help="模板 JSON")
    parser.add_argument("--no", help="零件号 NO（也用作条码内容）")
    parser.add_argument("--desc", help="零件名称 DESC")
    parser.add_argument("--model", help="适用车型，空格分隔")
    parser.add_argument("--price", help="价格，原样印出，例如 RM260+")
    parser.add_argument("--copies", type=int, default=1, help="打印张数")
    parser.add_argument("--preview", help="预览图输出路径（PNG）")
    parser.add_argument("--dry-run", action="store_true", help="输出 TSPL")
    parser.add_argument("--print", dest="do_print", action="store_true", help="发送到打印机")
    parser.add_argument("--printer", default=printer.DEFAULT_PRINTER, help="打印机名称")
    parser.add_argument("--list", action="store_true", help="列出打印机")
    args = parser.parse_args()

    if args.list:
        for name, is_default in printer.list_printers():
            print(("* " if is_default else "  ") + name)
        return

    tpl = layout.load_template(args.template)
    values = {k: getattr(args, k) for k in layout.template_fields(tpl)
              if getattr(args, k, None) is not None}
    try:
        label, ops = layout.build(tpl, values)
    except ValueError as e:
        sys.exit("错误：{}".format(e))
    if args.copies < 1:
        sys.exit("错误：--copies 至少为 1")

    for op in ops:
        if op["op"] == "qrcode":
            n = len(op["matrix"])
            print("二维码：版本 {}，{}x{} 模块，{:.1f}mm 见方".format(
                op["version"], n, n, n * op["cell"] / 8))
        elif op["op"] == "barcode":
            print("条码：{} 模块，宽 {:.1f}mm，起点 x={}".format(
                len(op["pattern"]), len(op["pattern"]) * op["narrow"] / 8, op["x"]))

    data = tspl.render(label, ops, args.copies)
    if args.dry_run:
        sys.stdout.write(data.decode("ascii"))
    if args.preview:
        os.makedirs(os.path.dirname(os.path.abspath(args.preview)), exist_ok=True)
        preview.render(label, ops).save(args.preview)
        print("预览图：" + args.preview)
    if args.do_print:
        written = printer.send_raw(args.printer, data, "terminal-printer label")
        print("已发送 {} 字节到「{}」，{} 张".format(written, args.printer, args.copies))


if __name__ == "__main__":
    main()
