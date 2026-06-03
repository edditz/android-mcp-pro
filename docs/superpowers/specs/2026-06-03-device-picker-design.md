# Device Picker — Design Spec

## Overview

When the MCP server starts without a user-specified device and multiple Android devices are connected, a local web page pops up for the user to select which device to connect. Single-device scenarios auto-select silently.

## Trigger Conditions

| Condition | Behavior |
|-----------|----------|
| User specified device (CLI/env/MCP config) | Normal connection, no picker |
| No config + 0 devices | RuntimeError (existing behavior) |
| No config + 1 device | Auto-select the only device |
| No config + 2+ devices | Launch device picker web page |

## Startup Flow

```
MCP server starts
  → _resolve_target()
    ├─ Config present → target, source="config"
    └─ No config → check last-device file
          ├─ File exists + serial online → use it, source="auto"
          ├─ File exists + serial offline → ignore, continue
          └─ File absent → continue
       → list_devices()
          ├─ 0 online → RuntimeError
          ├─ 1 online → auto-select, source="auto", save to last-device
          └─ 2+ online → pick_device() blocks, source="picker", save to last-device
```

## Runtime Reconnection

```
require_device()
  ├─ Connected + alive → return device
  ├─ Connected + dead + source="config" → RuntimeError
  └─ Connected + dead + source="auto"/"picker"
       → disconnect, clear last-device, re-run selection flow
```

## Module Structure

### New file: `src/android_mcp/device_picker.py`

```python
def pick_device(devices: list[tuple[str, str]], timeout: int = 60) -> str:
    """
    Launch a local HTTP page for the user to select a device.

    Args:
        devices: [(serial, state), ...] from adb devices
        timeout: seconds before TimeoutError

    Returns:
        Selected device serial

    Raises:
        TimeoutError: user did not select within timeout
    """
```

Internal implementation:
- `http.server.HTTPServer` on `127.0.0.1:0` (random port)
- `_PickerHandler` with GET / (HTML page) and POST /select (receive selection)
- `webbrowser.open()` to launch browser
- Blocking loop with `time.monotonic()` deadline
- Server cleanup on exit (success or timeout)

### Modified file: `src/android_mcp/__main__.py`

- `_connect_preferred_device()` gains multi-device selection logic
- New module-level `_device_source: Literal["config", "auto", "picker"] | None`
- `require_device()` gains alive-check + reconnection logic

### Persistence: `~/.android-mcp-pro/last-device`

- Plain text file containing one serial string
- Written after auto-select or picker selection
- NOT written for config-specified devices
- Cleared on reconnection failure before re-selection

## HTTP Server Details

| Aspect | Decision |
|--------|----------|
| Framework | stdlib `http.server` |
| Bind address | `127.0.0.1:0` |
| Routes | GET / → HTML page, POST /select → receive JSON |
| Browser launch | `webbrowser.open()` |
| Timeout | 60 seconds, then TimeoutError |
| Logging | Silenced (no stderr pollution) |

## Web Page Design

- Single-page HTML with inline CSS/JS, no external dependencies
- Light theme (`#f5f5f7` background, white cards)
- Device cards show: serial (monospace) + connection type (USB/WiFi)
- WiFi detection: serial contains `:`
- Icons: CSS SVG — blue for WiFi, amber for USB
- Click/Enter/Space to select → POST `/select` with `{serial}`
- Success state: green checkmark + "Connected" message
- Keyboard accessible (tab navigation, focus styles)
- Template in `device_picker_template.html`, injected via `__DEVICES__` placeholder

## Device Source Tracking

```python
_device_source: Literal["config", "auto", "picker"] | None = None
```

- `"config"` — user specified via CLI arg, env var, or MCP user_config. Failure = hard error.
- `"auto"` — single device auto-selected or restored from last-device file. Failure = re-select.
- `"picker"` — user chose via web page. Failure = re-select.

## Alive Check

Called in `require_device()` before returning the device:
- Run `adb devices`, check if current serial appears with state `device`
- If not present or state != `device` → treat as disconnected

## Dependencies

No new dependencies. Uses only:
- `http.server` (stdlib)
- `json` (stdlib)
- `webbrowser` (stdlib)
- `time` (stdlib)
- `pathlib` (stdlib)
- `threading` (stdlib, for server timeout handling)

## Files Changed

| File | Change |
|------|--------|
| `src/android_mcp/device_picker.py` | New — picker logic + HTTP server |
| `src/android_mcp/device_picker_template.html` | New — HTML template |
| `src/android_mcp/__main__.py` | Modified — selection flow + reconnection |
| `tests/unit/test_device_picker.py` | New — unit tests |
