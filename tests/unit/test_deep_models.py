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


def test_format_deep_tree_renders_property_lines():
    root = _leaf(children=(_leaf(depth=1, resource_id="child", text="hi"),))
    out = format_deep_tree(root)
    assert "[0] TextView" in out
    assert "id=title" in out
    assert "padding=[48,24,48,0]" in out
    assert "elevation=4.0dp" in out
    assert "textSize=14.0dp" in out
    assert "[1] TextView" in out
    assert "id=child" in out


def test_format_omits_absent_property_lines():
    n = DeepLayoutNode(
        class_name="android.widget.ImageView", resource_id="", bounds=(0, 0, 10, 10),
        text="", properties={"paddingLeft": 0, "paddingTop": 0, "paddingRight": 0,
                              "paddingBottom": 0}, depth=0, children=(),
    )
    out = format_deep_tree(n)
    assert "textSize" not in out
    assert "elevation" not in out


def test_format_deep_tree_handles_three_levels():
    leaf = _leaf(depth=2, resource_id="leaf", text="deep")
    mid = _leaf(depth=1, resource_id="mid", text="", children=(leaf,))
    root = _leaf(depth=0, resource_id="root", children=(mid,))
    out = format_deep_tree(root)
    lines = out.split("\n")
    # the leaf header line should be indented 2 levels (4 spaces) and tagged [2]
    assert any(line.startswith("    [2] TextView") and "id=leaf" in line for line in lines)
