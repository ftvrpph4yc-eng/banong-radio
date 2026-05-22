"""HTTP status screen for the Banong Radio demo."""

from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from banong_radio.runtime import PROJECT_ROOT, STATUS_PATH, now_iso, read_status


WEB_ROOT = PROJECT_ROOT / "web"


def dashboard_url(host: str, port: int) -> str:
    shown_host = "127.0.0.1" if host in {"", "0.0.0.0", "::"} else host
    return f"http://{shown_host}:{port}/"


def serve_status_screen(host: str = "127.0.0.1", port: int = 8765) -> None:
    handler = make_status_handler(WEB_ROOT)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Banong Radio status screen: {dashboard_url(host, port)}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def make_status_handler(web_root: Path) -> type[SimpleHTTPRequestHandler]:
    class StatusHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(web_root), **kwargs)

        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] == "/status.json":
                self._send_status()
                return
            if self.path == "/":
                self.path = "/status_screen.html"
            super().do_GET()

        def do_HEAD(self) -> None:
            if self.path == "/":
                self.path = "/status_screen.html"
            super().do_HEAD()

        def _send_status(self) -> None:
            try:
                payload = read_status()
                payload.setdefault("status_path", str(STATUS_PATH))
            except Exception as exc:
                payload = {
                    "ok": False,
                    "mode": "error",
                    "error": str(exc),
                    "status_path": str(STATUS_PATH),
                    "updated_at": now_iso(),
                }

            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return StatusHandler
