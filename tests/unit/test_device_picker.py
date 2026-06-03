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
