from android_mcp.layout.accessibility_provider import AccessibilityProvider

SAMPLE_XML = """<?xml version='1.0' encoding='UTF-8'?>
<hierarchy rotation="0">
  <node class="android.widget.FrameLayout" resource-id="com.x:id/root" bounds="[0,0][1080,1920]" enabled="true" visible-to-user="true" clickable="false" focused="false" checked="false" scrollable="false" text="" content-desc="">
    <node class="android.widget.TextView" resource-id="com.x:id/title" bounds="[0,0][1080,100]" enabled="true" visible-to-user="true" clickable="true" focused="false" checked="false" scrollable="false" text="Hello" content-desc="" />
  </node>
</hierarchy>"""


class FakeDevice:
    def __init__(self): self.info = {"displayWidth": 1080, "displaySizeDpX": 360}
    def dump_hierarchy(self): return SAMPLE_XML
    def app_current(self): return {"package": "com.x", "activity": ".MainActivity"}


class FakeMobile:
    def __init__(self): self.device = FakeDevice()


def test_get_layout_tree_includes_container_and_child():
    prov = AccessibilityProvider(FakeMobile())
    out = prov.get_layout_tree()
    assert "FrameLayout" in out
    assert "TextView" in out
    assert "Hello" in out


def test_get_layout_tree_includes_window_header():
    prov = AccessibilityProvider(FakeMobile())
    out = prov.get_layout_tree()
    header = out.splitlines()[0]
    assert header.startswith("[window]")
    assert "package=com.x" in header
    assert "activity=.MainActivity" in header


def test_get_layout_tree_filter_class():
    prov = AccessibilityProvider(FakeMobile())
    out = prov.get_layout_tree(filter_class="TextView")
    assert "TextView" in out
    # The filter keeps ancestor containers that have matching descendants,
    # so FrameLayout appears as a wrapper around the matching TextView child.
    assert "Hello" in out


def test_get_layout_tree_filter_class_no_match():
    prov = AccessibilityProvider(FakeMobile())
    out = prov.get_layout_tree(filter_class="RecyclerView")
    assert out == "No elements matching class 'RecyclerView' found."


def test_get_element_details_rejects_invalid_selector():
    prov = AccessibilityProvider(FakeMobile())
    result = prov.get_element_details("xpath", "//button")
    assert "Invalid selector_type" in result
    assert "xpath" in result
