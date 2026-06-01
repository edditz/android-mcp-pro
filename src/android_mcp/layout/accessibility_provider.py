import re
from typing import Optional

from android_mcp.layout.models import format_window_header
from android_mcp.tree.service import Tree


def _resolve_resource_id(device, resource_id: str) -> str:
    """Auto-expand short resourceId (e.g. 'btn_login') to full form
    (e.g. 'com.example.app:id/btn_login') using the current foreground app package."""
    if not resource_id or '/' in resource_id or ':' in resource_id:
        return resource_id
    try:
        pkg = device.app_current().get('package', '')
    except Exception:
        pkg = ''
    if pkg:
        return f'{pkg}:id/{resource_id}'
    return resource_id


def _display_scale(device) -> float:
    """Return the px-to-dp scale factor (density / 160).

    uiautomator2's device.info has no displayDensityDpi key, so derive the
    scale from displayWidth / displaySizeDpX (e.g. 1200 / 400 = 3.0). Falls
    back to `wm density`, then to 1.0 if neither is available.
    """
    info = device.info
    width_px = info.get("displayWidth")
    width_dp = info.get("displaySizeDpX")
    if width_px and width_dp:
        return width_px / width_dp

    try:
        output = device.shell("wm density").output
        match = re.search(r"(\d+)", output)
        if match:
            return int(match.group(1)) / 160
    except Exception:
        pass

    return 1.0


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


class AccessibilityProvider:
    """Layout provider backed by the Android accessibility tree (dump_hierarchy)."""

    def __init__(self, mobile):
        self.mobile = mobile

    def get_layout_tree(self, max_depth: Optional[int] = None, filter_class: Optional[str] = None) -> str:
        device = self.mobile.device
        xml_data = device.dump_hierarchy()
        tree = Tree(self.mobile)
        layout_root = tree.get_layout_tree(xml_data=xml_data, max_depth=max_depth)

        if layout_root is None:
            return "Failed to parse layout tree."

        if filter_class:
            layout_root = _filter_layout_tree(layout_root, filter_class)
            if layout_root is None:
                return f"No elements matching class '{filter_class}' found."

        try:
            current = device.app_current()
            header = format_window_header(current.get("package", ""), current.get("activity", ""))
        except Exception:
            header = format_window_header("", "")
        return header + "\n" + Tree.format_layout_tree(layout_root)

    def get_element_details(self, selector_type: str, selector_value: str,
                            timeout: float = 5.0) -> str:
        device = self.mobile.device

        valid_selectors = {"text", "resourceId", "description"}
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

        scale = _display_scale(device)

        width_px = bounds.get("right", 0) - bounds.get("left", 0)
        height_px = bounds.get("bottom", 0) - bounds.get("top", 0)
        width_dp = round(width_px / scale)
        height_dp = round(height_px / scale)

        lines = [
            f"class: {info.get('className', '')}",
            f"resource-id: {info.get('resourceName', '')}",
            f"text: {info.get('text', '')}",
            f"content-desc: {info.get('contentDescription', '')}",
            f"bounds: [{bounds.get('left',0)},{bounds.get('top',0)}][{bounds.get('right',0)},{bounds.get('bottom',0)}]",
            f"visible-bounds: [{visible_bounds.get('left',0)},{visible_bounds.get('top',0)}][{visible_bounds.get('right',0)},{visible_bounds.get('bottom',0)}]",
            f"width: {width_dp}dp ({width_px}px)",
            f"height: {height_dp}dp ({height_px}px)",
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
