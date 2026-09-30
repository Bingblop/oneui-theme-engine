package com.bloatware.bingblop;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class MainActivity extends Activity {

    private WebView webView;
    private Vibrator vibrator;
    private SharedPreferences prefs;

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

        webView = new WebView(this);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);

        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient());
        webView.setBackgroundColor(0xFF080A0F);

        webView.addJavascriptInterface(new AndroidBridge(), "AndroidBridge");
        webView.loadUrl("file:///android_asset/index.html");
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
        public String executeShell(String cmd) {
            StringBuilder sb = new StringBuilder();
            try {
                Process p;
                try {
                    p = Runtime.getRuntime().exec(new String[]{"rish", "-c", cmd});
                } catch (Exception e) {
                    try {
                        p = Runtime.getRuntime().exec(new String[]{"su", "-c", cmd});
                    } catch (Exception e2) {
                        p = Runtime.getRuntime().exec(new String[]{"sh", "-c", cmd});
                    }
                }
                BufferedReader reader = new BufferedReader(new InputStreamReader(p.getInputStream()));
                String line;
                while ((line = reader.readLine()) != null) {
                    sb.append(line).append("\n");
                }
                reader.close();
                p.waitFor();
            } catch (Exception e) {
                sb.append("Error: ").append(e.getMessage());
            }
            return sb.toString();
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

                // Detect execution environment
                String execMode = "Shell (Standard)";
                String testShizuku = executeShell("id");
                if (testShizuku.contains("uid=2000") || testShizuku.contains("shell")) {
                    execMode = "Privileged Shell (Shizuku / ADB)";
                } else if (testShizuku.contains("uid=0") || testShizuku.contains("root")) {
                    execMode = "Root (Superuser)";
                }
                obj.put("execMode", execMode);

                return obj.toString();
            } catch (Exception e) {
                return "{}";
            }
        }

        @JavascriptInterface
        public String loadPackages() {
            try {
                PackageManager pm = getPackageManager();

                // 1. Query running processes via dumpsys
                Set<String> runningPkgs = new HashSet<String>();
                String runningDump = executeShell("dumpsys activity processes | grep -E 'APP.*ProcessRecord\\{' | sed -E 's/^.*\\{[^:]+:([^:/ ]+).*$/\\1/g' | sort | uniq");
                if (runningDump != null) {
                    for (String line : runningDump.split("\n")) {
                        line = line.trim();
                        if (!line.isEmpty()) runningPkgs.add(line);
                    }
                }

                // 2. Query disabled packages via pm list packages -d
                Set<String> disabledPkgs = new HashSet<String>();
                String disabledDump = executeShell("pm list packages -d | cut -f 2 -d ':'");
                if (disabledDump != null) {
                    for (String line : disabledDump.split("\n")) {
                        line = line.trim();
                        if (!line.isEmpty()) disabledPkgs.add(line);
                    }
                }

                // 3. Query uninstalled/partitioned bloatware packages via pm list packages -u
                Set<String> uninstalledPkgs = new HashSet<String>();
                String uninstalledDump = executeShell("pm list packages -u | cut -f 2 -d ':'");
                Set<String> installedPkgs = new HashSet<String>();
                String installedDump = executeShell("pm list packages | cut -f 2 -d ':'");
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

                // 4. Query installed applications
                List<ApplicationInfo> appList = pm.getInstalledApplications(PackageManager.GET_META_DATA);
                JSONArray array = new JSONArray();

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

                // 5. Add uninstalled / partitioned system bloatware
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
                    Intent intent = new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
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

                // Query AppOps
                String appopsDump = executeShell("cmd appops get " + pkg);
                obj.put("appopsRaw", appopsDump != null ? appopsDump : "");

                return obj.toString();
            } catch (Exception e) {
                return "{}";
            }
        }

        @JavascriptInterface
        public String setAppOp(String pkg, String op, String mode) {
            // mode: allow, ignore, default
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
}
