package com.androidmcp.inspector;

import com.android.ddmlib.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

public class ViewHierarchyDumper {

    /** Returns all view-root window names in listViewRoots order (may be empty, never null). */
    public static List<String> listWindows(Client client, long timeoutMs) throws Exception {
        final List<String> windows = new ArrayList<>();
        final CountDownLatch latch = new CountDownLatch(1);
        client.listViewRoots(new DebugViewDumpHandler(DebugViewDumpHandler.CHUNK_VULW) {
            protected void handleViewDebugResult(ByteBuffer data) {
                int count = data.getInt();
                for (int i = 0; i < count; i++) {
                    windows.add(getString(data, data.getInt()));
                }
                latch.countDown();
            }
        });
        latch.await(timeoutMs, TimeUnit.MILLISECONDS);
        return windows;
    }

    /**
     * Pick the window to dump. ddmlib's listViewRoots order does NOT guarantee the
     * focused window is first (a backgrounded-but-alive Activity can precede the
     * foreground one), so when the caller knows the foreground activity we prefer the
     * window whose name contains that activity's simple class name. Falls back to the
     * first window when there is no hint or no match.
     */
    public static String pickWindow(List<String> windows, String preferredActivity) {
        if (windows.isEmpty()) return null;
        String simple = simpleClassName(preferredActivity);
        if (simple != null) {
            for (String w : windows) {
                if (w != null && w.contains(simple)) return w;
            }
        }
        return windows.get(0);
    }

    /** Returns the focused/first window name, or null. Kept for callers without an activity hint. */
    public static String firstWindow(Client client, long timeoutMs) throws Exception {
        List<String> windows = listWindows(client, timeoutMs);
        return windows.isEmpty() ? null : windows.get(0);
    }

    /**
     * Simple class name of an activity hint. Accepts the forms returned by
     * uiautomator2's app_current(): a relative name (".NoteEditorActivity"), a
     * fully-qualified name ("com.x.NoteEditorActivity"), or a "package/activity"
     * pair ("com.x/com.x.NoteEditorActivity"). Returns the last segment after the
     * final '/' or '.'.
     */
    static String simpleClassName(String activity) {
        if (activity == null) return null;
        String a = activity.trim();
        if (a.isEmpty()) return null;
        int slash = a.lastIndexOf('/');
        if (slash >= 0) a = a.substring(slash + 1);
        int dot = a.lastIndexOf('.');
        String simple = dot >= 0 ? a.substring(dot + 1) : a;
        return simple.isEmpty() ? null : simple;
    }

    /** Dump the given window as V1 text. */
    public static String dumpV1(Client client, String window, long timeoutMs) throws Exception {
        final AtomicReference<byte[]> ref = new AtomicReference<>();
        final CountDownLatch latch = new CountDownLatch(1);
        client.dumpViewHierarchy(window, false, true, false /* useV2=false → V1 text */,
            new DebugViewDumpHandler(DebugViewDumpHandler.CHUNK_VURT) {
                protected void handleViewDebugResult(ByteBuffer data) {
                    byte[] b = new byte[data.remaining()];
                    data.get(b);
                    ref.set(b);
                    latch.countDown();
                }
            });
        if (!latch.await(timeoutMs, TimeUnit.MILLISECONDS)) {
            throw new java.util.concurrent.TimeoutException("dump timed out");
        }
        byte[] bytes = ref.get();
        if (bytes == null || bytes.length == 0) return null;
        return new String(bytes, StandardCharsets.UTF_8);
    }
}
