package com.androidmcp.inspector;

import com.android.ddmlib.AndroidDebugBridge;
import com.android.ddmlib.Client;
import com.android.ddmlib.IDevice;
import com.android.ddmlib.Log;

public class Main {
    public static void main(String[] args) {
        // Route ddmlib's own logging to stderr so stdout stays pure JSON.
        Log.addLogger(new Log.ILogOutput() {
            @Override public void printLog(Log.LogLevel l, String tag, String msg) {
                System.err.println(l.getStringValue() + "/" + tag + ": " + msg);
            }
            @Override public void printAndPromptLog(Log.LogLevel l, String tag, String msg) {
                System.err.println(l.getStringValue() + "/" + tag + ": " + msg);
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
                case "--timeout-ms":
                    String raw = args[++i];
                    try {
                        timeoutMs = Long.parseLong(raw);
                    } catch (NumberFormatException nfe) {
                        fail("--timeout-ms must be a number, got: " + raw, "BAD_ARGS");
                    }
                    break;
            }
        }
        if (pkg == null) {
            fail("--package is required", "BAD_ARGS");
        }
        try {
            DeviceConnector conn = new DeviceConnector(adbPath);
            IDevice device = conn.connect(serial, timeoutMs);
            Client client = conn.findClient(device, pkg, timeoutMs);
            if (window == null) {
                window = ViewHierarchyDumper.firstWindow(client, 10000);
            }
            if (window == null) {
                fail("no window for " + pkg, "DUMP_FAILED");
            }
            String v1 = ViewHierarchyDumper.dumpV1(client, window, timeoutMs);
            if (v1 == null) {
                fail("empty dump", "PROTOCOL_UNSUPPORTED");
            }
            ViewNode root = ViewNodeParser.parse(v1);
            if (root == null) {
                fail("unparseable dump", "PROTOCOL_UNSUPPORTED");
            }
            CoordinateResolver.resolve(root);
            succeed(JsonOutput.toJson(root, pkg, window, "V1"));
        } catch (DeviceConnector.NotFound nf) {
            fail(nf.getMessage(), nf.errorType);
        } catch (java.util.concurrent.TimeoutException te) {
            fail("operation timed out", "TIMEOUT");
        } catch (Exception e) {
            String msg = e.getMessage() != null ? e.getMessage() : e.getClass().getSimpleName();
            fail(msg, "DUMP_FAILED");
        }
    }

    private static void succeed(String json) {
        System.out.println(json);
        System.out.flush();
        safeTerminate();
        Runtime.getRuntime().halt(0);
    }

    private static void fail(String message, String errorType) {
        System.out.println(JsonOutput.error(message, errorType));
        System.out.flush();
        safeTerminate();
        Runtime.getRuntime().halt(1);
    }

    // ddmlib's proxy thread may throw during terminate AFTER data is received; ignore.
    private static void safeTerminate() {
        try { AndroidDebugBridge.terminate(); } catch (Throwable ignored) {}
    }
}
