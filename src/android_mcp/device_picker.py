from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Callable, Optional
import json
import threading
import time
import webbrowser

_TEMPLATE_PATH = Path(__file__).parent / "device_picker_template.html"

_CONFIG_DIR = Path.home() / ".android-mcp-pro"
_LAST_DEVICE_FILE = _CONFIG_DIR / "last-device"


def save_last_device(serial: str) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _LAST_DEVICE_FILE.write_text(serial, encoding="utf-8")


def load_last_device() -> Optional[str]:
    try:
        content = _LAST_DEVICE_FILE.read_text(encoding="utf-8").strip()
        return content or None
    except FileNotFoundError:
        return None


def clear_last_device() -> None:
    try:
        _LAST_DEVICE_FILE.unlink()
    except FileNotFoundError:
        pass


def _build_html(
    devices: list[tuple[str, str]],
    current_device: Optional[str] = None,
    context: str = "startup",
) -> str:
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    device_list = [{"serial": serial} for serial, _ in devices]
    html = template.replace("__DEVICES__", json.dumps(device_list))
    html = html.replace("__CURRENT_DEVICE__", current_device or "")
    html = html.replace("__CONTEXT__", context)
    return html


def pick_device(
    devices: list[tuple[str, str]],
    timeout: int = 120,
    open_browser: bool = True,
    port_callback: Optional[Callable[[int], None]] = None,
    current_device: Optional[str] = None,
    refresh_devices: Optional[Callable[[], list[tuple[str, str]]]] = None,
    context: str = "startup",
) -> str:
    selected: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            current_list = refresh_devices() if refresh_devices else devices
            html = _build_html(current_list, current_device=current_device, context=context)
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
            elif self.path == "/devices":
                current_list = refresh_devices() if refresh_devices else devices
                device_list = [{"serial": s} for s, _ in current_list]
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(device_list).encode("utf-8"))
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


def run_picker_background(
    devices: list[tuple[str, str]],
    current_device: str,
    on_switch: Callable[[str], None],
    refresh_devices: Optional[Callable[[], list[tuple[str, str]]]] = None,
) -> None:
    """Launch the picker web page in a background thread (non-blocking).

    The page shows the current device as connected and allows switching.
    When the user selects a different device, `on_switch(serial)` is called.
    Selecting the same device just closes the page (no callback).
    """

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            html = _build_html(devices, current_device=current_device)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def do_POST(self):
            if self.path == "/select":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                serial = body.get("serial", "")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
                if serial and serial != current_device:
                    on_switch(serial)
                server.shutdown()
            elif self.path == "/devices":
                current_list = refresh_devices() if refresh_devices else devices
                device_list = [{"serial": s} for s, _ in current_list]
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(device_list).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]

    webbrowser.open(f"http://127.0.0.1:{port}")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
