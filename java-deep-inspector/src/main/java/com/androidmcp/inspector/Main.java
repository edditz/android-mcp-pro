package com.androidmcp.inspector;

import com.android.ddmlib.AndroidDebugBridge;
import com.android.ddmlib.Client;
import com.android.ddmlib.IDevice;

public class Main {
    public static void main(String[] args) {
        // Change A: Route ddmlib's logger to stderr before any ddmlib init,
        // so its internal noise never reaches stdout.
        com.android.ddmlib.Log.addLogger(new com.android.ddmlib.Log.ILogOutput() {
            @Override
            public void printLog(com.android.ddmlib.Log.LogLevel logLevel, String tag, String message) {
                System.err.println(logLevel.getStringValue() + "/" + tag + ": " + message);
            }
            @Override
            public void printAndPromptLog(com.android.ddmlib.Log.LogLevel logLevel, String tag, String message) {
                System.err.println(logLevel.getStringValue() + "/" + tag + ": " + message);
            }
        });

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
            System.out.flush();
            safeTerminate();
            Runtime.getRuntime().halt(1);
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
                System.out.flush();
                safeTerminate();
                Runtime.getRuntime().halt(1);
            }
            String v1 = ViewHierarchyDumper.dumpV1(client, window, timeoutMs);
            if (v1 == null) {
                System.out.println(JsonOutput.error("empty dump", "PROTOCOL_UNSUPPORTED"));
                System.out.flush();
                safeTerminate();
                Runtime.getRuntime().halt(1);
            }
            ViewNode root = ViewNodeParser.parse(v1);
            if (root == null) {
                System.out.println(JsonOutput.error("unparseable dump", "PROTOCOL_UNSUPPORTED"));
                System.out.flush();
                safeTerminate();
                Runtime.getRuntime().halt(1);
            }
            CoordinateResolver.resolve(root);
            // Change B: flush stdout then hard-exit so ddmlib daemon threads
            // cannot append anything to stdout after the JSON line.
            String json = JsonOutput.toJson(root, pkg, window, "V1");
            System.out.println(json);
            System.out.flush();
            safeTerminate();
            Runtime.getRuntime().halt(0);
        } catch (DeviceConnector.NotFound nf) {
            System.out.println(JsonOutput.error(nf.getMessage(), nf.errorType));
            System.out.flush();
            safeTerminate();
            Runtime.getRuntime().halt(1);
        } catch (java.util.concurrent.TimeoutException te) {
            System.out.println(JsonOutput.error("operation timed out", "TIMEOUT"));
            System.out.flush();
            safeTerminate();
            Runtime.getRuntime().halt(1);
        } catch (Exception e) {
            System.out.println(JsonOutput.error(String.valueOf(e.getMessage()), "DUMP_FAILED"));
            System.out.flush();
            safeTerminate();
            Runtime.getRuntime().halt(1);
        }
    }

    // ddmlib's proxy thread may throw during terminate AFTER data is received; ignore.
    private static void safeTerminate() {
        try { AndroidDebugBridge.terminate(); } catch (Throwable ignored) {}
    }
}
