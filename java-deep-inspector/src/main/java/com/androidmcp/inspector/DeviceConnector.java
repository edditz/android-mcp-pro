package com.androidmcp.inspector;

import com.android.ddmlib.*;
import java.util.concurrent.TimeUnit;

public class DeviceConnector {

    public static class NotFound extends Exception {
        public final String errorType;
        public NotFound(String msg, String errorType) { super(msg); this.errorType = errorType; }
    }

    private final String adbPath;

    public DeviceConnector(String adbPath) { this.adbPath = adbPath; }

    public IDevice connect(String serial, long timeoutMs) throws NotFound {
        AndroidDebugBridge.init(AdbInitOptions.builder().setClientSupportEnabled(true).build());
        AndroidDebugBridge bridge = AndroidDebugBridge.createBridge(adbPath, false, 30, TimeUnit.SECONDS);
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (bridge.getDevices().length == 0 && System.currentTimeMillis() < deadline) {
            sleep(100);
        }
        IDevice[] devices = bridge.getDevices();
        if (devices.length == 0) throw new NotFound("no adb devices", "PROCESS_NOT_FOUND");
        if (serial != null) {
            for (IDevice d : devices) if (serial.equals(d.getSerialNumber())) return d;
            throw new NotFound("device " + serial + " not found", "PROCESS_NOT_FOUND");
        }
        return devices[0];
    }

    public Client findClient(IDevice device, String pkg, long timeoutMs) throws NotFound {
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            for (Client c : device.getClients()) {
                ClientData cd = c.getClientData();
                String name = cd.getClientDescription() != null ? cd.getClientDescription() : cd.getPackageName();
                if (pkg.equals(name) || pkg.equals(cd.getPackageName())) {
                    if (!cd.hasFeature(ClientData.FEATURE_VIEW_HIERARCHY)) {
                        throw new NotFound("process " + pkg + " not debuggable / no view feature", "NOT_DEBUGGABLE");
                    }
                    return c;
                }
            }
            sleep(200);
        }
        throw new NotFound("no JDWP client for " + pkg, "PROCESS_NOT_FOUND");
    }

    private static void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException ignored) {}
    }
}
