from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Callable, Optional
import json
import time
import webbrowser

_TEMPLATE_PATH = Path(__file__).parent / "device_picker_template.html"


def _build_html(devices: list[tuple[str, str]]) -> str:
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    device_list = [{"serial": serial} for serial, _ in devices]
    return template.replace("__DEVICES__", json.dumps(device_list))


def pick_device(
    devices: list[tuple[str, str]],
    timeout: int = 60,
    open_browser: bool = True,
    port_callback: Optional[Callable[[int], None]] = None,
) -> str:
    selected: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            html = _build_html(devices)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def do_POST(self):
            if self.path == "/select":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                serial = body.get("serial", "")
                if serial:
                    selected.append(serial)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]

    if port_callback:
        port_callback(port)

    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{port}")

    deadline = time.monotonic() + timeout
    try:
        while not selected:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"Device selection timed out after {timeout}s. "
                    "No device was selected in the browser."
                )
            server.timeout = min(remaining, 1.0)
            server.handle_request()
    finally:
        server.server_close()

    return selected[0]
