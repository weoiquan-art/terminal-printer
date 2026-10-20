"""M4：本地网页标签编辑器。只监听本机 127.0.0.1，不对外开放。

用法：
    python editor.py            启动并打开浏览器（默认 http://127.0.0.1:8765/）
    python editor.py --no-open  只启动

预览和打印都走 labelkit，与 label.py / batch.py 完全同一套排版。
编辑器里的「打印一张」固定只打 1 张。
"""

import argparse
import base64
import copy
import io
import json
import os
import re
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from labelkit import fonts, layout, preview, printer, tspl

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(HERE, "templates")
EDITOR_DIR = os.path.join(HERE, "editor")
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

# XP-420B 最大打印宽度约 108mm；高度上限只是防止输错
LIMITS = {"width_mm": (10, 108), "height_mm": (10, 300), "gap_mm": (0, 10)}


def _check_template(tpl):
    for key, (lo, hi) in LIMITS.items():
        v = tpl.get(key)
        if not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise ValueError("{} 要在 {}～{} 之间".format(key, lo, hi))
    if not isinstance(tpl.get("elements"), list):
        raise ValueError("模板缺少 elements")


def _render(tpl, values):
    _check_template(tpl)
    label, ops = layout.build(tpl, values, strict=False)
    img = preview.render(label, ops, scale=1, margin=0)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    boxes = {}
    for op in ops:
        x0, y0, x1, y1 = layout.bbox(op)
        b = boxes.setdefault(op["el"], [x0, y0, x1, y1])
        boxes[op["el"]] = [min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1)]
    return label, ops, {
        "png": base64.b64encode(buf.getvalue()).decode("ascii"),
        "w": label["w"],
        "h": label["h"],
        "dots_per_mm": tpl.get("dots_per_mm", 8),
        "boxes": [{"el": i, "box": b} for i, b in sorted(boxes.items())],
        "warnings": [{"el": i, "msg": m} for i, m in label["warnings"]],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

    def _same_origin(self):
        # 防止别的网页借浏览器向本机编辑器发请求（例如偷偷打印、覆盖模板）
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        return origin is None or origin in ("http://" + host,)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            with open(os.path.join(EDITOR_DIR, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path == "/api/templates":
            names = sorted(n[:-5] for n in os.listdir(TEMPLATE_DIR) if n.endswith(".json"))
            return self._send(200, {"templates": names, "printer": printer.DEFAULT_PRINTER,
                                    "fonts": fonts.available(), "builtin_fonts": layout.FONTS})
        if path.startswith("/api/template/"):
            name = path[len("/api/template/"):]
            if not NAME_RE.match(name):
                return self._send(400, {"error": "模板名不合法"})
            p = os.path.join(TEMPLATE_DIR, name + ".json")
            if not os.path.exists(p):
                return self._send(404, {"error": "没有这个模板"})
            return self._send(200, layout.load_template(p))
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._same_origin():
            return self._send(403, {"error": "拒绝跨站请求"})
        try:
            body = self._json_body()
            path = self.path
            if path == "/api/preview":
                _, _, result = _render(body["template"], body.get("values", {}))
                return self._send(200, result)
            if path == "/api/save":
                name, tpl, overwrite = body["name"], body["template"], body.get("overwrite", False)
                if not NAME_RE.match(name):
                    raise ValueError("模板名只能用英文字母、数字、- 和 _")
                _check_template(tpl)
                p = os.path.join(TEMPLATE_DIR, name + ".json")
                if os.path.exists(p) and not overwrite:
                    return self._send(409, {"error": "已有同名模板", "exists": True})
                tpl = copy.deepcopy(tpl)
                tpl["name"] = name
                with open(p, "w", encoding="utf-8", newline="\n") as f:
                    json.dump(tpl, f, ensure_ascii=False, indent=2)
                    f.write("\n")
                return self._send(200, {"saved": name})
            if path == "/api/print":
                tpl, values = body["template"], body.get("values", {})
                _check_template(tpl)
                label, ops = layout.build(tpl, values)  # 严格模式：有任何问题都不打印
                data = tspl.render(label, ops, 1)
                written = printer.send_raw(body.get("printer") or printer.DEFAULT_PRINTER,
                                           data, "terminal-printer editor")
                return self._send(200, {"sent": written})
            self._send(404, {"error": "not found"})
        except (ValueError, KeyError, TypeError) as e:
            self._send(400, {"error": str(e)})
        except Exception as e:  # 打印机等外部错误，原样告诉页面
            self._send(500, {"error": "{}: {}".format(type(e).__name__, e)})


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="标签编辑器")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = "http://127.0.0.1:{}/".format(args.port)
    print("编辑器已启动：{}（Ctrl+C 退出）".format(url))
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
