package com.androidmcp.inspector;

import com.android.ddmlib.AndroidDebugBridge;
import com.android.ddmlib.Client;
import com.android.ddmlib.IDevice;

public class Main {
    public static void main(String[] args) {
        String adbPath = System.getenv().getOrDefault("ADB_PATH", "adb");
        String serial = null, pkg = null, window = null;
        long timeoutMs = 30000;
        for (int i = 0; i < args.length - 1; i++) {
            switch (args[i]) {
                case "--serial": serial = args[++i]; break;
                case "--package": pkg = args[++i]; break;
                case "--window": window = args[++i]; break;
                case "--adb": adbPath = args[++i]; break;
                case "--timeout-ms": timeoutMs = Long.parseLong(args[++i]); break;
            }
        }
        if (pkg == null) {
            System.out.println(JsonOutput.error("--package is required", "BAD_ARGS"));
            System.exit(1);
        }
        try {
            DeviceConnector conn = new DeviceConnector(adbPath);
            IDevice device = conn.connect(serial, timeoutMs);
            Client client = conn.findClient(device, pkg, timeoutMs);
            if (window == null) {
                window = ViewHierarchyDumper.firstWindow(client, 10000);
            }
            if (window == null) {
                System.out.println(JsonOutput.error("no window for " + pkg, "DUMP_FAILED"));
                System.exit(1);
            }
            String v1 = ViewHierarchyDumper.dumpV1(client, window, timeoutMs);
            if (v1 == null) {
                System.out.println(JsonOutput.error("empty dump", "PROTOCOL_UNSUPPORTED"));
                System.exit(1);
            }
            ViewNode root = ViewNodeParser.parse(v1);
            if (root == null) {
                System.out.println(JsonOutput.error("unparseable dump", "PROTOCOL_UNSUPPORTED"));
                System.exit(1);
            }
            CoordinateResolver.resolve(root);
            String json = JsonOutput.toJson(root, pkg, window, "V1");
            System.out.println(json);
            safeTerminate();
            System.exit(0);
        } catch (DeviceConnector.NotFound nf) {
            System.out.println(JsonOutput.error(nf.getMessage(), nf.errorType));
            safeTerminate();
            System.exit(1);
        } catch (java.util.concurrent.TimeoutException te) {
            System.out.println(JsonOutput.error("operation timed out", "TIMEOUT"));
            safeTerminate();
            System.exit(1);
        } catch (Exception e) {
            System.out.println(JsonOutput.error(String.valueOf(e.getMessage()), "DUMP_FAILED"));
            safeTerminate();
            System.exit(1);
        }
    }

    // ddmlib's proxy thread may throw during terminate AFTER data is received; ignore.
    private static void safeTerminate() {
        try { AndroidDebugBridge.terminate(); } catch (Throwable ignored) {}
    }
}
