# Layout Debugging for AI Design Review

**Date**: 2026-05-28
**Status**: Approved
**Scope**: Add layout data retrieval capabilities to Android-MCP for AI-automated design walkthrough (设计走查)

## Goal

Extend Android-MCP with tools that expose the full Android view hierarchy and element properties, enabling AI agents to perform layout debugging and design review. The focus is on data retrieval — analysis logic is left to the AI agent.

## Current State

The existing `Snapshot` tool only extracts interactive elements (buttons, inputs, etc.), flattens the tree into a list, and stores minimal properties (name, class_name, coordinates, bounding_box, resource_id). Container layouts (FrameLayout, LinearLayout, ConstraintLayout, etc.) are invisible.

## Design

### 1. New Data Model: `LayoutNode`

Add to `tree/views.py`:

```python
@dataclass(frozen=True)
class LayoutNode:
    class_name: str           # e.g. "android.widget.TextView"
    resource_id: str          # short form, e.g. "btn_login"
    bounds: BoundingBox       # [x1,y1][x2,y2]
    text: str                 # raw text attribute
    content_desc: str         # raw content-desc
    enabled: bool
    visible: bool
    clickable: bool
    focused: bool
    checked: bool
    scrollable: bool
    depth: int                # nesting level
    children: tuple[LayoutNode, ...]  # immutable, frozen
```

Modify `TreeState` to include:

```python
layout_root: LayoutNode | None = None
```

### 2. Enhanced Snapshot Tool

Add `include_layout: bool = False` parameter to the existing `Snapshot` tool.

When `include_layout=True`, the return value changes from:
```
[elements_table, screenshot]
```
to:
```
[elements_table, layout_tree_text, screenshot]
```

Layout tree text format:
```
[0] ConstraintLayout  [0,120][1080,2340]  id=main_container
  [1] LinearLayout  [0,120][1080,300]  orientation=horizontal
    [2] TextView  [32,168][400,252]  text="首页"  clickable=true
    [2] ImageView  [960,180][1048,268]  id=icon_search  clickable=true
  [1] RecyclerView  [0,300][1080,2340]  scrollable=true
    [2] CardView  [16,316][1064,580]  clickable=true
      [3] TextView  [32,332][500,380]  text="推荐"
      [3] ImageView  [520,332][1048,564]
```

### 3. New Tool: GetLayoutTree

```
GetLayoutTree(max_depth=10, filter_class=None)
```

Returns the full view hierarchy as formatted text. Parameters:
- `max_depth`: limits tree depth to prevent token explosion (default 10)
- `filter_class`: post-filter by class name (e.g. `"TextView"` returns only text nodes)

### 4. New Tool: GetElementDetails

```
GetElementDetails(selector_type, selector_value)
```

Returns complete properties of a single element (bounds, text, enabled, all state flags). Supports locating by text/resourceId/className/description. Reuses the same selector mechanism as `ClickBySelector`.

### 5. Parser Changes

Add to `tree/service.py`:

```python
def get_layout_tree(self, xml_data=None, max_depth=10) -> LayoutNode | None
```

Core logic:
- Reuses existing `get_element_tree()` for XML parsing
- Recursively traverses all `<node>` elements (not just interactive ones)
- Extracts all attributes into `LayoutNode`
- Preserves parent-child relationships via `children` tuple
- `max_depth` controls recursion depth; truncated nodes get `children=()`

Existing `get_interactive_elements()` and `annotated_screenshot()` are unchanged for backward compatibility.

### 6. Edge Cases

- Nodes beyond `max_depth` are truncated with `children=()`
- `filter_class` is a post-filter (build full tree first, then filter) — does not affect parsing performance
- `GetElementDetails` reuses uiautomator2 selector, same as `ClickBySelector`
- `include_layout=True` adds one recursive traversal per Snapshot call — XML parsing is fast (milliseconds), no noticeable impact

## Files to Modify

| File | Change |
|------|--------|
| `src/android_mcp/tree/views.py` | Add `LayoutNode` dataclass, add `layout_root` to `TreeState` |
| `src/android_mcp/tree/service.py` | Add `get_layout_tree()` method |
| `src/android_mcp/mobile/service.py` | Pass layout data through `get_state()` |
| `src/android_mcp/mobile/views.py` | No change needed (MobileState already holds TreeState) |
| `src/android_mcp/__main__.py` | Enhance Snapshot, add GetLayoutTree and GetElementDetails tools |

## Dependencies

No new dependencies. Uses existing `xml.etree.ElementTree`, `uiautomator2`, and `fastmcp`.
