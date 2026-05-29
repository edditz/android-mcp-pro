import com.android.ddmlib.*;
import java.nio.ByteBuffer;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

public class Spike {
    public static void main(String[] args) throws Exception {
        String adbPath = "/Users/eddie/Library/Android/sdk/platform-tools/adb";
        String targetPkg = "com.miui.notes";

        // 1. init ddmlib with client support so we can see JDWP Clients
        AndroidDebugBridge.init(AdbInitOptions.builder().setClientSupportEnabled(true).build());
        AndroidDebugBridge bridge = AndroidDebugBridge.createBridge(adbPath, false, 30, TimeUnit.SECONDS);

        // 2. wait for device
        long deadline = System.currentTimeMillis() + 15000;
        while (bridge.getDevices().length == 0 && System.currentTimeMillis() < deadline) {
            Thread.sleep(200);
        }
        if (bridge.getDevices().length == 0) { System.err.println("NO_DEVICE"); System.exit(2); }
        IDevice device = bridge.getDevices()[0];
        System.err.println("device = " + device.getSerialNumber());

        // 3. wait for clients (JDWP processes) to populate AND for our target to attach
        deadline = System.currentTimeMillis() + 40000;
        Client client = null;
        while (System.currentTimeMillis() < deadline) {
            for (Client c : device.getClients()) {
                ClientData cd = c.getClientData();
                String name = cd.getClientDescription() != null ? cd.getClientDescription() : cd.getPackageName();
                if (targetPkg.equals(name) || targetPkg.equals(cd.getPackageName())) { client = c; break; }
            }
            if (client != null) break;
            Thread.sleep(500);
        }
        System.err.println("clients = " + device.getClients().length);
        if (client == null) {
            System.err.println("PROCESS_NOT_FOUND. available clients:");
            for (Client c : device.getClients()) System.err.println("  - " + c.getClientData().getClientDescription());
            System.exit(3);
        }
        System.err.println("found client pid = " + client.getClientData().getPid());
        System.err.println("hasFeature(VIEW_HIERARCHY) = " + client.getClientData().hasFeature(ClientData.FEATURE_VIEW_HIERARCHY));

        // 5. list view roots (windows)
        final AtomicReference<String> windowRef = new AtomicReference<>();
        final CountDownLatch rootsLatch = new CountDownLatch(1);
        client.listViewRoots(new DebugViewDumpHandler(DebugViewDumpHandler.CHUNK_VULW) {
            protected void handleViewDebugResult(ByteBuffer data) {
                int count = data.getInt();
                System.err.println("window count = " + count);
                for (int i = 0; i < count; i++) {
                    String w = getString(data, data.getInt());
                    System.err.println("  window[" + i + "] = " + w);
                    if (windowRef.get() == null) windowRef.set(w);
                }
                rootsLatch.countDown();
            }
        });
        if (!rootsLatch.await(10, TimeUnit.SECONDS)) { System.err.println("LIST_ROOTS_TIMEOUT"); System.exit(4); }
        String window = windowRef.get();
        if (window == null) { System.err.println("NO_WINDOW"); System.exit(5); }

        // 6. dump view hierarchy WITH properties
        final AtomicReference<byte[]> hierRef = new AtomicReference<>();
        final CountDownLatch dumpLatch = new CountDownLatch(1);
        client.dumpViewHierarchy(window, false /*skipChildren*/, true /*includeProperties*/, true /*useV2*/,
            new DebugViewDumpHandler(DebugViewDumpHandler.CHUNK_VURT) {
                protected void handleViewDebugResult(ByteBuffer data) {
                    byte[] b = new byte[data.remaining()];
                    data.get(b);
                    hierRef.set(b);
                    dumpLatch.countDown();
                }
            });
        if (!dumpLatch.await(15, TimeUnit.SECONDS)) { System.err.println("DUMP_TIMEOUT"); System.exit(6); }
        byte[] hier = hierRef.get();
        System.err.println("=== DUMP OK: " + hier.length + " bytes ===");

        // 7. crude scan for property names to prove richness (V2 is binary; look for ascii prop tokens)
        String asText = new String(hier, java.nio.charset.StandardCharsets.ISO_8859_1);
        String[] probe = {"padding", "Padding", "margin", "Margin", "elevation", "getTextSize", "textSize", "mLeft", "getZ", "alpha"};
        for (String p : probe) {
            System.err.println("  contains '" + p + "' = " + asText.contains(p));
        }
        // dump a readable slice of ascii tokens
        System.err.println("=== ascii tokens sample ===");
        StringBuilder tok = new StringBuilder();
        int shown = 0;
        for (int i = 0; i < hier.length && shown < 120; i++) {
            char ch = (char)(hier[i] & 0xff);
            if (ch >= 32 && ch < 127) { tok.append(ch); }
            else { if (tok.length() >= 4) { System.err.println("  " + tok); shown++; } tok.setLength(0); }
        }
        AndroidDebugBridge.terminate();
        System.exit(0);
    }
}
