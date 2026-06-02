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


# The JDWP helper reports every distance in raw pixels (Android's ViewDebug
# exports px). We render them as "<dp>dp (<px>px)" so a design review can compare
# against Figma dp directly, while the raw px stays visible for sanity-checking.
# Font sizes are shown in sp (the unit Figma/Android type scales use), not dp.
from android_mcp.layout.density import px_to_dp


def _dp_px(px: float, scale: float) -> str:
    return f"{px_to_dp(px, scale)}dp ({px}px)"


# A property line is emitted whenever the keys are PRESENT, even if all values are 0.
# "Absent" (key not in dict) is intentionally distinct from "present and zero".
def _box_line(name: str, keys: tuple, p: dict, scale: float):
    if not any(k in p for k in keys):
        return None
    px = [p.get(k, 0) for k in keys]
    dp = [px_to_dp(v, scale) for v in px]
    return "{}=[{},{},{},{}]dp ([{},{},{},{}]px)".format(name, *dp, *px)


def _padding_line(p: dict, scale: float):
    keys = ("paddingLeft", "paddingTop", "paddingRight", "paddingBottom")
    return _box_line("padding", keys, p, scale)


def _margin_line(p: dict, scale: float):
    keys = ("marginLeft", "marginTop", "marginRight", "marginBottom")
    return _box_line("margin", keys, p, scale)


def format_deep_tree(root: DeepLayoutNode, scale: float = 1.0) -> str:
    """Render the deep tree. `scale` is the device px-to-dp factor (density/160);
    every distance is shown as dp with the raw px in parens. Pass 1.0 when the
    density is unknown (dp will then equal px)."""
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
        pad = _padding_line(p, scale)
        if pad:
            prop_bits.append(pad)
        mar = _margin_line(p, scale)
        if mar:
            prop_bits.append(mar)
        if "elevation" in p:
            prop_bits.append(f"elevation={_dp_px(p['elevation'], scale)}")
        if "textSize" in p:
            prop_bits.append(f"textSize={px_to_dp(p['textSize'], scale)}sp ({p['textSize']}px)")
        if "cornerRadius" in p:
            prop_bits.append(f"radius={_dp_px(p['cornerRadius'], scale)}")
        if prop_bits:
            lines.append(indent + "    " + "  ".join(prop_bits))

        for c in node.children:
            emit(c)

    emit(root)
    return "\n".join(lines)
