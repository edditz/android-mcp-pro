import com.android.ddmlib.*;
import java.nio.ByteBuffer;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

public class Spike2 {
    static long t0;
    static void mark(String s){ System.err.println(String.format("[+%5dms] %s", System.currentTimeMillis()-t0, s)); }

    public static void main(String[] args) throws Exception {
        String adbPath = "/Users/eddie/Library/Android/sdk/platform-tools/adb";
        String targetPkg = "com.miui.notes";
        t0 = System.currentTimeMillis();

        AndroidDebugBridge.init(AdbInitOptions.builder().setClientSupportEnabled(true).build());
        AndroidDebugBridge bridge = AndroidDebugBridge.createBridge(adbPath, false, 30, TimeUnit.SECONDS);
        mark("bridge created");

        long deadline = System.currentTimeMillis() + 15000;
        while (bridge.getDevices().length == 0 && System.currentTimeMillis() < deadline) Thread.sleep(100);
        IDevice device = bridge.getDevices()[0];
        mark("device ready: " + device.getSerialNumber());

        // measure: how long until target client attaches
        Client client = null;
        deadline = System.currentTimeMillis() + 40000;
        int lastCount = -1;
        while (System.currentTimeMillis() < deadline) {
            int n = device.getClients().length;
            if (n != lastCount) { mark("clients populated = " + n); lastCount = n; }
            for (Client c : device.getClients()) {
                ClientData cd = c.getClientData();
                String name = cd.getClientDescription() != null ? cd.getClientDescription() : cd.getPackageName();
                if (targetPkg.equals(name) || targetPkg.equals(cd.getPackageName())) { client = c; break; }
            }
            if (client != null) break;
            Thread.sleep(200);
        }
        if (client == null) { mark("TARGET NOT FOUND"); System.exit(3); }
        mark("TARGET FOUND pid=" + client.getClientData().getPid());

        // helper to do one dump and time it
        for (int round = 1; round <= 3; round++) {
            long ds = System.currentTimeMillis();
            String window = listFirstWindow(client);
            byte[] hier = dumpOne(client, window);
            mark("DUMP round " + round + " = " + hier.length + " bytes in " + (System.currentTimeMillis()-ds) + "ms");
        }

        AndroidDebugBridge.terminate();
        System.exit(0);
    }

    static String listFirstWindow(Client client) throws Exception {
        final AtomicReference<String> ref = new AtomicReference<>();
        final CountDownLatch latch = new CountDownLatch(1);
        client.listViewRoots(new DebugViewDumpHandler(DebugViewDumpHandler.CHUNK_VULW) {
            protected void handleViewDebugResult(ByteBuffer data) {
                int count = data.getInt();
                for (int i = 0; i < count; i++) { String w = getString(data, data.getInt()); if (ref.get()==null) ref.set(w); }
                latch.countDown();
            }
        });
        latch.await(10, TimeUnit.SECONDS);
        return ref.get();
    }

    static byte[] dumpOne(Client client, String window) throws Exception {
        final AtomicReference<byte[]> ref = new AtomicReference<>();
        final CountDownLatch latch = new CountDownLatch(1);
        client.dumpViewHierarchy(window, false, true, true, new DebugViewDumpHandler(DebugViewDumpHandler.CHUNK_VURT) {
            protected void handleViewDebugResult(ByteBuffer data) {
                byte[] b = new byte[data.remaining()]; data.get(b); ref.set(b); latch.countDown();
            }
        });
        latch.await(15, TimeUnit.SECONDS);
        return ref.get();
    }
}
