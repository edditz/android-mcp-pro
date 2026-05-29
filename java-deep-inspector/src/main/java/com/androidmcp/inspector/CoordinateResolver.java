package com.androidmcp.inspector;

public class CoordinateResolver {

    /** Fill absLeft/absTop/absRight/absBottom for the whole tree. */
    public static void resolve(ViewNode root) {
        resolve(root, 0, 0);
    }

    private static void resolve(ViewNode node, int parentAbsLeft, int parentAbsTop) {
        int mLeft = intProp(node, "layout:mLeft");
        int mTop = intProp(node, "layout:mTop");
        int mRight = intProp(node, "layout:mRight");
        int mBottom = intProp(node, "layout:mBottom");

        int width = mRight - mLeft;
        int height = mBottom - mTop;

        node.absLeft = parentAbsLeft + mLeft;
        node.absTop = parentAbsTop + mTop;
        node.absRight = node.absLeft + width;
        node.absBottom = node.absTop + height;

        int scrollX = intProp(node, "scrolling:mScrollX");
        int scrollY = intProp(node, "scrolling:mScrollY");
        int childOriginLeft = node.absLeft - scrollX;
        int childOriginTop = node.absTop - scrollY;
        for (ViewNode c : node.children) {
            resolve(c, childOriginLeft, childOriginTop);
        }
    }

    private static int intProp(ViewNode n, String key) {
        String v = n.props.get(key);
        if (v == null) return 0;
        try { return Integer.parseInt(v.trim()); }
        catch (NumberFormatException e) { return 0; }
    }
}
