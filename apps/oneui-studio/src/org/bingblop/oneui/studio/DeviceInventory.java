package org.bingblop.oneui.studio;

import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import java.io.FileInputStream;
import java.io.IOException;
import java.security.MessageDigest;
import org.json.JSONArray;
import org.json.JSONObject;

/** Read-only observations. Resource matching never means application permission. */
public final class DeviceInventory {
    private DeviceInventory() {}

    public static JSONObject inspect(Context context, JSONObject pack) throws Exception {
        JSONObject report = new JSONObject();
        report.put("format", "oneui-studio.device/1");
        report.put("observedAtEpochMillis", System.currentTimeMillis());
        report.put("model", Build.MODEL);
        report.put("manufacturer", Build.MANUFACTURER);
        report.put("androidRelease", Build.VERSION.RELEASE);
        report.put("androidApiLevel", Build.VERSION.SDK_INT);
        report.put("buildDisplay", Build.DISPLAY);
        report.put("buildFingerprint", Build.FINGERPRINT);
        report.put("securityPatch", Build.VERSION.SECURITY_PATCH);
        report.put("expectedFingerprint", pack.getString("buildFingerprint"));
        boolean matches = Build.FINGERPRINT.equals(pack.getString("buildFingerprint"))
                && Build.VERSION.SDK_INT == pack.getInt("androidApiLevel");
        JSONArray results = new JSONArray();
        JSONArray targets = pack.getJSONArray("targets");
        for (int index = 0; index < targets.length(); index++) {
            JSONObject target = targets.getJSONObject(index);
            JSONObject result = new JSONObject();
            String name = target.getString("package");
            result.put("package", name);
            result.put("expectedApkSha256", target.getString("apkSha256"));
            result.put("hashMatched", false);
            try {
                PackageInfo info = context.getPackageManager().getPackageInfo(name, 0);
                ApplicationInfo application = info.applicationInfo;
                if (application == null || application.sourceDir == null) {
                    throw new IOException("Package does not expose a readable base APK");
                }
                String digest = hash(application.sourceDir);
                boolean equal = digest.equalsIgnoreCase(target.getString("apkSha256"));
                result.put("observedApkSha256", digest);
                result.put("hashMatched", equal);
                result.put("versionCode", info.getLongVersionCode());
                result.put("versionName", info.versionName == null ? JSONObject.NULL : info.versionName);
                result.put("splitCount", info.splitNames == null ? 0 : info.splitNames.length);
                // This pack was measured from one APK per target; unknown splits
                // cannot be certified by matching only the base resource table.
                matches &= equal && (info.splitNames == null || info.splitNames.length == 0);
            } catch (Exception error) {
                result.put("status", "unverified");
                result.put("reason", error.getClass().getSimpleName() + ": " + error.getMessage());
                matches = false;
            }
            results.put(result);
        }
        report.put("targets", results);
        report.put("measuredResourcesMatched", matches);
        report.put("applicationVerified", false);
        report.put("overlayPolicyVerified", false);
        report.put("bridgeConnected", false);
        return report;
    }

    private static String hash(String path) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (FileInputStream input = new FileInputStream(path)) {
            byte[] buffer = new byte[128 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) {
                if (Thread.currentThread().isInterrupted()) throw new IOException("Inspection cancelled");
                digest.update(buffer, 0, count);
            }
        }
        StringBuilder value = new StringBuilder();
        for (byte part : digest.digest()) value.append(String.format(java.util.Locale.ROOT, "%02x", part & 255));
        return value.toString();
    }
}
