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


def test_get_layout_tree_basic():
    """Test parsing a simple XML hierarchy into LayoutNode tree."""
    from android_mcp.tree.service import Tree

    xml = """\
    <hierarchy>
      <node class="android.widget.FrameLayout" resource-id="root"
            bounds="[0,0][100,200]" enabled="true" visible-to-user="true"
            clickable="false" focused="false" checked="false"
            scrollable="false" text="" content-desc="">
        <node class="android.widget.TextView" resource-id="title"
              bounds="[10,10][90,40]" enabled="true" visible-to-user="true"
              clickable="false" focused="false" checked="false"
              scrollable="false" text="Hello" content-desc=""/>
      </node>
    </hierarchy>"""

    tree = Tree(mobile=None)
    root = tree.get_layout_tree(xml_data=xml)

    assert root is not None
    assert root.class_name == "android.widget.FrameLayout"
    assert root.resource_id == "root"
    assert root.depth == 0
    assert len(root.children) == 1
    assert root.children[0].text == "Hello"
    assert root.children[0].depth == 1


def test_get_layout_tree_max_depth():
    """Test that max_depth truncates deeper nodes."""
    from android_mcp.tree.service import Tree

    xml = """\
    <hierarchy>
      <node class="android.widget.FrameLayout" resource-id="l0"
            bounds="[0,0][100,200]" enabled="true" visible-to-user="true"
            clickable="false" focused="false" checked="false"
            scrollable="false" text="" content-desc="">
        <node class="android.widget.FrameLayout" resource-id="l1"
              bounds="[0,0][100,200]" enabled="true" visible-to-user="true"
              clickable="false" focused="false" checked="false"
              scrollable="false" text="" content-desc="">
          <node class="android.widget.TextView" resource-id="l2"
                bounds="[10,10][90,40]" enabled="true" visible-to-user="true"
                clickable="false" focused="false" checked="false"
                scrollable="false" text="deep" content-desc=""/>
        </node>
      </node>
    </hierarchy>"""

    tree = Tree(mobile=None)
    root = tree.get_layout_tree(xml_data=xml, max_depth=1)

    assert root is not None
    assert root.depth == 0
    assert len(root.children) == 1
    assert root.children[0].depth == 1
    assert root.children[0].children == ()


def test_format_layout_tree():
    """Test formatting LayoutNode tree as indented text."""
    from android_mcp.tree.service import Tree

    xml = """\
    <hierarchy>
      <node class="android.widget.FrameLayout" resource-id="root"
            bounds="[0,0][100,200]" enabled="true" visible-to-user="true"
            clickable="false" focused="false" checked="false"
            scrollable="false" text="" content-desc="">
        <node class="android.widget.TextView" resource-id="title"
              bounds="[10,10][90,40]" enabled="true" visible-to-user="true"
              clickable="true" focused="false" checked="false"
              scrollable="false" text="Hello" content-desc=""/>
      </node>
    </hierarchy>"""

    tree = Tree(mobile=None)
    root = tree.get_layout_tree(xml_data=xml)
    output = Tree.format_layout_tree(root)

    assert "FrameLayout" in output
    assert "TextView" in output
    assert "text=Hello" in output
    assert "clickable=true" in output
    assert "id=root" in output
    # Check indentation: child should be indented
    lines = output.strip().split('\n')
    assert lines[0].startswith('[0]')
    assert lines[1].startswith('  [1]')
