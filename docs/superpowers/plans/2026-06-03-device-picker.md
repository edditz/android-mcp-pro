# Device Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local web-based device picker that launches when multiple devices are connected and no device is specified in config.

**Architecture:** New `device_picker.py` module with a blocking HTTP server + HTML page. Startup flow in `__main__.py` gains multi-device detection, persistence via `~/.android-mcp-pro/last-device`, and reconnection logic with source tracking.

**Tech Stack:** Python stdlib only (`http.server`, `webbrowser`, `json`, `pathlib`, `time`)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/android_mcp/device_picker.py` | Create | HTTP server, `pick_device()` function, HTML template loading |
| `src/android_mcp/device_picker_template.html` | Exists | HTML/CSS/JS page template (already committed) |
| `src/android_mcp/__main__.py` | Modify | Device source tracking, startup selection logic, reconnection |
| `tests/unit/test_device_picker.py` | Create | Unit tests for picker module |

---

### Task 1: Create `device_picker.py` with `pick_device()` function

**Files:**
- Create: `src/android_mcp/device_picker.py`
- Test: `tests/unit/test_device_picker.py`

- [ ] **Step 1: Write failing test for `pick_device` with simulated POST**

```python
# tests/unit/test_device_picker.py
import threading
import urllib.request
import json
import pytest

from android_mcp.device_picker import pick_device, _build_html


def test_pick_device_returns_selected_serial():
    """Simulate a user selecting a device by POSTing to /select."""
    devices = [("R5CT1234567", "device"), ("192.168.1.100:5555", "device")]

    def simulate_user_selection(port):
        import time
        time.sleep(0.3)
        data = json.dumps({"serial": "R5CT1234567"}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/select",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req)

    # Run pick_device in a thread so we can POST to it
    result = [None]
    port_holder = [None]

    def run_picker():
        result[0] = pick_device(devices, timeout=5, open_browser=False, port_callback=port_holder.append)

    t = threading.Thread(target=run_picker)
    t.start()

    # Wait for port_callback to fire
    import time
    deadline = time.monotonic() + 3
    while not port_holder[1:] and time.monotonic() < deadline:
        time.sleep(0.05)

    port = port_holder[1]
    simulate_user_selection(port)
    t.join(timeout=5)

    assert result[0] == "R5CT1234567"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_device_picker.py::test_pick_device_returns_selected_serial -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'android_mcp.device_picker'`

- [ ] **Step 3: Write `device_picker.py` implementation**

```python
# src/android_mcp/device_picker.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_device_picker.py::test_pick_device_returns_selected_serial -v`
Expected: PASS

- [ ] **Step 5: Write test for timeout behavior**

```python
# append to tests/unit/test_device_picker.py

def test_pick_device_timeout():
    """pick_device raises TimeoutError when no selection is made."""
    devices = [("device1", "device"), ("device2", "device")]
    with pytest.raises(TimeoutError, match="timed out"):
        pick_device(devices, timeout=1, open_browser=False)
```

- [ ] **Step 6: Run timeout test**

Run: `uv run pytest tests/unit/test_device_picker.py::test_pick_device_timeout -v`
Expected: PASS (TimeoutError raised after ~1s)

- [ ] **Step 7: Write test for `_build_html`**

```python
# append to tests/unit/test_device_picker.py

def test_build_html_injects_devices():
    """HTML template has __DEVICES__ replaced with JSON array."""
    devices = [("ABC123", "device"), ("10.0.0.1:5555", "device")]
    html = _build_html(devices)
    assert "__DEVICES__" not in html
    assert '"ABC123"' in html
    assert '"10.0.0.1:5555"' in html
```

- [ ] **Step 8: Run all picker tests**

Run: `uv run pytest tests/unit/test_device_picker.py -v`
Expected: All 3 tests PASS

- [ ] **Step 9: Commit**

```bash
git add src/android_mcp/device_picker.py tests/unit/test_device_picker.py
git commit -m "feat: add device_picker module with HTTP-based device selection"
```

---

### Task 2: Add persistence helpers (`last-device` file)

**Files:**
- Modify: `src/android_mcp/device_picker.py` (add persistence functions)
- Test: `tests/unit/test_device_picker.py` (add persistence tests)

- [ ] **Step 1: Write failing tests for persistence**

```python
# append to tests/unit/test_device_picker.py

from android_mcp.device_picker import save_last_device, load_last_device, clear_last_device


def test_save_and_load_last_device(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    save_last_device("R5CT1234567")
    assert load_last_device() == "R5CT1234567"


def test_load_last_device_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert load_last_device() is None


def test_clear_last_device(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    save_last_device("R5CT1234567")
    clear_last_device()
    assert load_last_device() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_device_picker.py::test_save_and_load_last_device -v`
Expected: FAIL with `ImportError: cannot import name 'save_last_device'`

- [ ] **Step 3: Implement persistence functions**

Add to `src/android_mcp/device_picker.py`:

```python
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
```

- [ ] **Step 4: Run persistence tests**

Run: `uv run pytest tests/unit/test_device_picker.py -k "last_device" -v`
Expected: All 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/android_mcp/device_picker.py tests/unit/test_device_picker.py
git commit -m "feat: add last-device persistence helpers"
```

---

### Task 3: Integrate device picker into `__main__.py` startup flow

**Files:**
- Modify: `src/android_mcp/__main__.py`
- Test: `tests/unit/test_device_picker.py` (integration-style test)

- [ ] **Step 1: Write test for startup selection logic**

```python
# append to tests/unit/test_device_picker.py
from unittest.mock import patch, MagicMock
from android_mcp.device_picker import load_last_device, save_last_device


def test_auto_selects_single_device(tmp_path, monkeypatch):
    """When only one device is connected and no config, auto-select it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Clear any env config
    monkeypatch.delenv("ANDROID_MCP_DEVICE", raising=False)
    monkeypatch.delenv("ANDROID_MCP_CONNECTION", raising=False)

    from android_mcp import __main__ as main_mod

    with patch.object(main_mod, "mobile") as mock_mobile:
        mock_mobile.is_connected = False
        with patch("android_mcp.mobile.service.Mobile.list_devices", return_value=[("SINGLE123", "device")]):
            with patch.object(main_mod, "_configured_preference") as mock_pref:
                mock_pref.return_value = main_mod.DevicePreference(connection="auto", serial=None, source="auto-detect")
                with patch.object(main_mod, "_pick_auto_device", return_value="SINGLE123"):
                    main_mod._connect_preferred_device()
                    mock_mobile.connect.assert_called_with("SINGLE123")
```

- [ ] **Step 2: Run test to verify current behavior**

Run: `uv run pytest tests/unit/test_device_picker.py::test_auto_selects_single_device -v`
Expected: PASS (this tests existing auto-select behavior which already works)

- [ ] **Step 3: Add `_device_source` tracking and multi-device picker to `__main__.py`**

In `src/android_mcp/__main__.py`, add after imports:

```python
from android_mcp.device_picker import pick_device, save_last_device, load_last_device, clear_last_device
```

Add module-level source tracking (after `mobile = Mobile()` line):

```python
_device_source: Optional[Literal["config", "auto", "picker"]] = None
```

Replace `_connect_preferred_device()` with:

```python
def _connect_preferred_device() -> None:
    global _device_source

    if mobile.is_connected:
        return

    target = _resolve_target()

    # User explicitly configured a device
    if target.serial and target.source != "auto-detect":
        serial = target.serial
        if target.connection == "wifi" or ":" in serial:
            serial = Mobile.normalize_wifi_serial(serial)
            Mobile.adb_connect(serial)
        mobile.connect(serial)
        _device_source = "config"
        return

    # No explicit config — check last-device file
    if target.source == "auto-detect":
        last = load_last_device()
        if last:
            devices = Mobile.list_devices()
            online_serials = [s for s, st in devices if st == "device"]
            if last in online_serials:
                if ":" in last:
                    Mobile.adb_connect(last)
                mobile.connect(last)
                _device_source = "auto"
                return

    # Auto-detect: count online devices
    devices = Mobile.list_devices()
    online = [(s, st) for s, st in devices if st == "device"]

    if not online:
        raise RuntimeError(_not_configured_message())

    if len(online) == 1:
        serial = online[0][0]
        if ":" in serial:
            Mobile.adb_connect(serial)
        mobile.connect(serial)
        save_last_device(serial)
        _device_source = "auto"
        return

    # Multiple devices — launch picker
    serial = pick_device(online)
    if ":" in serial:
        Mobile.adb_connect(serial)
    mobile.connect(serial)
    save_last_device(serial)
    _device_source = "picker"
```

- [ ] **Step 4: Run full test suite to check nothing is broken**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/android_mcp/__main__.py
git commit -m "feat: integrate device picker into startup flow with source tracking"
```

---

### Task 4: Add reconnection logic to `require_device()`

**Files:**
- Modify: `src/android_mcp/__main__.py`
- Test: `tests/unit/test_device_picker.py`

- [ ] **Step 1: Write failing test for reconnection on config device**

```python
# append to tests/unit/test_device_picker.py

def test_require_device_raises_on_config_device_disconnect(tmp_path, monkeypatch):
    """Config-specified device that disconnects should raise RuntimeError."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from android_mcp import __main__ as main_mod

    main_mod._device_source = "config"
    mock_device = MagicMock()

    with patch.object(main_mod, "mobile") as mock_mobile:
        mock_mobile.is_connected = True
        mock_mobile.get_device.return_value = mock_device
        mock_device.serial = "DEADBEEF"
        # Device not in adb devices list anymore
        with patch("android_mcp.mobile.service.Mobile.list_devices", return_value=[]):
            with pytest.raises(RuntimeError, match="not connected"):
                main_mod.require_device()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_device_picker.py::test_require_device_raises_on_config_device_disconnect -v`
Expected: FAIL (current `require_device()` doesn't check liveness)

- [ ] **Step 3: Implement reconnection logic**

Replace `require_device()` in `src/android_mcp/__main__.py`:

```python
def _is_device_alive(serial: str) -> bool:
    devices = Mobile.list_devices()
    online_serials = [s for s, st in devices if st == "device"]
    return serial in online_serials


def require_device():
    global _device_source

    if mobile.is_connected:
        device = mobile.get_device()
        serial = getattr(device, "serial", None) or getattr(device, "_serial", None)
        if serial and not _is_device_alive(serial):
            mobile.disconnect()
            if _device_source == "config":
                raise RuntimeError(
                    f"Configured device '{serial}' is not connected."
                    + _format_available_devices()
                )
            clear_last_device()
            _device_source = None
        else:
            return device

    _connect_preferred_device()
    return mobile.get_device()
```

- [ ] **Step 4: Run reconnection test**

Run: `uv run pytest tests/unit/test_device_picker.py::test_require_device_raises_on_config_device_disconnect -v`
Expected: PASS

- [ ] **Step 5: Write test for auto/picker reconnection**

```python
# append to tests/unit/test_device_picker.py

def test_require_device_reconnects_on_auto_device_disconnect(tmp_path, monkeypatch):
    """Auto-selected device that disconnects should re-trigger selection."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from android_mcp import __main__ as main_mod

    main_mod._device_source = "auto"
    mock_device = MagicMock()

    with patch.object(main_mod, "mobile") as mock_mobile:
        mock_mobile.is_connected = True
        mock_mobile.get_device.return_value = mock_device
        mock_device.serial = "OLD_DEVICE"

        # First call: device is dead
        # After disconnect + reconnect: new device available
        call_count = [0]
        def list_devices_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return []  # old device gone
            return [("NEW_DEVICE", "device")]  # new device available

        with patch("android_mcp.mobile.service.Mobile.list_devices", side_effect=list_devices_side_effect):
            with patch.object(main_mod, "_connect_preferred_device") as mock_connect:
                main_mod.require_device()
                mock_mobile.disconnect.assert_called_once()
                mock_connect.assert_called_once()
```

- [ ] **Step 6: Run all tests**

Run: `uv run pytest tests/unit/test_device_picker.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/android_mcp/__main__.py tests/unit/test_device_picker.py
git commit -m "feat: add device liveness check and reconnection logic"
```

---

### Task 5: Final integration test and cleanup

**Files:**
- Modify: `src/android_mcp/__main__.py` (ensure import order is clean)
- Test: full test suite

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Verify HTML template is loadable**

```python
# append to tests/unit/test_device_picker.py

def test_template_file_exists_and_loadable():
    """The HTML template file should exist and contain the __DEVICES__ placeholder."""
    from android_mcp.device_picker import _TEMPLATE_PATH
    assert _TEMPLATE_PATH.exists()
    content = _TEMPLATE_PATH.read_text()
    assert "__DEVICES__" in content
    assert "select" in content.lower()
```

- [ ] **Step 3: Run final test**

Run: `uv run pytest tests/unit/test_device_picker.py::test_template_file_exists_and_loadable -v`
Expected: PASS

- [ ] **Step 4: Run full suite one final time**

Run: `uv run pytest tests/ -v`
Expected: All PASS, no regressions

- [ ] **Step 5: Final commit (if any cleanup needed)**

```bash
git add -A
git commit -m "test: add device picker integration tests"
```
