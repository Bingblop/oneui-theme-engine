package com.bloatware.bingblop;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.util.Log;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.provider.Settings;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

public class MainActivity extends Activity {

    private WebView webView;
    private Vibrator vibrator;
    private SharedPreferences prefs;

    private File rishFile;
    private File rishDexFile;
    private File adbBinFile;
    private File adbHomeDir;

    private final ExecutorService executor = Executors.newCachedThreadPool();

    // Working modes: "auto", "adb_tcp", "adb_wireless", "shizuku", "root", "unprivileged"
    private String activeWorkingMode = "auto";
    private String adbTcpHost = "127.0.0.1";
    private int adbTcpPort = 5555;
    private String adbWirelessHost = "127.0.0.1";
    private int adbWirelessPort = 0;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // One UI dark system bar integration
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getWindow().setNavigationBarColor(0xFF080A0F);
            getWindow().setStatusBarColor(0xFF080A0F);
        }

        vibrator = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
        prefs = getSharedPreferences("adb_app_manager_prefs", Context.MODE_PRIVATE);

        // Load saved working mode settings
        activeWorkingMode = prefs.getString("working_mode", "auto");
        adbTcpHost = prefs.getString("adb_tcp_host", "127.0.0.1");
        adbTcpPort = prefs.getInt("adb_tcp_port", 5555);
        adbWirelessHost = prefs.getString("adb_wireless_host", "127.0.0.1");
        adbWirelessPort = prefs.getInt("adb_wireless_port", 0);

        // Extract binaries and ADB keys in background
        setupBinariesAndKeys();

        webView = new WebView(this);
        setContentView(webView);

        webView.setVerticalScrollBarEnabled(true);
        webView.setHorizontalScrollBarEnabled(false);
        webView.setOverScrollMode(android.view.View.OVER_SCROLL_IF_CONTENT_SCROLLS);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(false);
        settings.setUseWideViewPort(false);

        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient());
        webView.setBackgroundColor(0xFF080A0F);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            WebView.setWebContentsDebuggingEnabled(true);
        }

        webView.addJavascriptInterface(new AndroidBridge(), "AndroidBridge");
        webView.loadUrl("file:///android_asset/index.html");
    }

    private void setupBinariesAndKeys() {
        try {
            File filesDir = getFilesDir();
            
            // 1. Shizuku rish setup
            rishFile = new File(filesDir, "rish");
            rishDexFile = new File(filesDir, "rish_shizuku.dex");
            extractAsset("rish", rishFile);
            rishFile.setExecutable(true, false);
            rishFile.setReadable(true, false);
            extractAsset("rish_shizuku.dex", rishDexFile);
            rishDexFile.setReadable(true, false);
            if (Build.VERSION.SDK_INT >= 34) {
                rishDexFile.setWritable(false, false);
            }

            // 2. ADB Native Library setup
            // Prefer extracted native library in nativeLibraryDir (standard for Android APKs)
            File nativeAdb = new File(getApplicationInfo().nativeLibraryDir, "libadb.so");
            if (nativeAdb.exists() && nativeAdb.canExecute()) {
                adbBinFile = nativeAdb;
            } else {
                adbBinFile = new File(filesDir, "libadb.so");
                extractAsset("libadb.so", adbBinFile);
                adbBinFile.setExecutable(true, false);
                adbBinFile.setReadable(true, false);
            }

            // 3. ADB Keys setup (.android/adbkey & .android/adbkey.pub)
            adbHomeDir = new File(filesDir, "adb_home");
            File dotAndroid = new File(adbHomeDir, ".android");
            if (!dotAndroid.exists()) dotAndroid.mkdirs();

            File keyFile = new File(dotAndroid, "adbkey");
            File pubFile = new File(dotAndroid, "adbkey.pub");

            extractAsset("adbkey", keyFile);
            keyFile.setReadable(true, false);
            keyFile.setWritable(true, false);

            extractAsset("adbkey.pub", pubFile);
            pubFile.setReadable(true, false);
            pubFile.setWritable(true, false);

            // Connect to 5555 if available right on launch
            executor.submit(new Runnable() {
                @Override
                public void run() {
                    try {
                        if (isPortOpen(adbTcpHost, adbTcpPort, 400)) {
                            performConnectAdbTcp(adbTcpHost, adbTcpPort);
                        }
                    } catch (Exception e) {
                        Log.w("ADBAppManager", "Auto-connect background failed: " + e.getMessage());
                    }
                }
            });

        } catch (Exception e) {
            Log.e("ADBAppManager", "setupBinariesAndKeys error", e);
        }
    }

    private void extractAsset(String assetName, File destFile) {
        try {
            if (destFile.exists() && destFile.length() > 0) return;
            InputStream in = getAssets().open(assetName);
            OutputStream out = new FileOutputStream(destFile);
            byte[] buf = new byte[8192];
            int len;
            while ((len = in.read(buf)) > 0) {
                out.write(buf, 0, len);
            }
            in.close();
            out.flush();
            out.close();
        } catch (Exception ignored) {}
    }

    private boolean isAdbTargetConnected(String target) {
        try {
            ProcessBuilder pb = buildAdbProcess("devices");
            String out = runProcessWithTimeout(pb, 1500);
            return out != null && out.contains(target) && !out.contains("offline") && !out.contains("unauthorized");
        } catch (Exception e) {
            return false;
        }
    }

    private ProcessBuilder buildAdbProcess(String... args) {
        List<String> cmd = new ArrayList<String>();
        cmd.add(adbBinFile != null && adbBinFile.exists() ? adbBinFile.getAbsolutePath() : "adb");
        cmd.add("-P");
        cmd.add("5042");
        for (String a : args) {
            cmd.add(a);
        }
        ProcessBuilder pb = new ProcessBuilder(cmd);
        Map<String, String> env = pb.environment();
        if (adbHomeDir != null) {
            env.put("HOME", adbHomeDir.getAbsolutePath());
            env.put("ANDROID_USER_HOME", adbHomeDir.getAbsolutePath());
            File dotKey = new File(new File(adbHomeDir, ".android"), "adbkey");
            if (dotKey.exists()) {
                env.put("ADB_VENDOR_KEYS", dotKey.getAbsolutePath());
            }
        }
        env.put("TMPDIR", getCacheDir().getAbsolutePath());
        pb.redirectErrorStream(true);
        return pb;
    }

    private String runProcessWithTimeout(ProcessBuilder pb, int timeoutMs) {
        final StringBuilder sb = new StringBuilder();
        try {
            final Process p = pb.start();
            Future<String> future = executor.submit(new Callable<String>() {
                @Override
                public String call() throws Exception {
                    BufferedReader reader = new BufferedReader(new InputStreamReader(p.getInputStream()));
                    String line;
                    while ((line = reader.readLine()) != null) {
                        sb.append(line).append("\n");
                    }
                    reader.close();
                    p.waitFor();
                    return sb.toString();
                }
            });

            try {
                future.get(timeoutMs, TimeUnit.MILLISECONDS);
            } catch (Exception timeoutEx) {
                future.cancel(true);
                try { p.destroy(); } catch (Exception ignored) {}
                sb.append("\n[Process timed out after ").append(timeoutMs).append("ms]");
            }
        } catch (Exception e) {
            sb.append("Error: ").append(e.getMessage());
        }
        return sb.toString().trim();
    }

    private boolean isPortOpen(String host, int port, int timeoutMs) {
        Socket socket = null;
        try {
            socket = new Socket();
            socket.connect(new InetSocketAddress(host, port), timeoutMs);
            return true;
        } catch (Exception e) {
            return false;
        } finally {
            if (socket != null) {
                try { socket.close(); } catch (Exception ignored) {}
            }
        }
    }

    public String performConnectAdbTcp(String host, int port) {
        if (host == null || host.trim().isEmpty()) host = "127.0.0.1";
        if (port <= 0) port = 5555;
        adbTcpHost = host.trim();
        adbTcpPort = port;

        prefs.edit().putString("adb_tcp_host", adbTcpHost).putInt("adb_tcp_port", adbTcpPort).apply();

        ProcessBuilder pb = buildAdbProcess("connect", adbTcpHost + ":" + adbTcpPort);
        String output = runProcessWithTimeout(pb, 4500);
        Log.d("ADBAppManager", "connectAdbTcp (" + adbTcpHost + ":" + adbTcpPort + ") -> " + output);

        if (output != null && (output.contains("connected") || output.contains("already connected"))) {
            activeWorkingMode = "adb_tcp";
            prefs.edit().putString("working_mode", activeWorkingMode).apply();
        }
        return output != null ? output : "";
    }

    public String performConnectAdbWireless(String host, int port) {
        if (host == null || host.trim().isEmpty()) host = "127.0.0.1";
        if (port <= 0) return "Error: Invalid wireless debugging port";
        adbWirelessHost = host.trim();
        adbWirelessPort = port;

        prefs.edit().putString("adb_wireless_host", adbWirelessHost).putInt("adb_wireless_port", adbWirelessPort).apply();

        ProcessBuilder pb = buildAdbProcess("connect", adbWirelessHost + ":" + adbWirelessPort);
        String output = runProcessWithTimeout(pb, 5000);
        Log.d("ADBAppManager", "connectAdbWireless (" + adbWirelessHost + ":" + adbWirelessPort + ") -> " + output);

        if (output != null && (output.contains("connected") || output.contains("already connected"))) {
            activeWorkingMode = "adb_wireless";
            prefs.edit().putString("working_mode", activeWorkingMode).apply();
        }
        return output != null ? output : "";
    }

    private class AndroidBridge {

        @JavascriptInterface
        public void vibrate() {
            if (vibrator != null) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    vibrator.vibrate(VibrationEffect.createOneShot(20, VibrationEffect.DEFAULT_AMPLITUDE));
                } else {
                    vibrator.vibrate(20);
                }
            }
        }

        @JavascriptInterface
        public void showToast(final String msg) {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    Toast.makeText(MainActivity.this, msg, Toast.LENGTH_SHORT).show();
                }
            });
        }

        @JavascriptInterface
        public void openDeveloperOptions() {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    try {
                        Intent intent = new Intent(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS);
                        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                        startActivity(intent);
                    } catch (Exception e) {
                        try {
                            Intent intent = new Intent(Settings.ACTION_SETTINGS);
                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                            startActivity(intent);
                        } catch (Exception ignored) {}
                    }
                }
            });
        }

        @JavascriptInterface
        public void requestShizukuPermission() {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    try {
                        Intent intent = new Intent("moe.shizuku.manager.intent.action.REQUEST_PERMISSION");
                        intent.setPackage("moe.shizuku.privileged.api");
                        intent.putExtra("moe.shizuku.manager.intent.extra.PACKAGE_NAME", getPackageName());
                        startActivity(intent);
                    } catch (Exception e) {
                        try {
                            Intent intent = new Intent("moe.shizuku.manager.intent.action.REQUEST_PERMISSION");
                            intent.setPackage("af.shizuku.plus.api");
                            intent.putExtra("moe.shizuku.manager.intent.extra.PACKAGE_NAME", getPackageName());
                            startActivity(intent);
                        } catch (Exception e2) {
                            try {
                                Intent launchIntent = getPackageManager().getLaunchIntentForPackage("moe.shizuku.privileged.api");
                                if (launchIntent != null) {
                                    startActivity(launchIntent);
                                } else {
                                    Intent launchPlus = getPackageManager().getLaunchIntentForPackage("af.shizuku.plus.api");
                                    if (launchPlus != null) {
                                        startActivity(launchPlus);
                                    } else {
                                        Toast.makeText(MainActivity.this, "Shizuku app not found on device!", Toast.LENGTH_LONG).show();
                                    }
                                }
                            } catch (Exception e3) {
                                Toast.makeText(MainActivity.this, "Failed to launch Shizuku: " + e3.getMessage(), Toast.LENGTH_SHORT).show();
                            }
                        }
                    }
                }
            });
        }

        @JavascriptInterface
        public String checkShizukuStatus() {
            JSONObject obj = new JSONObject();
            try {
                boolean installed = false;
                try {
                    getPackageManager().getPackageInfo("moe.shizuku.privileged.api", 0);
                    installed = true;
                } catch (Exception e) {
                    try {
                        getPackageManager().getPackageInfo("af.shizuku.plus.api", 0);
                        installed = true;
                    } catch (Exception ignored) {}
                }
                obj.put("installed", installed);

                // Quick test execution through bundled rish with strict 1200ms timeout
                String testId = "";
                if (rishFile != null && rishFile.exists()) {
                    ProcessBuilder pb = new ProcessBuilder("/system/bin/sh", rishFile.getAbsolutePath(), "-c", "id");
                    pb.environment().put("RISH_APPLICATION_ID", getPackageName());
                    pb.redirectErrorStream(true);
                    testId = runProcessWithTimeout(pb, 1200);
                }

                boolean authorized = testId.contains("uid=2000") || testId.contains("shell") || testId.contains("uid=0");
                obj.put("authorized", authorized);
                obj.put("running", authorized || testId.contains("Waiting for Shizuku"));
                obj.put("raw", testId);

                return obj.toString();
            } catch (Exception e) {
                return "{\"installed\":false,\"authorized\":false,\"running\":false}";
            }
        }

        @JavascriptInterface
        public String connectAdbTcp(String host, int port) {
            return performConnectAdbTcp(host, port);
        }

        @JavascriptInterface
        public String pairAdbWireless(String host, int port, String code) {
            if (host == null || host.trim().isEmpty()) host = "127.0.0.1";
            if (port <= 0 || code == null || code.trim().isEmpty()) {
                return "Error: Invalid port or pairing code";
            }
            ProcessBuilder pb = buildAdbProcess("pair", host.trim() + ":" + port, code.trim());
            return runProcessWithTimeout(pb, 6000);
        }

        @JavascriptInterface
        public String connectAdbWireless(String host, int port) {
            if (host == null || host.trim().isEmpty()) host = "127.0.0.1";
            if (port <= 0) return "Error: Invalid wireless debugging port";
            adbWirelessHost = host.trim();
            adbWirelessPort = port;

            prefs.edit().putString("adb_wireless_host", adbWirelessHost).putInt("adb_wireless_port", adbWirelessPort).apply();

            ProcessBuilder pb = buildAdbProcess("connect", adbWirelessHost + ":" + adbWirelessPort);
            String output = runProcessWithTimeout(pb, 4000);

            if (output.contains("connected") || output.contains("already connected")) {
                activeWorkingMode = "adb_wireless";
                prefs.edit().putString("working_mode", activeWorkingMode).apply();
            }
            return output;
        }

        @JavascriptInterface
        public String setAdbTcpip(int port) {
            if (port <= 0) port = 5555;
            ProcessBuilder pb = buildAdbProcess("tcpip", String.valueOf(port));
            return runProcessWithTimeout(pb, 4000);
        }

        @JavascriptInterface
        public String disconnectAdb(String target) {
            ProcessBuilder pb;
            if (target != null && !target.trim().isEmpty()) {
                pb = buildAdbProcess("disconnect", target.trim());
            } else {
                pb = buildAdbProcess("disconnect");
            }
            return runProcessWithTimeout(pb, 3000);
        }

        @JavascriptInterface
        public String getWorkingMode() {
            try {
                JSONObject obj = new JSONObject();

                // Check ADB over TCP (5555) port
                boolean tcpPortOpen = isPortOpen(adbTcpHost, adbTcpPort, 300);
                JSONObject tcpObj = new JSONObject();
                tcpObj.put("host", adbTcpHost);
                tcpObj.put("port", adbTcpPort);
                tcpObj.put("portOpen", tcpPortOpen);

                // Check ADB devices
                boolean tcpConnected = isAdbTargetConnected(adbTcpHost + ":" + adbTcpPort);
                if (!tcpConnected && tcpPortOpen) {
                    performConnectAdbTcp(adbTcpHost, adbTcpPort);
                    tcpConnected = isAdbTargetConnected(adbTcpHost + ":" + adbTcpPort);
                }
                boolean wirelessConnected = (adbWirelessPort > 0) && isAdbTargetConnected(adbWirelessHost + ":" + adbWirelessPort);
                tcpObj.put("connected", tcpConnected);
                obj.put("adbTcp", tcpObj);

                JSONObject wirelessObj = new JSONObject();
                wirelessObj.put("host", adbWirelessHost);
                wirelessObj.put("port", adbWirelessPort);
                wirelessObj.put("connected", wirelessConnected);
                obj.put("adbWireless", wirelessObj);

                // Check Shizuku status
                JSONObject shizukuObj = new JSONObject(checkShizukuStatus());
                obj.put("shizuku", shizukuObj);

                // Check Root status
                boolean rootAvailable = false;
                try {
                    Process pRoot = Runtime.getRuntime().exec(new String[]{"which", "su"});
                    rootAvailable = (pRoot.waitFor() == 0);
                } catch (Exception ignored) {}
                obj.put("rootAvailable", rootAvailable);

                // Determine active / resolved mode
                String resolvedMode = activeWorkingMode;
                if ("auto".equals(resolvedMode)) {
                    if (tcpConnected) {
                        resolvedMode = "adb_tcp";
                    } else if (wirelessConnected) {
                        resolvedMode = "adb_wireless";
                    } else if (shizukuObj.optBoolean("authorized", false)) {
                        resolvedMode = "shizuku";
                    } else if (tcpPortOpen) {
                        // Port is open, try connecting
                        performConnectAdbTcp(adbTcpHost, adbTcpPort);
                        resolvedMode = "adb_tcp";
                    } else if (rootAvailable) {
                        resolvedMode = "root";
                    } else {
                        resolvedMode = "unprivileged";
                    }
                }
                obj.put("activeMode", resolvedMode);
                obj.put("configuredMode", activeWorkingMode);

                boolean isPrivileged = "adb_tcp".equals(resolvedMode) || "adb_wireless".equals(resolvedMode) || "shizuku".equals(resolvedMode) || "root".equals(resolvedMode);
                obj.put("isPrivileged", isPrivileged);

                return obj.toString();
            } catch (Exception e) {
                return "{\"activeMode\":\"unprivileged\",\"isPrivileged\":false}";
            }
        }

        @JavascriptInterface
        public void setWorkingMode(String mode) {
            activeWorkingMode = (mode != null) ? mode : "auto";
            prefs.edit().putString("working_mode", activeWorkingMode).apply();
        }

        @JavascriptInterface
        public String executeShell(String cmd) {
            if (cmd == null || cmd.trim().isEmpty()) return "";

            // Check resolved mode
            String mode = activeWorkingMode;
            if ("auto".equals(mode)) {
                // If auto, test ADB TCP first, then Shizuku, then Root
                if (isPortOpen(adbTcpHost, adbTcpPort, 200)) {
                    mode = "adb_tcp";
                } else {
                    String shizukuStatus = checkShizukuStatus();
                    if (shizukuStatus.contains("\"authorized\":true")) {
                        mode = "shizuku";
                    } else {
                        mode = "standard";
                    }
                }
            }

            // Route execution
            if ("adb_tcp".equals(mode)) {
                if (!isAdbTargetConnected(adbTcpHost + ":" + adbTcpPort)) {
                    performConnectAdbTcp(adbTcpHost, adbTcpPort);
                }
                ProcessBuilder pb = buildAdbProcess("-s", adbTcpHost + ":" + adbTcpPort, "shell", cmd);
                String res = runProcessWithTimeout(pb, 5000);
                if (res != null && res.contains("device '") && res.contains("' not found")) {
                    performConnectAdbTcp(adbTcpHost, adbTcpPort);
                    res = runProcessWithTimeout(pb, 5000);
                }
                Log.d("ADBAppManager", "executeShell [adb_tcp]: " + cmd + " -> " + (res != null ? res.trim() : ""));
                return res != null ? res : "";
            } else if ("adb_wireless".equals(mode)) {
                if (!isAdbTargetConnected(adbWirelessHost + ":" + adbWirelessPort)) {
                    connectAdbWireless(adbWirelessHost, adbWirelessPort);
                }
                ProcessBuilder pb = buildAdbProcess("-s", adbWirelessHost + ":" + adbWirelessPort, "shell", cmd);
                String res = runProcessWithTimeout(pb, 5000);
                Log.d("ADBAppManager", "executeShell [adb_wireless]: " + cmd + " -> " + (res != null ? res.trim() : ""));
                return res != null ? res : "";
            } else if ("shizuku".equals(mode)) {
                if (rishFile != null && rishFile.exists()) {
                    ProcessBuilder pb = new ProcessBuilder("/system/bin/sh", rishFile.getAbsolutePath(), "-c", cmd);
                    pb.environment().put("RISH_APPLICATION_ID", getPackageName());
                    pb.redirectErrorStream(true);
                    String res = runProcessWithTimeout(pb, 5000);
                    Log.d("ADBAppManager", "executeShell [shizuku]: " + cmd + " -> " + (res != null ? res.trim() : ""));
                    return res != null ? res : "";
                }
            } else if ("root".equals(mode)) {
                try {
                    ProcessBuilder pb = new ProcessBuilder("su", "-c", cmd);
                    pb.redirectErrorStream(true);
                    String res = runProcessWithTimeout(pb, 5000);
                    Log.d("ADBAppManager", "executeShell [root]: " + cmd + " -> " + (res != null ? res.trim() : ""));
                    return res != null ? res : "";
                } catch (Exception ignored) {}
            }

            // Fallback: standard sh (limited unprivileged access)
            ProcessBuilder pb = new ProcessBuilder("/system/bin/sh", "-c", cmd);
            pb.redirectErrorStream(true);
            String res = runProcessWithTimeout(pb, 4000);
            Log.d("ADBAppManager", "executeShell [standard]: " + cmd + " -> " + (res != null ? res.trim() : ""));
            return res != null ? res : "";
        }

        @JavascriptInterface
        public String getSystemInfo() {
            try {
                JSONObject obj = new JSONObject();
                obj.put("device", Build.MODEL);
                obj.put("manufacturer", Build.MANUFACTURER);
                obj.put("brand", Build.BRAND);
                obj.put("sdk", Build.VERSION.SDK_INT);
                obj.put("release", Build.VERSION.RELEASE);

                JSONObject modeInfo = new JSONObject(getWorkingMode());
                String mode = modeInfo.optString("activeMode", "unprivileged");
                String execMode = "Unprivileged (Read-Only)";
                if ("adb_tcp".equals(mode)) {
                    execMode = "ADB TCP (Port " + adbTcpPort + ")";
                } else if ("adb_wireless".equals(mode)) {
                    execMode = "Wireless Debugging (Port " + adbWirelessPort + ")";
                } else if ("shizuku".equals(mode)) {
                    execMode = "Shizuku ADB (UID 2000)";
                } else if ("root".equals(mode)) {
                    execMode = "Root (Superuser)";
                }
                obj.put("execMode", execMode);
                obj.put("activeMode", mode);
                obj.put("isPrivileged", modeInfo.optBoolean("isPrivileged", false));

                return obj.toString();
            } catch (Exception e) {
                return "{}";
            }
        }

        @JavascriptInterface
        public String loadPackages() {
            try {
                PackageManager pm = getPackageManager();

                // 1. ALWAYS query native installed applications first (Guaranteed fast & non-blocking!)
                List<ApplicationInfo> appList = pm.getInstalledApplications(PackageManager.GET_META_DATA);

                // 2. Query running processes and disabled packages ONLY if a privileged working mode is active
                Set<String> runningPkgs = new HashSet<String>();
                Set<String> disabledPkgs = new HashSet<String>();
                Set<String> uninstalledPkgs = new HashSet<String>();

                JSONObject modeObj = new JSONObject(getWorkingMode());
                boolean isPrivileged = modeObj.optBoolean("isPrivileged", false);

                if (isPrivileged) {
                    try {
                        String runningDump = executeShell("dumpsys activity processes | grep -E 'APP.*ProcessRecord\\{' | sed -E 's/^.*\\{[^:]+:([^:/ ]+).*$/\\1/g' | sort | uniq");
                        if (runningDump != null) {
                            for (String line : runningDump.split("\n")) {
                                line = line.trim();
                                if (!line.isEmpty()) runningPkgs.add(line);
                            }
                        }
                    } catch (Exception ignored) {}

                    try {
                        String disabledDump = executeShell("pm list packages -d | cut -f 2 -d ':'");
                        if (disabledDump != null) {
                            for (String line : disabledDump.split("\n")) {
                                line = line.trim();
                                if (!line.isEmpty()) disabledPkgs.add(line);
                            }
                        }
                    } catch (Exception ignored) {}

                    try {
                        String uninstalledDump = executeShell("pm list packages -u | cut -f 2 -d ':'");
                        String installedDump = executeShell("pm list packages | cut -f 2 -d ':'");
                        Set<String> installedPkgs = new HashSet<String>();
                        if (installedDump != null) {
                            for (String line : installedDump.split("\n")) {
                                line = line.trim();
                                if (!line.isEmpty()) installedPkgs.add(line);
                            }
                        }
                        if (uninstalledDump != null) {
                            for (String line : uninstalledDump.split("\n")) {
                                line = line.trim();
                                if (!line.isEmpty() && !installedPkgs.contains(line)) {
                                    uninstalledPkgs.add(line);
                                }
                            }
                        }
                    } catch (Exception ignored) {}
                }

                JSONArray array = new JSONArray();

                // Populate installed apps
                for (ApplicationInfo ai : appList) {
                    JSONObject item = new JSONObject();
                    item.put("pkg", ai.packageName);
                    String label = pm.getApplicationLabel(ai).toString();
                    item.put("name", (label != null && !label.isEmpty()) ? label : ai.packageName);

                    boolean isSystem = (ai.flags & ApplicationInfo.FLAG_SYSTEM) != 0;
                    item.put("isSystem", isSystem);
                    item.put("isRunning", runningPkgs.contains(ai.packageName));
                    item.put("isFrozen", disabledPkgs.contains(ai.packageName) || !ai.enabled);
                    item.put("isUninstalled", false);
                    item.put("targetSdk", ai.targetSdkVersion);

                    array.put(item);
                }

                // Add uninstalled / partitioned system bloatware
                for (String uPkg : uninstalledPkgs) {
                    JSONObject item = new JSONObject();
                    item.put("pkg", uPkg);
                    item.put("name", uPkg);
                    item.put("isSystem", true);
                    item.put("isRunning", false);
                    item.put("isFrozen", true);
                    item.put("isUninstalled", true);
                    item.put("targetSdk", 0);
                    array.put(item);
                }

                return array.toString();
            } catch (Exception e) {
                return "[]";
            }
        }

        @JavascriptInterface
        public String executeAppAction(String action, String pkg) {
            String res = "";
            try {
                if ("freeze".equals(action)) {
                    res = executeShell("pm disable-user " + pkg);
                } else if ("unfreeze".equals(action)) {
                    executeShell("pm enable " + pkg);
                    res = executeShell("pm unsuspend " + pkg);
                } else if ("suspend".equals(action)) {
                    res = executeShell("pm suspend " + pkg);
                } else if ("unsuspend".equals(action)) {
                    res = executeShell("pm unsuspend " + pkg);
                } else if ("force_stop".equals(action)) {
                    res = executeShell("am force-stop " + pkg);
                } else if ("clear_data".equals(action)) {
                    res = executeShell("pm clear " + pkg);
                } else if ("uninstall".equals(action)) {
                    res = executeShell("pm uninstall --user 0 " + pkg);
                } else if ("uninstall_keep_data".equals(action)) {
                    res = executeShell("pm uninstall -k --user 0 " + pkg);
                } else if ("uninstall_updates".equals(action)) {
                    res = executeShell("pm uninstall-system-updates " + pkg);
                } else if ("reinstall".equals(action)) {
                    res = executeShell("pm install-existing " + pkg);
                } else if ("launch".equals(action)) {
                    Intent intent = getPackageManager().getLaunchIntentForPackage(pkg);
                    if (intent != null) {
                        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                        startActivity(intent);
                        res = "Launched";
                    } else {
                        res = executeShell("monkey -p " + pkg + " -c android.intent.category.LAUNCHER 1");
                    }
                } else if ("app_settings".equals(action)) {
                    Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
                    intent.setData(Uri.parse("package:" + pkg));
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    startActivity(intent);
                    res = "Settings opened";
                }
            } catch (Exception e) {
                res = "Error: " + e.getMessage();
            }
            return res;
        }

        @JavascriptInterface
        public String executeBatchAction(String action, String pkgsJson) {
            int success = 0;
            int failed = 0;
            try {
                JSONArray arr = new JSONArray(pkgsJson);
                for (int i = 0; i < arr.length(); i++) {
                    String pkg = arr.getString(i);
                    String r = executeAppAction(action, pkg);
                    if (r != null && !r.toLowerCase().contains("error") && !r.toLowerCase().contains("failed")) {
                        success++;
                    } else {
                        failed++;
                    }
                }
            } catch (Exception e) {
                failed++;
            }
            return "{\"success\":" + success + ",\"failed\":" + failed + "}";
        }

        @JavascriptInterface
        public String getAppDetails(String pkg) {
            try {
                JSONObject obj = new JSONObject();
                PackageManager pm = getPackageManager();

                try {
                    PackageInfo pi = pm.getPackageInfo(pkg, PackageManager.GET_PERMISSIONS | PackageManager.GET_ACTIVITIES | PackageManager.GET_SERVICES | PackageManager.GET_RECEIVERS | PackageManager.GET_PROVIDERS);
                    obj.put("versionName", pi.versionName != null ? pi.versionName : "N/A");
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                        obj.put("versionCode", pi.getLongVersionCode());
                    } else {
                        obj.put("versionCode", pi.versionCode);
                    }
                    obj.put("firstInstallTime", pi.firstInstallTime);
                    obj.put("lastUpdateTime", pi.lastUpdateTime);

                    if (pi.applicationInfo != null) {
                        obj.put("sourceDir", pi.applicationInfo.sourceDir);
                        obj.put("dataDir", pi.applicationInfo.dataDir);
                        obj.put("targetSdk", pi.applicationInfo.targetSdkVersion);
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                            obj.put("minSdk", pi.applicationInfo.minSdkVersion);
                        }
                    }

                    // Permissions
                    JSONArray permArray = new JSONArray();
                    if (pi.requestedPermissions != null) {
                        for (int i = 0; i < pi.requestedPermissions.length; i++) {
                            String p = pi.requestedPermissions[i];
                            JSONObject pObj = new JSONObject();
                            pObj.put("name", p);
                            boolean granted = (pi.requestedPermissionsFlags != null && (pi.requestedPermissionsFlags[i] & PackageInfo.REQUESTED_PERMISSION_GRANTED) != 0);
                            pObj.put("granted", granted);
                            permArray.put(pObj);
                        }
                    }
                    obj.put("permissions", permArray);

                    // Activities
                    JSONArray actArray = new JSONArray();
                    if (pi.activities != null) {
                        for (android.content.pm.ActivityInfo ai : pi.activities) {
                            actArray.put(ai.name);
                        }
                    }
                    obj.put("activities", actArray);

                    // Services
                    JSONArray srvArray = new JSONArray();
                    if (pi.services != null) {
                        for (android.content.pm.ServiceInfo si : pi.services) {
                            srvArray.put(si.name);
                        }
                    }
                    obj.put("services", srvArray);

                } catch (Exception e) {
                    obj.put("error", e.getMessage());
                }

                // Query AppOps (if privileged)
                try {
                    String appopsDump = executeShell("cmd appops get " + pkg);
                    obj.put("appopsRaw", appopsDump != null ? appopsDump : "");
                } catch (Exception ignored) {}

                return obj.toString();
            } catch (Exception e) {
                return "{}";
            }
        }

        @JavascriptInterface
        public String setAppOp(String pkg, String op, String mode) {
            return executeShell("appops set " + pkg + " " + op + " " + mode);
        }

        @JavascriptInterface
        public String setPermission(String pkg, String perm, boolean grant) {
            if (grant) {
                return executeShell("pm grant " + pkg + " " + perm);
            } else {
                return executeShell("pm revoke " + pkg + " " + perm);
            }
        }

        @JavascriptInterface
        public void savePreferences(String jsonStr) {
            prefs.edit().putString("custom_settings", jsonStr).apply();
        }

        @JavascriptInterface
        public String loadPreferences() {
            return prefs.getString("custom_settings", "{}");
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        try {
            executor.shutdown();
        } catch (Exception ignored) {}
    }
}
