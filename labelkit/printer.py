"""通过 Windows 打印队列以 RAW 方式发送数据。"""

DEFAULT_PRINTER = "Xprinter XP-420B"


def list_printers():
    import win32print

    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    default = win32print.GetDefaultPrinter()
    return [(p[2], p[2] == default) for p in win32print.EnumPrinters(flags)]


def send_raw(printer_name, data, doc_name="terminal-printer"):
    import win32print

    handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(handle, 1, (doc_name, None, "RAW"))
        try:
            win32print.StartPagePrinter(handle)
            written = win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
        finally:
            win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)
    return written
