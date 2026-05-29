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

    @Test
    void parsesCornerRadiusAndNestsChild() {
        ViewNode root = new ViewNode();
        root.className = "android.view.View";
        root.props.put("layout:getOutlineString()", "BKG:rrect{Rect(0, 0 - 132, 72), r:24.0} a:1.0");
        ViewNode child = new ViewNode();
        child.className = "android.widget.ImageView";
        root.children.add(child);

        String json = JsonOutput.toJson(root, "com.x", "w", "V1");
        assertTrue(json.contains("\"cornerRadius\":24.0"), json);
        assertTrue(json.contains("\"class\":\"android.widget.ImageView\""), json);
    }

    @Test
    void nonFiniteNumbersAreQuotedNotBare() {
        ViewNode root = new ViewNode();
        root.className = "android.view.View";
        root.props.put("drawing:getAlpha()", "NaN");
        String json = JsonOutput.toJson(root, "com.x", "w", "V1");
        // must be quoted, not bare NaN
        assertTrue(json.contains("\"alpha\":\"NaN\""), json);
        assertFalse(json.contains("\"alpha\":NaN"), json);
    }

    @Test
    void escapesSpecialCharsInText() {
        ViewNode root = new ViewNode();
        root.className = "android.widget.TextView";
        root.props.put("text:mText", "He said \"hi\"\nbye\tend");
        String json = JsonOutput.toJson(root, "com.x", "w", "V1");
        assertTrue(json.contains("He said \\\"hi\\\"\\nbye\\tend"), json);
    }

    @Test
    void outputIsValidJsonPerPython() throws Exception {
        ViewNode root = new ViewNode();
        root.className = "android.widget.TextView";
        root.props.put("text:mText", "weird \" \\ \n \t 手写");
        root.props.put("drawing:getAlpha()", "NaN");
        root.props.put("padding:mPaddingLeft", "48");
        root.props.put("layout:getOutlineString()", "BKG:rrect{Rect(0,0-1,1), r:8.0} a:1.0");
        ViewNode child = new ViewNode();
        child.className = "android.view.View";
        root.children.add(child);
        String json = JsonOutput.toJson(root, "com.x", "w", "V1");

        // Validate with python's strict json parser (rejects bare NaN via allow_nan? No —
        // json.loads ACCEPTS NaN by default; use a strict check that forbids it).
        ProcessBuilder pb = new ProcessBuilder("python3", "-c",
            "import json,sys; json.loads(sys.stdin.read(), parse_constant=lambda x:(_ for _ in ()).throw(ValueError('bare '+x)))");
        pb.redirectErrorStream(true);
        Process p = pb.start();
        p.getOutputStream().write(json.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        p.getOutputStream().close();
        String out = new String(p.getInputStream().readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
        int code = p.waitFor();
        assertEquals(0, code, "python json.loads rejected output: " + out + "\nJSON was: " + json);
    }
}
