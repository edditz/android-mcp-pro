import com.android.ddmlib.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

public class Spike3 {
    public static void main(String[] args) throws Exception {
        String adbPath = "/Users/eddie/Library/Android/sdk/platform-tools/adb";
        String targetPkg = "com.miui.notes";
        AndroidDebugBridge.init(AdbInitOptions.builder().setClientSupportEnabled(true).build());
        AndroidDebugBridge bridge = AndroidDebugBridge.createBridge(adbPath, false, 30, TimeUnit.SECONDS);
        long deadline = System.currentTimeMillis() + 15000;
        while (bridge.getDevices().length == 0 && System.currentTimeMillis() < deadline) Thread.sleep(100);
        IDevice device = bridge.getDevices()[0];
        Client client = null;
        deadline = System.currentTimeMillis() + 40000;
        while (System.currentTimeMillis() < deadline) {
            for (Client c : device.getClients()) {
                ClientData cd = c.getClientData();
                String name = cd.getClientDescription() != null ? cd.getClientDescription() : cd.getPackageName();
                if (targetPkg.equals(name) || targetPkg.equals(cd.getPackageName())) { client = c; break; }
            }
            if (client != null) break;
            Thread.sleep(200);
        }
        if (client == null) { System.err.println("NOT FOUND"); System.exit(3); }

        // list first window
        final AtomicReference<String> wref = new AtomicReference<>();
        final CountDownLatch wl = new CountDownLatch(1);
        client.listViewRoots(new DebugViewDumpHandler(DebugViewDumpHandler.CHUNK_VULW){
            protected void handleViewDebugResult(ByteBuffer d){ int n=d.getInt(); for(int i=0;i<n;i++){String w=getString(d,d.getInt()); if(wref.get()==null)wref.set(w);} wl.countDown(); }
        });
        wl.await(10, TimeUnit.SECONDS);
        String window = wref.get();

        // request V1 (useV2 = false)
        final AtomicReference<byte[]> ref = new AtomicReference<>();
        final CountDownLatch dl = new CountDownLatch(1);
        client.dumpViewHierarchy(window, false, true, false /* useV2=false → V1 text */,
            new DebugViewDumpHandler(DebugViewDumpHandler.CHUNK_VURT){
                protected void handleViewDebugResult(ByteBuffer d){ byte[] b=new byte[d.remaining()]; d.get(b); ref.set(b); dl.countDown(); }
            });
        if(!dl.await(15, TimeUnit.SECONDS)){ System.err.println("V1 DUMP TIMEOUT"); System.exit(6); }
        byte[] v1 = ref.get();
        System.err.println("=== V1 dump = " + v1.length + " bytes ===");
        java.nio.file.Files.write(java.nio.file.Paths.get("/tmp/spike/v1_dump.txt"), v1);
        System.err.println("wrote /tmp/spike/v1_dump.txt");
        AndroidDebugBridge.terminate();
        System.exit(0);
    }
}
