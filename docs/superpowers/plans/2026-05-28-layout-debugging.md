# Layout Debugging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add layout data retrieval capabilities to Android-MCP for AI-automated design review.

**Architecture:** Extend the existing tree parsing layer to preserve the full view hierarchy (not just interactive elements), expose it through enhanced Snapshot and two new MCP tools.

**Tech Stack:** Python 3.13, fastmcp, uiautomator2, xml.etree.ElementTree, Pillow

---

## File Structure

| File | Responsibility |
|------|----------------|
| `src/android_mcp/tree/views.py` | Add `LayoutNode` dataclass, extend `TreeState` |
| `src/android_mcp/tree/service.py` | Add `get_layout_tree()` recursive parser |
| `src/android_mcp/mobile/service.py` | Pass `include_layout` through `get_state()` |
| `src/android_mcp/__main__.py` | Enhance Snapshot, add GetLayoutTree + GetElementDetails |
| `tests/unit/test_layout.py` | Unit tests for LayoutNode and tree parsing |

---

### Task 1: Add LayoutNode Data Model

**Files:**
- Modify: `src/android_mcp/tree/views.py`
- Create: `tests/unit/test_layout.py`

- [ ] **Step 1: Create test file and write failing test**

```python
# tests/unit/test_layout.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/eddie/github-projects/Android-MCP
uv run pytest tests/unit/test_layout.py -v
```

Expected: FAIL with `ImportError: cannot import name 'LayoutNode'`

- [ ] **Step 3: Add LayoutNode to tree/views.py**

Add the `LayoutNode` dataclass after `CenterCord` and add `layout_root` field to `TreeState`:

```python
# In tree/views.py, after CenterCord class, add:

@dataclass(frozen=True)
class LayoutNode:
    class_name: str
    resource_id: str
    bounds: BoundingBox
    text: str
    content_desc: str
    enabled: bool
    visible: bool
    clickable: bool
    focused: bool
    checked: bool
    scrollable: bool
    depth: int
    children: tuple['LayoutNode', ...]
```

Also modify `TreeState` to include:

```python
@dataclass
class TreeState:
    interactive_elements: list[ElementNode]
    layout_root: LayoutNode | None = None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_layout.py -v
```

Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/android_mcp/tree/views.py tests/unit/test_layout.py
git commit -m "feat: add LayoutNode dataclass for full view hierarchy"
```

---

### Task 2: Add Layout Tree Parser

**Files:**
- Modify: `src/android_mcp/tree/service.py`
- Modify: `tests/unit/test_layout.py`

- [ ] **Step 1: Write failing test for get_layout_tree**

Append to `tests/unit/test_layout.py`:

```python
from xml.etree import ElementTree


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
    # l1's children should be truncated because max_depth=1
    assert root.children[0].children == ()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_layout.py::test_get_layout_tree_basic tests/unit/test_layout.py::test_get_layout_tree_max_depth -v
```

Expected: FAIL with `AttributeError: 'Tree' object has no attribute 'get_layout_tree'`

- [ ] **Step 3: Implement get_layout_tree in tree/service.py**

Add this method to the `Tree` class in `src/android_mcp/tree/service.py`:

```python
def get_layout_tree(self, xml_data=None, max_depth=10):
    """Parse full view hierarchy into a LayoutNode tree."""
    from android_mcp.tree.views import LayoutNode, BoundingBox

    element_tree = self.get_element_tree(xml_data=xml_data)

    def parse_node(node, depth):
        bounds_match = re.search(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
        if bounds_match:
            x1, y1, x2, y2 = map(int, bounds_match.groups())
            bounds = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
        else:
            bounds = BoundingBox(x1=0, y1=0, x2=0, y2=0)

        raw_id = node.get('resource-id', '')
        short_id = raw_id.split('/')[-1] if '/' in raw_id else raw_id

        children = ()
        if depth < max_depth:
            child_nodes = [parse_node(child, depth + 1) for child in node]
            children = tuple(c for c in child_nodes if c is not None)

        return LayoutNode(
            class_name=node.get('class', ''),
            resource_id=short_id,
            bounds=bounds,
            text=node.get('text', ''),
            content_desc=node.get('content-desc', ''),
            enabled=node.get('enabled', 'false') == 'true',
            visible=node.get('visible-to-user', 'false') == 'true',
            clickable=node.get('clickable', 'false') == 'true',
            focused=node.get('focused', 'false') == 'true',
            checked=node.get('checked', 'false') == 'true',
            scrollable=node.get('scrollable', 'false') == 'true',
            depth=depth,
            children=children,
        )

    return parse_node(element_tree, 0)
```

Also add `import re` at the top of the file if not already present (it is not currently imported).

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_layout.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/android_mcp/tree/service.py tests/unit/test_layout.py
git commit -m "feat: add get_layout_tree recursive parser"
```

---

### Task 3: Add Layout Tree Text Formatter

**Files:**
- Modify: `src/android_mcp/tree/service.py`
- Modify: `tests/unit/test_layout.py`

- [ ] **Step 1: Write failing test for format_layout_tree**

Append to `tests/unit/test_layout.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_layout.py::test_format_layout_tree -v
```

Expected: FAIL with `AttributeError: type object 'Tree' has no attribute 'format_layout_tree'`

- [ ] **Step 3: Implement format_layout_tree**

Add this static method to the `Tree` class:

```python
@staticmethod
def format_layout_tree(root):
    """Format a LayoutNode tree as indented text for AI consumption."""
    lines = []

    def format_node(node, indent=0):
        prefix = "  " * indent
        short_class = node.class_name.split('.')[-1] if '.' in node.class_name else node.class_name
        parts = [f"[{node.depth}] {short_class}  {node.bounds.to_string()}"]

        if node.resource_id:
            parts.append(f"id={node.resource_id}")
        if node.text:
            parts.append(f"text={node.text}")
        if node.content_desc:
            parts.append(f"desc={node.content_desc}")
        if node.clickable:
            parts.append("clickable=true")
        if node.scrollable:
            parts.append("scrollable=true")
        if node.focused:
            parts.append("focused=true")
        if node.checked:
            parts.append("checked=true")

        lines.append(prefix + "  ".join(parts))

        for child in node.children:
            format_node(child, indent + 1)

    format_node(root)
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_layout.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/android_mcp/tree/service.py tests/unit/test_layout.py
git commit -m "feat: add format_layout_tree text formatter"
```

---

### Task 4: Wire Layout Data Through Mobile Service

**Files:**
- Modify: `src/android_mcp/mobile/service.py`

- [ ] **Step 1: Update get_state to accept include_layout parameter**

In `src/android_mcp/mobile/service.py`, modify the `get_state` method signature and body:

```python
def get_state(self, use_vision=False, as_bytes: bool = False, as_base64: bool = False, use_annotation: bool = True, include_layout: bool = False):
    try:
        xml_data, screenshot_data = self.capture_data(use_vision=use_vision)
        tree = Tree(self)
        tree_state = tree.get_state(xml_data=xml_data)

        if include_layout:
            layout_root = tree.get_layout_tree(xml_data=xml_data)
            tree_state.layout_root = layout_root

        if use_vision:
            nodes = tree_state.interactive_elements
            if use_annotation:
                screenshot = tree.annotated_screenshot(nodes=nodes, scale=1.0, screenshot=screenshot_data)
            else:
                screenshot = screenshot_data
            if os.getenv("SCREENSHOT_QUANTIZED") in ["1", "yes", "true", True]:
                screenshot = self.quantized_screenshot(screenshot)

            if as_base64:
                screenshot = self.as_base64(screenshot)
            elif as_bytes:
                screenshot = self.screenshot_in_bytes(screenshot)
        else:
            screenshot = None
        return MobileState(tree_state=tree_state, screenshot=screenshot)
    except Exception as e:
        raise RuntimeError(f"Failed to get device state: {e}")
```

- [ ] **Step 2: Commit**

```bash
git add src/android_mcp/mobile/service.py
git commit -m "feat: add include_layout parameter to get_state"
```

---

### Task 5: Enhance Snapshot Tool

**Files:**
- Modify: `src/android_mcp/__main__.py`

- [ ] **Step 1: Update Snapshot tool definition**

In `src/android_mcp/__main__.py`, replace the existing `state_tool` function:

```python
@mcp.tool(
    name="Snapshot",
    description="Get the state of the device. Optionally includes visual screenshot when use_vision=True. The use_annotation parameter (default True) can be set to False to get a clean screenshot without bounding boxes. Set include_layout=True to get the full view hierarchy tree.",
    annotations=ToolAnnotations(title="Snapshot", readOnlyHint=True),
)
def state_tool(use_vision: bool = False, use_annotation: bool = True, include_layout: bool = False):
    require_device()
    mobile_state = mobile.get_state(
        use_vision=use_vision, use_annotation=use_annotation, as_bytes=True,
        include_layout=include_layout,
    )
    result = [mobile_state.tree_state.to_string()]
    if include_layout and mobile_state.tree_state.layout_root:
        from android_mcp.tree.service import Tree
        result.append(Tree.format_layout_tree(mobile_state.tree_state.layout_root))
    if use_vision:
        result.append(Image(data=mobile_state.screenshot, format="PNG"))
    return result
```

- [ ] **Step 2: Commit**

```bash
git add src/android_mcp/__main__.py
git commit -m "feat: enhance Snapshot with include_layout parameter"
```

---

### Task 6: Add GetLayoutTree Tool

**Files:**
- Modify: `src/android_mcp/__main__.py`

- [ ] **Step 1: Add GetLayoutTree tool after Snapshot**

Insert this new tool definition after the `state_tool` function in `__main__.py`:

```python
@mcp.tool(
    name="GetLayoutTree",
    description="Get the full view hierarchy of the device screen as a tree of all UI elements (including containers like FrameLayout, LinearLayout, etc.). Useful for layout debugging and design review.",
    annotations=ToolAnnotations(title="Get Layout Tree", readOnlyHint=True),
)
def get_layout_tree_tool(max_depth: int = 10, filter_class: str = None):
    require_device()
    xml_data = mobile.device.dump_hierarchy()
    tree = Tree(mobile)
    layout_root = tree.get_layout_tree(xml_data=xml_data, max_depth=max_depth)

    if layout_root is None:
        return "Failed to parse layout tree."

    if filter_class:
        layout_root = _filter_layout_tree(layout_root, filter_class)
        if layout_root is None:
            return f"No elements matching class '{filter_class}' found."

    return Tree.format_layout_tree(layout_root)
```

Also add this helper function before the tool definitions:

```python
def _filter_layout_tree(node, filter_class):
    """Filter layout tree to only include nodes matching the given class name."""
    from android_mcp.tree.views import LayoutNode

    filtered_children = []
    for child in node.children:
        filtered_child = _filter_layout_tree(child, filter_class)
        if filtered_child is not None:
            filtered_children.append(filtered_child)

    matches = filter_class.lower() in node.class_name.lower()
    if matches or filtered_children:
        return LayoutNode(
            class_name=node.class_name,
            resource_id=node.resource_id,
            bounds=node.bounds,
            text=node.text,
            content_desc=node.content_desc,
            enabled=node.enabled,
            visible=node.visible,
            clickable=node.clickable,
            focused=node.focused,
            checked=node.checked,
            scrollable=node.scrollable,
            depth=node.depth,
            children=tuple(filtered_children),
        )
    return None
```

- [ ] **Step 2: Commit**

```bash
git add src/android_mcp/__main__.py
git commit -m "feat: add GetLayoutTree MCP tool"
```

---

### Task 7: Add GetElementDetails Tool

**Files:**
- Modify: `src/android_mcp/__main__.py`

- [ ] **Step 1: Add GetElementDetails tool**

Insert this new tool definition after `GetLayoutTree` in `__main__.py`:

```python
@mcp.tool(
    name="GetElementDetails",
    description="Get detailed properties of a single UI element. Locate by text, resourceId, className, or description. Returns bounds, text, content-desc, and all state flags.",
    annotations=ToolAnnotations(title="Get Element Details", readOnlyHint=True),
)
def get_element_details_tool(selector_type: str, selector_value: str, timeout: float = 5.0):
    device = require_device()

    valid_selectors = {"text", "resourceId", "className", "description"}
    if selector_type not in valid_selectors:
        return f"Invalid selector_type '{selector_type}'. Must be one of: {', '.join(sorted(valid_selectors))}"

    kwargs = {}
    if selector_type == "resourceId":
        kwargs["resourceId"] = _resolve_resource_id(device, selector_value)
    else:
        kwargs[selector_type] = selector_value

    el = device(**kwargs)
    if not el.wait(timeout=timeout):
        return f"Element not found with {selector_type}='{selector_value}' within {timeout}s"

    info = el.info
    bounds = info.get("bounds", {})
    visible_bounds = info.get("visibleBounds", {})

    lines = [
        f"class: {info.get('className', '')}",
        f"resource-id: {info.get('resourceName', '')}",
        f"text: {info.get('text', '')}",
        f"content-desc: {info.get('contentDescription', '')}",
        f"bounds: [{bounds.get('left',0)},{bounds.get('top',0)}][{bounds.get('right',0)},{bounds.get('bottom',0)}]",
        f"visible-bounds: [{visible_bounds.get('left',0)},{visible_bounds.get('top',0)}][{visible_bounds.get('right',0)},{visible_bounds.get('bottom',0)}]",
        f"enabled: {info.get('enabled', False)}",
        f"visible: {info.get('visible', True)}",
        f"clickable: {info.get('clickable', False)}",
        f"focused: {info.get('focused', False)}",
        f"checked: {info.get('checked', False)}",
        f"scrollable: {info.get('scrollable', False)}",
        f"selected: {info.get('selected', False)}",
        f"package: {info.get('packageName', '')}",
    ]
    return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add src/android_mcp/__main__.py
git commit -m "feat: add GetElementDetails MCP tool"
```

---

### Task 8: Final Verification

- [ ] **Step 1: Run all tests**

```bash
cd /Users/eddie/github-projects/Android-MCP
uv run pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 2: Verify server starts**

```bash
uv run android-mcp --help
```

Expected: Help text shows available options

- [ ] **Step 3: Final commit if needed**

```bash
git status
```

If any uncommitted changes remain:
```bash
git add -A
git commit -m "chore: final cleanup for layout debugging feature"
```
