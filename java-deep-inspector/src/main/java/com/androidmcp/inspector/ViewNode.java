package com.androidmcp.inspector;

import java.util.*;

public class ViewNode {
    public String className = "";
    public String hash = "";
    /**
     * Raw indentation level (number of leading spaces) from the dump line.
     * Equals tree depth only when the dump has no indentation gaps; for malformed
     * dumps with forward depth jumps it may exceed the node's actual position.
     */
    public int depth;
    public final Map<String, String> props = new LinkedHashMap<>();
    public final List<ViewNode> children = new ArrayList<>();
    // absolute bounds filled by CoordinateResolver (later task)
    public int absLeft, absTop, absRight, absBottom;
}
