#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""麦当劳点餐台 · 本地原型服务（Python 标准库，无第三方依赖）。

启动：
    python order_app/app.py                # http://127.0.0.1:8765
    python order_app/app.py --lan          # 局域网可访问（手机真机）
    python order_app/app.py --port 9000

接口：
    GET  /api/menu                     菜单
    POST /api/order                    下单 → 取餐号
    POST /api/portrait                 订单 → 光谱 + 旋律
    GET  /media/<order>/<file>         产物（png / wav），支持 Range
    GET  /health                       健康检查
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import socket
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(APP_DIR)
for p in (PROJECT_DIR, APP_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import menu  # noqa: E402
import portrait_service as svc  # noqa: E402

STATIC_DIR = os.path.join(APP_DIR, "static")
OUT_DIR = os.path.join(APP_DIR, "out")
MAX_BODY = 1 << 20  # 1MB


def _safe_path(root: str, rel: str):
    """把 URL 相对路径限制在 root 目录内，防目录穿越。"""
    rel = unquote(rel).lstrip("/")
    full = os.path.realpath(os.path.join(root, rel))
    root_real = os.path.realpath(root)
    if full == root_real or full.startswith(root_real + os.sep):
        return full if os.path.isfile(full) else None
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "McdOrder/0.1"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------ 基础输出
    def _headers(self, code: int, ctype: str, length: int, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def _json(self, obj, code: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._headers(code, "application/json; charset=utf-8", len(body),
                      {"Cache-Control": "no-store"})
        self.wfile.write(body)

    def _error(self, code: int, msg: str):
        self._json(dict(error=msg), code)

    def _file(self, path: str, ctype: str, cache: str = "public, max-age=86400"):
        size = os.path.getsize(path)
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        partial = False
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            try:
                start = int(a) if a else 0
                end = int(b) if b else size - 1
            except ValueError:
                start, end = 0, size - 1
            if start >= size or start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            end = min(end, size - 1)
            partial = True

        length = end - start + 1
        extra = {"Accept-Ranges": "bytes", "Cache-Control": cache}
        if partial:
            extra["Content-Range"] = f"bytes {start}-{end}/{size}"
        self._headers(206 if partial else 200, ctype, length, extra)
        with open(path, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                chunk = f.read(min(64 * 1024, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    # ------------------------------------------------------------ 路由
    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path in ("/", "/index.html"):
                return self._file(os.path.join(STATIC_DIR, "index.html"),
                                  "text/html; charset=utf-8", "no-store")
            if path == "/health":
                return self._json(svc.health())
            if path == "/api/menu":
                return self._json(menu.menu_payload())
            if path.startswith("/static/"):
                f = _safe_path(STATIC_DIR, path[len("/static/"):])
                if not f:
                    return self._error(404, "资源不存在")
                return self._file(f, _ctype(f), "no-store")
            if path.startswith("/media/"):
                f = _safe_path(OUT_DIR, path[len("/media/"):])
                if not f:
                    return self._error(404, "产物不存在")
                return self._file(f, _ctype(f))
            return self._error(404, "页面不存在")
        except BrokenPipeError:
            pass
        except Exception:
            traceback.print_exc()
            self._error(500, "服务内部错误")

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
            if path == "/api/order":
                rec = svc.create_order(payload.get("items") or [])
                return self._json(rec)
            if path == "/api/portrait":
                order_no = str(payload.get("order_no") or "")
                style = str(payload.get("style") or "minyue")
                if not order_no:
                    return self._error(400, "缺少订单号")
                return self._json(svc.build_portrait(order_no, style))
            return self._error(404, "接口不存在")
        except ValueError as e:
            return self._error(400, str(e))
        except BrokenPipeError:
            pass
        except Exception:
            traceback.print_exc()
            self._error(500, "服务内部错误")

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ValueError("请求体长度不合法")
        if length <= 0:
            return {}
        if length > MAX_BODY:
            raise ValueError("请求体过大")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            raise ValueError("请求体不是合法 JSON")
        if not isinstance(data, dict):
            raise ValueError("请求体必须是对象")
        return data

    # ------------------------------------------------------------ 日志
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


def _ctype(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    fixed = {".wav": "audio/wav", ".png": "image/png", ".css": "text/css; charset=utf-8",
             ".js": "application/javascript; charset=utf-8",
             ".svg": "image/svg+xml", ".json": "application/json; charset=utf-8"}
    return fixed.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"


def _lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    ap = argparse.ArgumentParser(description="麦当劳点餐台原型")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--lan", action="store_true", help="绑定 0.0.0.0，供手机局域网访问")
    a = ap.parse_args()

    host = "0.0.0.0" if a.lan else "127.0.0.1"
    os.makedirs(OUT_DIR, exist_ok=True)

    # 开启点餐台：读 MCP 缓存（最近门店 + 最新营养），覆盖 CATALOG
    import mcp_cache
    st = mcp_cache.store()
    changed = mcp_cache.refresh_catalog()
    print("麦当劳点餐台原型已启动")
    if st:
        print(f"  门店： {st['storeName']}（{st['distance']}m，"
              f"{st.get('businessStartTime','')}-{st.get('businessEndTime','')}）"
              f" · 数据同步于 {mcp_cache.synced_at()}")
    else:
        print("  门店： 无 MCP 缓存，使用本地快照（data/mcp_cache.json）")
    if changed:
        print(f"  营养更新：{len(changed)} 处按 MCP 最新值覆盖：")
        for r in changed:
            print(f"    {r['name']}({r['code']}) {r['field']}: {r['old']} -> {r['new']}")
    else:
        print("  营养更新：0 处（与 MCP 缓存一致）")

    srv = ThreadingHTTPServer((host, a.port), Handler)
    print(f"  本机： http://127.0.0.1:{a.port}")
    if a.lan:
        print(f"  手机： http://{_lan_ip()}:{a.port}  （需同一 WiFi）")
    print("  Ctrl+C 停止")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
