import json
import pytest
from android_mcp.layout.jdwp_provider import JdwpProvider, _json_to_node
from android_mcp.layout import jdwp_runner

NODE = {
    "class": "android.widget.TextView", "hash": "abc", "resourceId": "title",
    "bounds": [61, 2427, 1139, 2598], "text": "标题",
    "properties": {"paddingLeft": 48, "paddingTop": 24, "paddingRight": 48,
                   "paddingBottom": 0, "elevation": 4.0, "textSize": 42.0},
    "children": [
        {"class": "android.widget.ImageView", "hash": "def", "resourceId": "icon",
         "bounds": [0, 0, 100, 100], "text": "", "properties": {}, "children": []}
    ],
}
DUMP = {"ok": True, "protocol": "V1", "package": "com.x", "window": "w", "root": NODE}


class FakeDevice:
    def __init__(self): self.info = {"displayWidth": 1080, "displaySizeDpX": 360}
    def app_current(self): return {"package": "com.x"}


class FakeMobile:
    def __init__(self): self.device = FakeDevice()
    def get_device(self): return self.device


def make_provider(monkeypatch, dump=DUMP):
    monkeypatch.setattr(jdwp_runner, "run_deep_dump", lambda *a, **k: dump)
    return JdwpProvider(FakeMobile(), jar_path="/x.jar", adb_path="adb", serial="s")


def test_json_to_node_recursive():
    root = _json_to_node(NODE, depth=0)
    assert root.class_name == "android.widget.TextView"
    assert root.children[0].class_name == "android.widget.ImageView"
    assert root.children[0].depth == 1


def test_get_layout_tree_renders(monkeypatch):
    prov = make_provider(monkeypatch)
    out = prov.get_layout_tree()
    assert "TextView" in out and "ImageView" in out
    assert "padding=[48,24,48,0]" in out
    assert "textSize=42.0dp" in out


def test_get_layout_tree_filter_class(monkeypatch):
    prov = make_provider(monkeypatch)
    out = prov.get_layout_tree(filter_class="ImageView")
    assert "ImageView" in out
    assert "TextView" not in out


def test_get_element_details_by_resourceid(monkeypatch):
    prov = make_provider(monkeypatch)
    out = prov.get_element_details("resourceId", "title")
    assert "android.widget.TextView" in out
    assert "paddingLeft" in out or "padding=" in out


def test_get_element_details_not_found(monkeypatch):
    prov = make_provider(monkeypatch)
    out = prov.get_element_details("resourceId", "does_not_exist")
    assert "ELEMENT_NOT_FOUND" in out or "not" in out.lower()


def test_deep_error_propagates_as_text(monkeypatch):
    def boom(*a, **k): raise jdwp_runner.DeepDumpError("nope", "NOT_DEBUGGABLE")
    monkeypatch.setattr(jdwp_runner, "run_deep_dump", boom)
    prov = JdwpProvider(FakeMobile(), jar_path="/x.jar", adb_path="adb", serial="s")
    out = prov.get_layout_tree()
    assert "NOT_DEBUGGABLE" in out


def test_real_fixture_parses(monkeypatch):
    with open("tests/fixtures/deep_dump_sample.json") as f:
        dump = json.load(f)
    prov = make_provider(monkeypatch, dump=dump)
    out = prov.get_layout_tree()
    assert "[0]" in out  # at least the root renders
    assert "DecorView" in out
