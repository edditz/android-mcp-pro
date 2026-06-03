import threading
import urllib.request
import json
import time
import pytest

from android_mcp.device_picker import pick_device, _build_html


def test_pick_device_returns_selected_serial():
    """Simulate a user selecting a device by POSTing to /select."""
    devices = [("R5CT1234567", "device"), ("192.168.1.100:5555", "device")]

    def simulate_user_selection(port):
        time.sleep(0.3)
        data = json.dumps({"serial": "R5CT1234567"}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/select",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req)

    result = [None]
    port_holder = [None]

    def run_picker():
        result[0] = pick_device(devices, timeout=5, open_browser=False, port_callback=port_holder.append)

    t = threading.Thread(target=run_picker)
    t.start()

    deadline = time.monotonic() + 3
    while not port_holder[1:] and time.monotonic() < deadline:
        time.sleep(0.05)

    port = port_holder[1]
    simulate_user_selection(port)
    t.join(timeout=5)

    assert result[0] == "R5CT1234567"


def test_pick_device_timeout():
    """pick_device raises TimeoutError when no selection is made."""
    devices = [("device1", "device"), ("device2", "device")]
    with pytest.raises(TimeoutError, match="timed out"):
        pick_device(devices, timeout=1, open_browser=False)


def test_build_html_injects_devices():
    """HTML template has __DEVICES__ replaced with JSON array."""
    devices = [("ABC123", "device"), ("10.0.0.1:5555", "device")]
    html = _build_html(devices)
    assert "__DEVICES__" not in html
    assert '"ABC123"' in html
    assert '"10.0.0.1:5555"' in html


from android_mcp.device_picker import save_last_device, load_last_device, clear_last_device


def test_save_and_load_last_device(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    # Force re-evaluation of Path.home() by patching the module-level vars
    import android_mcp.device_picker as dp
    monkeypatch.setattr(dp, "_CONFIG_DIR", tmp_path / ".android-mcp-pro")
    monkeypatch.setattr(dp, "_LAST_DEVICE_FILE", tmp_path / ".android-mcp-pro" / "last-device")

    save_last_device("R5CT1234567")
    assert load_last_device() == "R5CT1234567"


def test_load_last_device_missing(tmp_path, monkeypatch):
    import android_mcp.device_picker as dp
    monkeypatch.setattr(dp, "_CONFIG_DIR", tmp_path / ".android-mcp-pro")
    monkeypatch.setattr(dp, "_LAST_DEVICE_FILE", tmp_path / ".android-mcp-pro" / "last-device")

    assert load_last_device() is None


def test_clear_last_device(tmp_path, monkeypatch):
    import android_mcp.device_picker as dp
    monkeypatch.setattr(dp, "_CONFIG_DIR", tmp_path / ".android-mcp-pro")
    monkeypatch.setattr(dp, "_LAST_DEVICE_FILE", tmp_path / ".android-mcp-pro" / "last-device")

    save_last_device("R5CT1234567")
    clear_last_device()
    assert load_last_device() is None


def test_is_device_alive_true():
    """Device is alive when serial appears in adb devices with state 'device'."""
    from android_mcp.__main__ import _is_device_alive
    from unittest.mock import patch

    with patch("android_mcp.mobile.service.Mobile.list_devices", return_value=[("ABC123", "device"), ("DEF456", "device")]):
        assert _is_device_alive("ABC123") is True


def test_is_device_alive_false():
    """Device is not alive when serial is missing from adb devices."""
    from android_mcp.__main__ import _is_device_alive
    from unittest.mock import patch

    with patch("android_mcp.mobile.service.Mobile.list_devices", return_value=[("OTHER", "device")]):
        assert _is_device_alive("ABC123") is False


def test_is_device_alive_offline():
    """Device is not alive when state is not 'device' (e.g. 'offline')."""
    from android_mcp.__main__ import _is_device_alive
    from unittest.mock import patch

    with patch("android_mcp.mobile.service.Mobile.list_devices", return_value=[("ABC123", "offline")]):
        assert _is_device_alive("ABC123") is False
