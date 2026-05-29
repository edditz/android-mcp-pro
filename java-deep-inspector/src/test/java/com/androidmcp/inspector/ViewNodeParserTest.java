package com.androidmcp.inspector;

import org.junit.jupiter.api.Test;
import java.nio.file.*;
import static org.junit.jupiter.api.Assertions.*;

class ViewNodeParserTest {

    @Test
    void parsesKeyLenValuePairs() {
        String dump =
            "android.widget.FrameLayout@aaa padding:mPaddingLeft=2,48 layout:mLeft=1,0 layout:mTop=1,0 layout:mRight=4,1080 layout:mBottom=4,1920\n" +
            " android.widget.TextView@bbb text:mText=5,Hello text:getTextSize()=4,42.0 layout:mLeft=1,0 layout:mTop=1,0 layout:mRight=4,1080 layout:mBottom=3,100\n";
        ViewNode root = ViewNodeParser.parse(dump);
        assertEquals("android.widget.FrameLayout", root.className);
        assertEquals(1, root.children.size());
        ViewNode child = root.children.get(0);
        assertEquals("android.widget.TextView", child.className);
        assertEquals("Hello", child.props.get("text:mText"));
        assertEquals("42.0", child.props.get("text:getTextSize()"));
    }

    @Test
    void valueContainingSpacesRespectsLength() {
        String val = "BKG:rrect{Rect(0, 0 - 132, 72), r:0.0} a:0.0";
        String dump = "android.view.View@ccc layout:getOutlineString()=" + val.length() + "," + val + " drawing:getAlpha()=3,1.0\n";
        ViewNode root = ViewNodeParser.parse(dump);
        assertEquals(val, root.props.get("layout:getOutlineString()"));
        assertEquals("1.0", root.props.get("drawing:getAlpha()"));
    }

    @Test
    void parsesRealFixtureTreeShape() throws Exception {
        String dump = new String(Files.readAllBytes(
            Paths.get(getClass().getResource("/v1_dump_sample.txt").toURI())));
        ViewNode root = ViewNodeParser.parse(dump);
        assertNotNull(root);
        assertTrue(root.className.contains("DecorView"));
        assertFalse(root.children.isEmpty());
        assertTrue(hasTextSize(root));
    }

    private boolean hasTextSize(ViewNode n) {
        if (n.props.containsKey("text:getTextSize()")) return true;
        for (ViewNode c : n.children) if (hasTextSize(c)) return true;
        return false;
    }
}
