from dataclasses import dataclass


@dataclass(frozen=True)
class DeepLayoutNode:
    class_name: str
    resource_id: str
    bounds: tuple[int, int, int, int]   # absolute (left, top, right, bottom)
    text: str
    properties: dict[str, float | int | str]  # extracted props, e.g. paddingLeft, elevation, textSize
    depth: int
    children: tuple["DeepLayoutNode", ...]


def format_window_header(package: str, activity: str = "", window: str = "",
                         mode: str = "") -> str:
    """One-line header identifying the captured window/Activity, for debugging.

    Prepended to GetLayoutTree output so the caller can see exactly which
    foreground page the tree was dumped from, and which backend produced it.
    `mode` is the active layout backend ("deep" or "accessibility") — callers
    such as a design-review skill can read it to know which properties to expect
    instead of inferring the backend from the data. `window` is the JDWP window
    token (deep mode only); omitted for the accessibility path.
    """
    parts = []
    if mode:
        parts.append(f"mode={mode}")
    parts += [f"package={package or '<unknown>'}", f"activity={activity or '<unknown>'}"]
    if window:
        parts.append(f"window={window}")
    return "[window] " + " ".join(parts)


def _short_class(class_name: str) -> str:
    return class_name.rsplit(".", 1)[-1] if "." in class_name else class_name


# A property line is emitted whenever the keys are PRESENT, even if all values are 0.
# "Absent" (key not in dict) is intentionally distinct from "present and zero".
def _padding_line(p: dict):
    keys = ("paddingLeft", "paddingTop", "paddingRight", "paddingBottom")
    if not any(k in p for k in keys):
        return None
    vals = [p.get(k, 0) for k in keys]
    return "padding=[{},{},{},{}]".format(*vals)


def _margin_line(p: dict):
    keys = ("marginLeft", "marginTop", "marginRight", "marginBottom")
    if not any(k in p for k in keys):
        return None
    vals = [p.get(k, 0) for k in keys]
    return "margin=[{},{},{},{}]".format(*vals)


def format_deep_tree(root: DeepLayoutNode) -> str:
    lines = []

    def emit(node: DeepLayoutNode):
        indent = "  " * node.depth
        l, t, r, b = node.bounds
        head = f"{indent}[{node.depth}] {_short_class(node.class_name)}  [{l},{t}][{r},{b}]"
        if node.resource_id:
            head += f"  id={node.resource_id}"
        if node.text:
            head += f'  text="{node.text}"'
        lines.append(head)

        p = node.properties
        prop_bits = []
        pad = _padding_line(p)
        if pad:
            prop_bits.append(pad)
        mar = _margin_line(p)
        if mar:
            prop_bits.append(mar)
        if "elevation" in p:
            prop_bits.append(f"elevation={p['elevation']}dp")
        if "textSize" in p:
            prop_bits.append(f"textSize={p['textSize']}dp")
        if "cornerRadius" in p:
            prop_bits.append(f"radius={p['cornerRadius']}dp")
        if prop_bits:
            lines.append(indent + "    " + "  ".join(prop_bits))

        for c in node.children:
            emit(c)

    emit(root)
    return "\n".join(lines)
