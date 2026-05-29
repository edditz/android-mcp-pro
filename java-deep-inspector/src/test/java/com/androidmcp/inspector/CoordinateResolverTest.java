package com.androidmcp.inspector;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CoordinateResolverTest {

    private ViewNode node(int l, int t, int r, int b, int scrollX, int scrollY) {
        ViewNode n = new ViewNode();
        n.props.put("layout:mLeft", String.valueOf(l));
        n.props.put("layout:mTop", String.valueOf(t));
        n.props.put("layout:mRight", String.valueOf(r));
        n.props.put("layout:mBottom", String.valueOf(b));
        n.props.put("scrolling:mScrollX", String.valueOf(scrollX));
        n.props.put("scrolling:mScrollY", String.valueOf(scrollY));
        return n;
    }

    @Test
    void rootBoundsAreAbsolute() {
        ViewNode root = node(0, 0, 1080, 1920, 0, 0);
        CoordinateResolver.resolve(root);
        assertEquals(0, root.absLeft);
        assertEquals(1080, root.absRight);
        assertEquals(1920, root.absBottom);
    }

    @Test
    void childOffsetByParentOrigin() {
        ViewNode root = node(0, 0, 1080, 1920, 0, 0);
        ViewNode child = node(48, 100, 1032, 200, 0, 0);
        root.children.add(child);
        CoordinateResolver.resolve(root);
        assertEquals(48, child.absLeft);
        assertEquals(100, child.absTop);
        assertEquals(1032, child.absRight);
        assertEquals(200, child.absBottom);
    }

    @Test
    void parentScrollShiftsChildren() {
        ViewNode root = node(0, 0, 1080, 1920, 0, 50);
        ViewNode child = node(0, 100, 1080, 200, 0, 0);
        root.children.add(child);
        CoordinateResolver.resolve(root);
        assertEquals(50, child.absTop);
        assertEquals(150, child.absBottom);
    }
}
