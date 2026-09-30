package com.hexnext.themer;

import android.app.Activity;
import android.content.Context;
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
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStreamReader;

public class MainActivity extends Activity {

    private WebView webView;
    private Vibrator vibrator;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Dark status bar and navigation bar integration
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getWindow().setNavigationBarColor(0xFF0B0D14);
            getWindow().setStatusBarColor(0xFF0B0D14);
        }

        vibrator = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);

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
        webView.setBackgroundColor(0xFF0B0D14);

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
        public void showToast(final String message) {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    Toast.makeText(MainActivity.this, message, Toast.LENGTH_SHORT).show();
                }
            });
        }

        @JavascriptInterface
        public String executeShell(String cmd) {
            StringBuilder sb = new StringBuilder();
            try {
                // Try rish or su or direct sh
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
                p.waitFor();
            } catch (Exception e) {
                sb.append("Error: ").append(e.getMessage());
            }
            return sb.toString();
        }

        @JavascriptInterface
        public boolean applyTheme(String jsonConfig) {
            try {
                JSONObject obj = new JSONObject(jsonConfig);
                String accent = obj.getString("accent").replace("#", "");
                String bg = obj.getString("bg").replace("#", "");
                String card = obj.getString("card").replace("#", "");

                if (accent.length() == 6) accent = "ff" + accent;
                if (bg.length() == 6) bg = "ff" + bg;
                if (card.length() == 6) card = "ff" + card;

                JSONObject targets = obj.getJSONObject("targets");

                // 1. Android Framework
                if (targets.optBoolean("android", true)) {
                    String cmd = "cmd overlay fabricate --target android --name hexnext_android " +
                            "color/background_dark 0x1c 0x" + bg + " " +
                            "color/primary_material_dark 0x1c 0x" + bg + " " +
                            "color/system_neutral1_900 0x1c 0x" + bg + " " +
                            "color/system_neutral1_1000 0x1c 0x" + bg + " " +
                            "color/system_accent1_600 0x1c 0x" + accent + " " +
                            "color/system_accent1_100 0x1c 0x" + card;
                    executeShell(cmd);
                    executeShell("cmd overlay enable --user current com.android.shell:hexnext_android");
                }

                // 2. SystemUI
                if (targets.optBoolean("systemui", true)) {
                    String cmd = "cmd overlay fabricate --target com.android.systemui --name hexnext_systemui " +
                            "color/qs_background_dark 0x1c 0x" + bg + " " +
                            "color/quick_settings_panel_background_color 0x1c 0x" + bg + " " +
                            "color/notification_panel_background_color 0x1c 0x" + bg + " " +
                            "color/qs_tile_active_color 0x1c 0x" + accent + " " +
                            "color/qs_tile_inactive_color 0x1c 0x" + card;
                    executeShell(cmd);
                    executeShell("cmd overlay enable --user current com.android.shell:hexnext_systemui");
                }

                // 3. Settings
                if (targets.optBoolean("settings", true)) {
                    String cmd = "cmd overlay fabricate --target com.android.settings --name hexnext_settings " +
                            "color/sec_widget_round_and_bgcolor 0x1c 0x" + card + " " +
                            "color/sec_dashboard_tab_selected_color 0x1c 0x" + accent + " " +
                            "color/sec_dashboard_background_color 0x1c 0x" + bg;
                    executeShell(cmd);
                    executeShell("cmd overlay enable --user current com.android.shell:hexnext_settings");
                }

                // 4. Telephony & Dialer
                if (targets.optBoolean("telephony", true)) {
                    String cmd = "cmd overlay fabricate --target com.samsung.android.dialer --name hexnext_dialer " +
                            "color/primary_color 0x1c 0x" + accent + " " +
                            "color/dialpad_background_color 0x1c 0x" + bg;
                    executeShell(cmd);
                    executeShell("cmd overlay enable --user current com.android.shell:hexnext_dialer");
                }

                // Set system setting
                executeShell("settings put system current_sec_active_themepackage com.samsung.themedesigner.HexNext");

                return true;
            } catch (Exception e) {
                return false;
            }
        }

        @JavascriptInterface
        public void resetTheme() {
            executeShell("cmd overlay disable --user current com.android.shell:hexnext_android");
            executeShell("cmd overlay disable --user current com.android.shell:hexnext_systemui");
            executeShell("cmd overlay disable --user current com.android.shell:hexnext_settings");
            executeShell("cmd overlay disable --user current com.android.shell:hexnext_dialer");
            executeShell("settings delete system current_sec_active_themepackage");
        }

        @JavascriptInterface
        public void autoFixHex() {
            executeShell("cmd overlay enable --user current android:SemWT_android");
            executeShell("cmd overlay enable --user current android:SemWT_com.android.systemui");
            executeShell("cmd overlay enable --user current android:SemWT_MonetPalette");
            executeShell("cmd overlay enable --user current android:SemWT_G_MonetPalette");
            executeShell("settings put system current_sec_active_themepackage com.samsung.themedesigner.Hex");
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
