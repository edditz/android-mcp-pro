package com.androidmcp.inspector;

import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class ViewHierarchyDumperTest {

    private static final String LIST =
        "com.miui.notes/com.miui.notes.notesui.feature.note.presentation.list.AINoteListActivity/android.view.ViewRootImpl@1ba50c5";
    private static final String EDITOR =
        "com.miui.notes/com.miui.notes.notesui.feature.note.presentation.editor.webview.NoteEditorActivity/android.view.ViewRootImpl@5c65ad6";

    @Test
    void pickWindowPrefersMatchingActivityNotFirst() {
        // listViewRoots order puts the backgrounded list Activity first; the hint must
        // steer the pick to the focused editor window.
        String picked = ViewHierarchyDumper.pickWindow(
            List.of(LIST, EDITOR),
            ".notesui.feature.note.presentation.editor.webview.NoteEditorActivity");
        assertEquals(EDITOR, picked);
    }

    @Test
    void pickWindowFallsBackToFirstWhenNoHint() {
        assertEquals(LIST, ViewHierarchyDumper.pickWindow(List.of(LIST, EDITOR), null));
        assertEquals(LIST, ViewHierarchyDumper.pickWindow(List.of(LIST, EDITOR), ""));
    }

    @Test
    void pickWindowFallsBackToFirstWhenNoMatch() {
        assertEquals(LIST, ViewHierarchyDumper.pickWindow(List.of(LIST, EDITOR), ".SomeOtherActivity"));
    }

    @Test
    void pickWindowEmptyReturnsNull() {
        assertNull(ViewHierarchyDumper.pickWindow(List.of(), ".NoteEditorActivity"));
    }

    @Test
    void simpleClassNameHandlesDottedAndFullyQualified() {
        assertEquals("NoteEditorActivity", ViewHierarchyDumper.simpleClassName(".a.b.NoteEditorActivity"));
        assertEquals("NoteEditorActivity",
            ViewHierarchyDumper.simpleClassName("com.x/com.x.NoteEditorActivity"));
        assertEquals("MainActivity", ViewHierarchyDumper.simpleClassName("MainActivity"));
        assertNull(ViewHierarchyDumper.simpleClassName(null));
        assertNull(ViewHierarchyDumper.simpleClassName(""));
    }
}
