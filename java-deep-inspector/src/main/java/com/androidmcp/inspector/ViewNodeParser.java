package com.androidmcp.inspector;

import java.util.*;

public class ViewNodeParser {

    /** Parse a V1 hierarchy text dump into a ViewNode tree. */
    public static ViewNode parse(String dump) {
        if (dump == null || dump.isEmpty()) return null;
        String[] lines = dump.split("\n", -1);
        ViewNode root = null;
        Deque<ViewNode> stack = new ArrayDeque<>();
        Deque<Integer> depths = new ArrayDeque<>();

        for (String raw : lines) {
            if (raw.isEmpty() || raw.trim().isEmpty()) continue;
            if (raw.startsWith("DONE")) break; // ddmlib terminator, if present

            int depth = 0;
            while (depth < raw.length() && raw.charAt(depth) == ' ') depth++;
            String content = raw.substring(depth);

            ViewNode node = parseLine(content);
            node.depth = depth;

            if (root == null) {
                root = node;
                stack.push(node);
                depths.push(depth);
                continue;
            }
            while (!depths.isEmpty() && depths.peek() >= depth) {
                stack.pop();
                depths.pop();
            }
            if (!stack.isEmpty()) {
                stack.peek().children.add(node);
            }
            stack.push(node);
            depths.push(depth);
        }
        return root;
    }

    /** Parse "ClassName@hash key=LEN,VALUE key=LEN,VALUE ...". */
    static ViewNode parseLine(String content) {
        ViewNode node = new ViewNode();
        int sp = content.indexOf(' ');
        String head = sp < 0 ? content : content.substring(0, sp);
        int at = head.indexOf('@');
        if (at >= 0) {
            node.className = head.substring(0, at);
            node.hash = head.substring(at + 1);
        } else {
            node.className = head;
        }
        int i = sp < 0 ? content.length() : sp + 1;
        int n = content.length();
        while (i < n) {
            while (i < n && content.charAt(i) == ' ') i++;
            if (i >= n) break;
            int eq = content.indexOf('=', i);
            if (eq < 0) break;
            String key = content.substring(i, eq);
            int comma = content.indexOf(',', eq + 1);
            if (comma < 0) break;
            int len;
            try {
                len = Integer.parseInt(content.substring(eq + 1, comma));
            } catch (NumberFormatException e) {
                break;
            }
            int valStart = comma + 1;
            if (valStart + len > n) {
                // Malformed: declared length exceeds remaining content. Store what
                // remains and stop — the rest of this line cannot be trusted.
                node.props.put(key, content.substring(valStart, n));
                break;
            }
            int valEnd = valStart + len;
            String value = content.substring(valStart, valEnd);
            node.props.put(key, value);
            i = valEnd;
        }
        return node;
    }
}
