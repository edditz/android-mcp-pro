package com.androidmcp.inspector;

import java.util.*;

public class JsonOutput {

    public static String error(String message, String errorType) {
        StringBuilder sb = new StringBuilder();
        sb.append("{\"ok\":false,\"error\":").append(quote(message))
          .append(",\"errorType\":").append(quote(errorType)).append("}");
        return sb.toString();
    }

    public static String toJson(ViewNode root, String pkg, String window, String protocol) {
        StringBuilder sb = new StringBuilder();
        sb.append("{\"ok\":true,\"protocol\":").append(quote(protocol))
          .append(",\"package\":").append(quote(pkg))
          .append(",\"window\":").append(quote(window))
          .append(",\"root\":");
        node(sb, root);
        sb.append("}");
        return sb.toString();
    }

    private static void node(StringBuilder sb, ViewNode n) {
        sb.append("{");
        sb.append("\"class\":").append(quote(n.className));
        sb.append(",\"hash\":").append(quote(n.hash));
        String rid = n.props.getOrDefault("mID", "");
        sb.append(",\"resourceId\":").append(quote(stripId(rid)));
        sb.append(",\"bounds\":[").append(n.absLeft).append(",").append(n.absTop)
          .append(",").append(n.absRight).append(",").append(n.absBottom).append("]");
        sb.append(",\"text\":").append(quote(n.props.getOrDefault("text:mText", "")));
        sb.append(",\"properties\":");
        properties(sb, n.props);
        sb.append(",\"children\":[");
        for (int i = 0; i < n.children.size(); i++) {
            if (i > 0) sb.append(",");
            node(sb, n.children.get(i));
        }
        sb.append("]}");
    }

    private static final String[][] NUMERIC = {
        {"paddingLeft", "padding:mPaddingLeft"},
        {"paddingTop", "padding:mPaddingTop"},
        {"paddingRight", "padding:mPaddingRight"},
        {"paddingBottom", "padding:mPaddingBottom"},
        {"marginLeft", "layout:layout_leftMargin"},
        {"marginTop", "layout:layout_topMargin"},
        {"marginRight", "layout:layout_rightMargin"},
        {"marginBottom", "layout:layout_bottomMargin"},
        {"elevation", "drawing:getElevation()"},
        {"textSize", "text:getTextSize()"},
        {"scaledTextSize", "text:getScaledTextSize()"},
        {"alpha", "drawing:getAlpha()"},
    };

    private static void properties(StringBuilder sb, Map<String, String> props) {
        sb.append("{");
        boolean first = true;
        for (String[] pair : NUMERIC) {
            String v = props.get(pair[1]);
            if (v == null) continue;
            if (!first) sb.append(","); first = false;
            sb.append(quote(pair[0])).append(":").append(numberOrQuote(v));
        }
        String outline = props.get("layout:getOutlineString()");
        Double radius = parseRadius(outline);
        if (radius != null) {
            if (!first) sb.append(","); first = false;
            sb.append("\"cornerRadius\":").append(radius);
        }
        // TextView's current text color, emitted as #AARRGGBB so a design review can
        // compare it against Figma hex tokens directly. The raw value is a signed
        // decimal ARGB int (ViewDebug exports it that way); only TextViews carry it.
        String textColor = toHexColor(props.get("text:mCurTextColor"));
        if (textColor != null) {
            if (!first) sb.append(","); first = false;
            sb.append("\"textColor\":").append(quote(textColor));
        }
        sb.append("}");
    }

    /** Convert a signed decimal ARGB int (e.g. "-16777216") to "#AARRGGBB", or null
     *  if the value is absent or unparseable. */
    static String toHexColor(String decimal) {
        if (decimal == null) return null;
        try {
            // parseLong tolerates the full signed-int range; mask back to 32 bits.
            long argb = Long.parseLong(decimal.trim()) & 0xFFFFFFFFL;
            return String.format("#%08X", argb);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    static Double parseRadius(String outline) {
        if (outline == null) return null;
        int idx = outline.indexOf("r:");
        if (idx < 0) return null;
        int j = idx + 2;
        int k = j;
        while (k < outline.length() && (Character.isDigit(outline.charAt(k)) || outline.charAt(k) == '.')) k++;
        try { return Double.parseDouble(outline.substring(j, k)); }
        catch (Exception e) { return null; }
    }

    private static String stripId(String rid) {
        int slash = rid.indexOf('/');
        return slash >= 0 ? rid.substring(slash + 1) : rid;
    }

    private static String numberOrQuote(String v) {
        try {
            double d = Double.parseDouble(v);
            // Java parses "NaN"/"Infinity" but those are NOT valid JSON — quote them.
            if (!Double.isFinite(d)) return quote(v);
            return v;
        } catch (NumberFormatException e) {
            return quote(v);
        }
    }

    static String quote(String s) {
        if (s == null) s = "";
        StringBuilder b = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:
                    if (c < 0x20) b.append(String.format("\\u%04x", (int) c));
                    else b.append(c);
            }
        }
        return b.append("\"").toString();
    }
}
