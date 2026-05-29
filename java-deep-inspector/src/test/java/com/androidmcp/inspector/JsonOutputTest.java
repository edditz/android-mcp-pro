package com.androidmcp.inspector;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class JsonOutputTest {

    @Test
    void promotesNamedFieldsAndNestsChildren() {
        ViewNode root = new ViewNode();
        root.className = "android.widget.TextView";
        root.props.put("text:mText", "Hello");
        root.props.put("padding:mPaddingLeft", "48");
        root.props.put("padding:mPaddingTop", "24");
        root.props.put("text:getTextSize()", "42.0");
        root.props.put("drawing:getElevation()", "4.0");
        root.props.put("mID", "id/title");
        root.absLeft = 61; root.absTop = 2427; root.absRight = 1139; root.absBottom = 2598;

        String json = JsonOutput.toJson(root, "com.x", "win0", "V1");
        assertTrue(json.contains("\"ok\":true"));
        assertTrue(json.contains("\"package\":\"com.x\""));
        assertTrue(json.contains("\"class\":\"android.widget.TextView\""));
        assertTrue(json.contains("\"bounds\":[61,2427,1139,2598]"));
        assertTrue(json.contains("\"paddingLeft\":48"));
        assertTrue(json.contains("\"textSize\":42.0"));
        assertTrue(json.contains("\"elevation\":4.0"));
    }

    @Test
    void errorJson() {
        String json = JsonOutput.error("process not debuggable", "NOT_DEBUGGABLE");
        assertTrue(json.contains("\"ok\":false"));
        assertTrue(json.contains("\"errorType\":\"NOT_DEBUGGABLE\""));
    }
}
