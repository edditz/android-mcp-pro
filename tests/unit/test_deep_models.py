import dataclasses

import pytest

from android_mcp.layout.models import DeepLayoutNode, format_deep_tree


def _leaf(**kw):
    base = dict(
        class_name="android.widget.TextView", resource_id="title",
        bounds=(61, 2427, 1139, 2598), text="标题",
        properties={"paddingLeft": 48, "paddingTop": 24, "paddingRight": 48,
                    "paddingBottom": 0, "elevation": 4.0, "textSize": 14.0},
        depth=0, children=(),
    )
    base.update(kw)
    return DeepLayoutNode(**base)


def test_node_is_frozen_and_holds_properties():
    n = _leaf()
    assert n.properties["paddingLeft"] == 48
    assert n.bounds == (61, 2427, 1139, 2598)
    with pytest.raises(dataclasses.FrozenInstanceError):
        n.text = "mutated"


def test_format_deep_tree_renders_dp_with_px_in_parens():
    # scale=3.0: raw px values convert to dp, px shown in parens. textSize → sp.
    root = _leaf(children=(_leaf(depth=1, resource_id="child", text="hi"),))
    out = format_deep_tree(root, scale=3.0)
    assert "[0] TextView" in out
    assert "id=title" in out
    # padding 48/24/48/0 px @ ×3 → 16/8/16/0 dp, raw px preserved
    assert "padding=[16,8,16,0]dp ([48,24,48,0]px)" in out
    # elevation 4px → 1.3dp
    assert "elevation=1.3dp (4.0px)" in out
    # textSize 14px → 4.7sp (font sizes are sp, not dp)
    assert "textSize=4.7sp (14.0px)" in out
    assert "[1] TextView" in out
    assert "id=child" in out


def test_format_deep_tree_text_size_prefers_scaled():
    # When the device reports getScaledTextSize(), use it for the sp value — it's
    # the device's own px->sp conversion and stays correct even when the scaled
    # density isn't a clean 160-multiple (HyperOS/MIUI) or font-scale != 1.
    # Here textSize/scale would give 52/3 = 17.3, but scaledTextSize is exactly 17.
    root = _leaf(properties={"textSize": 52.0, "scaledTextSize": 17.0})
    out = format_deep_tree(root, scale=3.0)
    assert "textSize=17sp (52.0px)" in out
    assert "scaledTextSize" not in out  # consumed by textSize, not shown separately


def test_format_deep_tree_text_size_falls_back_without_scaled():
    # No scaledTextSize -> fall back to textSize px / layout scale.
    root = _leaf(properties={"textSize": 42.0})
    out = format_deep_tree(root, scale=3.0)
    assert "textSize=14sp (42.0px)" in out


def test_format_deep_tree_scale_one_is_identity():
    # When scale is unknown (1.0), dp == px numerically.
    root = _leaf()
    out = format_deep_tree(root, scale=1.0)
    assert "padding=[48,24,48,0]dp ([48,24,48,0]px)" in out


def test_format_omits_absent_property_lines():
    n = DeepLayoutNode(
        class_name="android.widget.ImageView", resource_id="", bounds=(0, 0, 10, 10),
        text="", properties={"paddingLeft": 0, "paddingTop": 0, "paddingRight": 0,
                              "paddingBottom": 0}, depth=0, children=(),
    )
    out = format_deep_tree(n, scale=3.0)
    assert "textSize" not in out
    assert "elevation" not in out


def test_format_deep_tree_handles_three_levels():
    leaf = _leaf(depth=2, resource_id="leaf", text="deep")
    mid = _leaf(depth=1, resource_id="mid", text="", children=(leaf,))
    root = _leaf(depth=0, resource_id="root", children=(mid,))
    out = format_deep_tree(root, scale=3.0)
    lines = out.split("\n")
    # the leaf header line should be indented 2 levels (4 spaces) and tagged [2]
    assert any(line.startswith("    [2] TextView") and "id=leaf" in line for line in lines)
