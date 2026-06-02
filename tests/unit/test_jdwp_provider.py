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
    prov = make_provider(monkeypatch)  # FakeDevice scale = 1080/360 = 3.0
    out = prov.get_layout_tree()
    assert "TextView" in out and "ImageView" in out
    # px values converted to dp with raw px in parens; textSize in sp
    assert "padding=[16,8,16,0]dp ([48,24,48,0]px)" in out
    assert "textSize=14sp (42.0px)" in out


def test_get_layout_tree_header_includes_package_and_window(monkeypatch):
    prov = make_provider(monkeypatch)  # DUMP has package="com.x", window="w"
    out = prov.get_layout_tree()
    header = out.splitlines()[0]
    assert header.startswith("[window]")
    assert "mode=deep" in header
    assert "package=com.x" in header
    assert "window=w" in header


def test_get_layout_tree_filter_retains_ancestors(monkeypatch):
    # tree: FrameLayout(container) > TextView(match). Filtering by TextView must KEEP
    # the FrameLayout ancestor (consistent with AccessibilityProvider).
    tree = {
        "ok": True, "protocol": "V1", "package": "com.x", "window": "w",
        "root": {
            "class": "android.widget.FrameLayout", "hash": "r", "resourceId": "root",
            "bounds": [0, 0, 100, 100], "text": "", "properties": {}, "children": [
                {"class": "android.widget.TextView", "hash": "t", "resourceId": "label",
                 "bounds": [0, 0, 100, 50], "text": "hi", "properties": {}, "children": []}
            ],
        },
    }
    prov = make_provider(monkeypatch, dump=tree)
    out = prov.get_layout_tree(filter_class="TextView")
    assert "TextView" in out
    assert "FrameLayout" in out  # ancestor retained — matches AccessibilityProvider behavior


def test_get_layout_tree_filter_no_match(monkeypatch):
    prov = make_provider(monkeypatch)  # default DUMP (TextView>ImageView)
    out = prov.get_layout_tree(filter_class="RecyclerView")
    assert out == "No elements matching class 'RecyclerView' found."


def test_get_element_details_by_resourceid(monkeypatch):
    prov = make_provider(monkeypatch)
    out = prov.get_element_details("resourceId", "title")
    assert out.startswith("mode: deep")
    assert "android.widget.TextView" in out
    # px props annotated with dp; bounds-derived width/height included (scale 3.0)
    assert "paddingLeft: 16dp (48px)" in out
    assert "textSize: 14sp (42.0px)" in out
    assert "width: " in out and "dp (" in out


def test_get_element_details_text_size_prefers_scaled(monkeypatch):
    # getScaledTextSize() present -> use it for sp (device's own px->sp conversion),
    # not textSize/scale. 52/3 would be 17.3; scaledTextSize is exactly 17.
    node = {**NODE, "properties": {"textSize": 52.0, "scaledTextSize": 17.0}}
    dump = {**DUMP, "root": node}
    prov = make_provider(monkeypatch, dump=dump)
    out = prov.get_element_details("resourceId", "title")
    assert "textSize: 17sp (52.0px)" in out
    # scaledTextSize is consumed into textSize, not emitted as its own raw line
    assert "scaledTextSize:" not in out


def test_get_element_details_not_found(monkeypatch):
    prov = make_provider(monkeypatch)
    out = prov.get_element_details("resourceId", "does_not_exist")
    assert "ELEMENT_NOT_FOUND" in out


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


def test_get_element_details_description_falls_back_to_text(monkeypatch):
    prov = make_provider(monkeypatch)  # default DUMP: TextView text="标题"
    # description lookup with a value that isn't any node's text → not found, with note
    out = prov.get_element_details("description", "no-such-desc")
    assert "ELEMENT_NOT_FOUND" in out
    assert "content-desc" in out  # the explanatory note is present


# Fix A tests
def test_missing_root_field_returns_error(monkeypatch):
    monkeypatch.setattr(jdwp_runner, "run_deep_dump", lambda *a, **k: {"ok": True})  # no "root"
    prov = JdwpProvider(FakeMobile(), jar_path="/x.jar", adb_path="adb", serial="s")
    out = prov.get_layout_tree()
    assert "DUMP_FAILED" in out


def test_app_current_failure_returns_error(monkeypatch):
    class BadDevice:
        def app_current(self): raise RuntimeError("adb lost")
    class BadMobile:
        def get_device(self): return BadDevice()
    monkeypatch.setattr(jdwp_runner, "run_deep_dump", lambda *a, **k: {"ok": True, "root": {}})
    prov = JdwpProvider(BadMobile(), jar_path="/x.jar", adb_path="adb", serial="s")
    out = prov.get_layout_tree()
    assert "DUMP_FAILED" in out


# Fix B test
def test_description_success_includes_note(monkeypatch):
    prov = make_provider(monkeypatch)  # default DUMP: TextView text="标题"
    out = prov.get_element_details("description", "标题")
    assert "matched on text instead" in out
    assert "android.widget.TextView" in out


# Fix E test
def test_no_id_sentinel_becomes_empty(monkeypatch):
    node = {"class": "android.view.View", "hash": "h", "resourceId": "NO_ID",
            "bounds": [0, 0, 1, 1], "text": "", "properties": {}, "children": []}
    dump = {"ok": True, "root": node}
    prov = make_provider(monkeypatch, dump=dump)
    # element lookup for "NO_ID" must NOT match
    out = prov.get_element_details("resourceId", "NO_ID")
    assert "ELEMENT_NOT_FOUND" in out
