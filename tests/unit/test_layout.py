from android_mcp.tree.views import LayoutNode, BoundingBox


def test_layout_node_creation():
    node = LayoutNode(
        class_name="android.widget.TextView",
        resource_id="title",
        bounds=BoundingBox(x1=0, y1=0, x2=100, y2=50),
        text="Hello",
        content_desc="",
        enabled=True,
        visible=True,
        clickable=False,
        focused=False,
        checked=False,
        scrollable=False,
        depth=0,
        children=(),
    )
    assert node.class_name == "android.widget.TextView"
    assert node.text == "Hello"
    assert node.depth == 0
    assert node.children == ()


def test_layout_node_is_frozen():
    node = LayoutNode(
        class_name="android.widget.TextView",
        resource_id="",
        bounds=BoundingBox(x1=0, y1=0, x2=100, y2=50),
        text="",
        content_desc="",
        enabled=True,
        visible=True,
        clickable=False,
        focused=False,
        checked=False,
        scrollable=False,
        depth=0,
        children=(),
    )
    try:
        node.text = "changed"
        assert False, "Should have raised"
    except AttributeError:
        pass


def test_layout_node_with_children():
    child = LayoutNode(
        class_name="android.widget.TextView",
        resource_id="child",
        bounds=BoundingBox(x1=10, y1=10, x2=90, y2=40),
        text="child text",
        content_desc="",
        enabled=True,
        visible=True,
        clickable=False,
        focused=False,
        checked=False,
        scrollable=False,
        depth=1,
        children=(),
    )
    parent = LayoutNode(
        class_name="android.widget.FrameLayout",
        resource_id="container",
        bounds=BoundingBox(x1=0, y1=0, x2=100, y2=50),
        text="",
        content_desc="",
        enabled=True,
        visible=True,
        clickable=False,
        focused=False,
        checked=False,
        scrollable=False,
        depth=0,
        children=(child,),
    )
    assert len(parent.children) == 1
    assert parent.children[0].text == "child text"
