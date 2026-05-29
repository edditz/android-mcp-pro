from android_mcp.layout.models import DeepLayoutNode, format_deep_tree
from android_mcp.layout import jdwp_runner


def _json_to_node(obj: dict, depth: int) -> DeepLayoutNode:
    children = tuple(_json_to_node(c, depth + 1) for c in obj.get("children", []))
    b = obj.get("bounds", [0, 0, 0, 0])
    return DeepLayoutNode(
        class_name=obj.get("class", ""),
        resource_id=obj.get("resourceId", ""),
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


def _format_element(node: DeepLayoutNode) -> str:
    l, t, r, b = node.bounds
    lines = [
        f"class: {node.class_name}",
        f"resource-id: {node.resource_id}",
        f"text: {node.text}",
        f"bounds: [{l},{t}][{r},{b}]",
    ]
    for k, v in node.properties.items():
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


class JdwpProvider:
    """Layout provider backed by JDWP/ddmlib via the Java deep-inspector jar."""

    def __init__(self, mobile, *, jar_path: str, adb_path: str, serial: str = None):
        self.mobile = mobile
        self.jar_path = jar_path
        self.adb_path = adb_path
        self.serial = serial

    def _dump_root(self) -> DeepLayoutNode:
        device = self.mobile.get_device()
        pkg = device.app_current().get("package", "")
        data = jdwp_runner.run_deep_dump(
            self.jar_path, serial=self.serial, package=pkg, adb_path=self.adb_path)
        return _json_to_node(data["root"], depth=0)

    def get_layout_tree(self, max_depth=None, filter_class=None) -> str:
        try:
            root = self._dump_root()
        except jdwp_runner.DeepDumpError as e:
            return f"[deep mode error: {e.error_type}] {e}"
        if filter_class:
            root = _filter(root, filter_class)
            if root is None:
                return f"No elements matching class '{filter_class}' found."
        return format_deep_tree(root)

    def get_element_details(self, selector_type: str, selector_value: str, timeout: float = 5.0) -> str:
        valid = {"text", "resourceId", "description"}
        if selector_type not in valid:
            return f"Invalid selector_type '{selector_type}'. Must be one of: {', '.join(sorted(valid))}"
        try:
            root = self._dump_root()
        except jdwp_runner.DeepDumpError as e:
            return f"[deep mode error: {e.error_type}] {e}"
        lookup_type = "resourceId" if selector_type == "resourceId" else "text"
        node = _find(root, lookup_type, selector_value)
        if node is None:
            return (f"ELEMENT_NOT_FOUND: no node with {selector_type}='{selector_value}' "
                    f"in the deep tree.")
        return _format_element(node)
