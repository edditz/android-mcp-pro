from android_mcp.layout.models import DeepLayoutNode, format_deep_tree, format_window_header, text_size_sp
from android_mcp.layout.density import display_scale, px_to_dp
from android_mcp.layout import jdwp_runner


def _json_to_node(obj: dict, depth: int) -> DeepLayoutNode:
    children = tuple(_json_to_node(c, depth + 1) for c in obj.get("children", []))
    b = obj.get("bounds", [0, 0, 0, 0])
    raw_id = obj.get("resourceId", "")
    resource_id = "" if raw_id == "NO_ID" else raw_id
    return DeepLayoutNode(
        class_name=obj.get("class", ""),
        resource_id=resource_id,
        bounds=tuple(b),
        text=obj.get("text", ""),
        properties=dict(obj.get("properties", {})),
        depth=depth,
        children=children,
    )


def _filter(node: DeepLayoutNode, needle: str):
    """Retain-ancestors filter mirroring AccessibilityProvider semantics.

    Returns a (possibly child-pruned) copy of *node* if *node* matches the
    needle OR any of its descendants do; returns None if the entire subtree
    has no match.  Node depths are preserved as-is (consistent with
    AccessibilityProvider which also keeps original depths).
    """
    filtered_children = tuple(
        c for c in (_filter(ch, needle) for ch in node.children) if c is not None
    )
    matches = needle.lower() in node.class_name.lower()
    if matches or filtered_children:
        return DeepLayoutNode(
            class_name=node.class_name, resource_id=node.resource_id, bounds=node.bounds,
            text=node.text, properties=node.properties, depth=node.depth,
            children=filtered_children,
        )
    return None


def _find(node: DeepLayoutNode, selector_type: str, value: str):
    if selector_type == "resourceId" and node.resource_id == value:
        return node
    if selector_type == "text" and node.text == value:
        return node
    for c in node.children:
        hit = _find(c, selector_type, value)
        if hit is not None:
            return hit
    return None


# Property keys whose values are raw pixel distances — annotated with dp on
# output. textSize is shown in sp (the type-scale unit). Everything else
# (textColor, alpha, scaledTextSize, ...) is passed through unchanged.
_PX_KEYS = frozenset({
    "paddingLeft", "paddingTop", "paddingRight", "paddingBottom",
    "marginLeft", "marginTop", "marginRight", "marginBottom",
    "elevation", "cornerRadius",
})


def _format_element(node: DeepLayoutNode, scale: float = 1.0) -> str:
    l, t, r, b = node.bounds
    w_px, h_px = r - l, b - t
    lines = [
        f"class: {node.class_name}",
        f"resource-id: {node.resource_id}",
        f"text: {node.text}",
        f"bounds: [{l},{t}][{r},{b}]",
        f"width: {px_to_dp(w_px, scale)}dp ({w_px}px)",
        f"height: {px_to_dp(h_px, scale)}dp ({h_px}px)",
    ]
    for k, v in node.properties.items():
        if k in _PX_KEYS:
            lines.append(f"{k}: {px_to_dp(v, scale)}dp ({v}px)")
        elif k == "textSize":
            # text_size_sp prefers the device's getScaledTextSize() for the sp value;
            # render as "textSize: <sp>sp (<px>px)" to match the dp/px style above.
            lines.append(text_size_sp(node.properties, scale).replace("=", ": ", 1))
        elif k == "scaledTextSize":
            continue  # consumed by the textSize line above, not shown separately
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines)


class JdwpProvider:
    """Layout provider backed by JDWP/ddmlib via the Java deep-inspector jar."""

    def __init__(self, mobile, *, jar_path: str, adb_path: str, serial: str = None):
        self.mobile = mobile
        self.jar_path = jar_path
        self.adb_path = adb_path
        self.serial = serial

    def _dump_root(self) -> tuple[DeepLayoutNode, dict]:
        """Return (root node, metadata). Metadata carries package/activity/window
        for the debug header."""
        device = self.mobile.get_device()
        try:
            current = device.app_current()
        except Exception:
            current = {}
        pkg = current.get("package", "")
        activity = current.get("activity", "")
        if not pkg:
            raise jdwp_runner.DeepDumpError(
                "could not determine foreground package", "DUMP_FAILED")
        data = jdwp_runner.run_deep_dump(
            self.jar_path, serial=self.serial, package=pkg, adb_path=self.adb_path,
            activity=activity or None)
        root_data = data.get("root")
        if root_data is None:
            raise jdwp_runner.DeepDumpError("response missing 'root' field", "DUMP_FAILED")
        meta = {
            "package": data.get("package", pkg),
            "activity": activity,
            "window": data.get("window", ""),
        }
        return _json_to_node(root_data, depth=0), meta

    def _scale(self) -> float:
        """Device px-to-dp factor; 1.0 if the device can't be queried (so output
        degrades to px==dp rather than raising mid-render)."""
        try:
            return display_scale(self.mobile.get_device())
        except Exception:
            return 1.0

    def get_layout_tree(self, max_depth=None, filter_class=None) -> str:
        """Return the formatted deep layout tree.

        filter_class filters by class-name substring (case-insensitive), retaining
        ancestor containers of matches (consistent with normal mode).
        max_depth is accepted for interface compatibility but is currently ignored in
        deep mode — the full tree captured by the Java helper is always returned.
        """
        try:
            root, meta = self._dump_root()
        except jdwp_runner.DeepDumpError as e:
            return f"[deep mode error: {e.error_type}] {e}"
        if filter_class:
            root = _filter(root, filter_class)
            if root is None:
                return f"No elements matching class '{filter_class}' found."
        header = format_window_header(meta["package"], meta["activity"], meta["window"],
                                      mode="deep")
        return header + "\n" + format_deep_tree(root, scale=self._scale())

    def get_element_details(self, selector_type: str, selector_value: str, timeout: float = 5.0) -> str:
        valid = {"text", "resourceId", "description"}
        if selector_type not in valid:
            return f"Invalid selector_type '{selector_type}'. Must be one of: {', '.join(sorted(valid))}"
        try:
            root, _meta = self._dump_root()
        except jdwp_runner.DeepDumpError as e:
            return f"[deep mode error: {e.error_type}] {e}"
        if selector_type == "description":
            # The JDWP deep tree does not capture content-description; fall back to text.
            lookup_type = "text"
        else:
            lookup_type = selector_type
        node = _find(root, lookup_type, selector_value)
        if node is None:
            note = (" (note: deep mode has no content-desc; searched text instead)"
                    if selector_type == "description" else "")
            return (f"ELEMENT_NOT_FOUND: no node with {selector_type}='{selector_value}'"
                    f"{note} in the deep tree.")
        result = "mode: deep\n" + _format_element(node, scale=self._scale())
        if selector_type == "description":
            result = ("note: deep mode has no content-desc; matched on text instead\n"
                      + result)
        return result
