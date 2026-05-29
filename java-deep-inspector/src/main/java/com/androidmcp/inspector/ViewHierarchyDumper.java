package com.androidmcp.inspector;

import com.android.ddmlib.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

public class ViewHierarchyDumper {

    /** Returns the focused/first window name, or null. */
    public static String firstWindow(Client client, long timeoutMs) throws Exception {
        final AtomicReference<String> ref = new AtomicReference<>();
        final CountDownLatch latch = new CountDownLatch(1);
        client.listViewRoots(new DebugViewDumpHandler(DebugViewDumpHandler.CHUNK_VULW) {
            protected void handleViewDebugResult(ByteBuffer data) {
                int count = data.getInt();
                for (int i = 0; i < count; i++) {
                    String w = getString(data, data.getInt());
                    if (ref.get() == null) ref.set(w);
                }
                latch.countDown();
            }
        });
        latch.await(timeoutMs, TimeUnit.MILLISECONDS);
        return ref.get();
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
