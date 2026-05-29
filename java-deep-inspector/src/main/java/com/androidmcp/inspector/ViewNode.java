package com.androidmcp.inspector;

import java.util.*;

public class ViewNode {
    public String className = "";
    public String hash = "";
    public int depth;
    public final Map<String, String> props = new LinkedHashMap<>();
    public final List<ViewNode> children = new ArrayList<>();
    // absolute bounds filled by CoordinateResolver (later task)
    public int absLeft, absTop, absRight, absBottom;
}
