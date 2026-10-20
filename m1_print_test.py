"""M1：向 XP-420B 发送一段硬编码 TSPL，打印一张 50x40mm 测试标签。

用法（Windows）：
    python m1_print_test.py --list                 列出本机打印机名称
    python m1_print_test.py --printer "Xprinter XP-420B"
    python m1_print_test.py --dry-run              只输出 TSPL，不打印（任何系统都可用）

验收看三点：外框四边都完整（不偏）、中心十字在标签正中、只出一张纸（不跳纸）。
"""

import argparse
import sys

# 假设：203dpi，即 8 点/mm。50x40mm = 400x320 点。须在真机上验证。
DOTS_PER_MM = 8
WIDTH_MM, HEIGHT_MM = 50, 40


def build_tspl(gap_mm):
    w = WIDTH_MM * DOTS_PER_MM
    h = HEIGHT_MM * DOTS_PER_MM
    cx, cy = w // 2, h // 2
    lines = [
        "SIZE {} mm,{} mm".format(WIDTH_MM, HEIGHT_MM),
        "GAP {} mm,0 mm".format(gap_mm),
        "DIRECTION 1",
        "REFERENCE 0,0",
        "CLS",
        # 距边 1mm 的外框：哪边缺了就说明往哪边偏
        "BOX 8,8,{},{},3".format(w - 8, h - 8),
        'TEXT 24,24,"3",0,2,2,"M1 TEST"',
        'TEXT 24,90,"3",0,1,1,"50x40mm 203dpi"',
        'TEXT 24,{},"3",0,1,1,"GAP {}mm"'.format(h - 50, gap_mm),
        # 中心十字
        "BAR {},{},4,40".format(cx - 2, cy - 20),
        "BAR {},{},40,4".format(cx - 20, cy - 2),
        "PRINT 1,1",
    ]
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


def list_printers():
    import win32print

    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    default = win32print.GetDefaultPrinter()
    for p in win32print.EnumPrinters(flags):
        name = p[2]
        print(("* " if name == default else "  ") + name)


def send_raw(printer_name, data):
    import win32print

    if not printer_name:
        printer_name = win32print.GetDefaultPrinter()
    handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(handle, 1, ("terminal-printer M1", None, "RAW"))
        try:
            win32print.StartPagePrinter(handle)
            written = win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
        finally:
            win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)
    print("已发送 {} 字节到「{}」".format(written, printer_name))


def main():
    parser = argparse.ArgumentParser(description="M1 测试标签")
    parser.add_argument("--list", action="store_true", help="列出打印机")
    parser.add_argument("--printer", help="打印机名称（默认用系统默认打印机）")
    parser.add_argument("--gap", type=float, default=2, help="间隙高度 mm，默认 2")
    parser.add_argument("--dry-run", action="store_true", help="只输出 TSPL")
    args = parser.parse_args()

    if args.list:
        list_printers()
        return
    gap = "{:g}".format(args.gap)
    data = build_tspl(gap)
    if args.dry_run:
        sys.stdout.write(data.decode("ascii"))
        return
    send_raw(args.printer, data)


if __name__ == "__main__":
    main()
