package org.bingblop.oneui.studio;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.util.AtomicFile;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.json.JSONArray;
import org.json.JSONObject;

/** Native, offline source editor. This activity never installs or enables overlays. */
public final class MainActivity extends Activity {
    private static final int BG = 0xff080a10, PANEL = 0xff141822, TEXT = 0xfff2f4fa;
    private static final int MUTED = 0xffa0aabc, ACCENT = 0xffb89cff;
    private static final int IMPORT = 40, EXPORT = 41, REPORT = 42;
    private static final String[] SLUGS = {"amoled-black", "neon-violet", "cyberpunk-gold"};
    private static final String[] NAMES = {"AMOLED Black", "Neon Violet", "Cyberpunk Gold"};
    private static final String[] ROLES = {
        "background", "surface", "accent", "onAccent", "textPrimary", "textSecondary",
        "quickPanelBackground", "quickTileActive", "quickTileInactive", "quickTileIconActive", "quickTileIconInactive",
        "notificationBackground", "notificationText", "settingsBackground", "settingsIcon",
        "keyboardBackground", "keyboardKeyBackground", "keyboardKeyText", "keyboardAccent",
        "statusBarIcons", "navigationBarBackground", "navigationBarIcons", "outline", "link", "error"
    };
    private static final String[] LABELS = {
        "Background", "Surface", "Accent", "Text on accent", "Primary text", "Secondary text",
        "Panel background", "Active tile", "Inactive tile", "Active tile icon", "Inactive tile icon",
        "Notification background", "Notification text", "Settings background", "Settings icons",
        "Keyboard background", "Key background", "Key text", "Keyboard accent",
        "Status bar icons", "Navigation background", "Navigation icons", "Outline", "Links", "Errors"
    };
    private static final String[] APP_KEYS = {"global", "framework", "systemui", "settings", "keyboard", "phone", "contacts", "messages", "files"};
    private static final String[] APP_NAMES = {"All apps", "Framework", "Quick panel & notifications", "Settings", "Keyboard", "Phone", "Contacts", "Messages", "My Files"};
    private static final String[] DIMENSIONS = {"cornerRadius", "quickTileRadius", "keyboardKeyRadius", "navigationBarHeight", "bodyTextSize"};
    private static final String[] DIMENSION_NAMES = {"Dialog & button corners", "Quick tile corners", "Keyboard key corners", "Navigation bar height", "Body text size"};
    private static final int[] DIM_MIN = {0, 0, 0, 16, 10}, DIM_MAX = {32, 32, 24, 96, 28};
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private ThemeSource theme;
    private JSONObject pack, device;
    private JSONArray history = new JSONArray();
    private LinearLayout content, root;
    private int page = 0, preview = 0, appScope = 0;
    private boolean dark = true, busy = true;
    private String status = "Opening your workspace…";

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        dark = getPreferences(0).getBoolean("dark", true);
        if (state != null) {
            page = state.getInt("page", 0);
            preview = state.getInt("preview", 0);
            appScope = state.getInt("appScope", 0);
        }
        render();
        worker.execute(() -> {
            try {
                JSONObject measured;
                try (InputStream input = getAssets().open("resource-pack.json")) {
                    measured = new JSONObject(new String(input.readAllBytes(), StandardCharsets.UTF_8));
                }
                ThemeSource restored;
                File draft = new File(getFilesDir(), "draft.ouitheme");
                try (InputStream input = new AtomicFile(draft).openRead()) {
                    restored = ThemeSource.read(input);
                } catch (java.io.FileNotFoundException missing) {
                    restored = ThemeSource.builtin(getAssets(), "sources/amoled-black.ouitheme");
                }
                JSONArray events = readHistory();
                ThemeSource opened = restored;
                main.post(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    pack = measured; theme = opened; history = events;
                    chooseAvailableVariant(); busy = false; status = "Your workspace is saved on this device";
                    render();
                });
            } catch (Exception error) {
                main.post(() -> { busy = false; status = "Workspace could not open"; render(); showError(error); });
            }
        });
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        state.putInt("page", page); state.putInt("preview", preview); state.putInt("appScope", appScope);
        super.onSaveInstanceState(state);
    }

    @Override protected void onDestroy() {
        worker.shutdownNow();
        main.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    private void chooseAvailableVariant() {
        if (!theme.hasVariant(dark ? "dark" : "light")) dark = theme.hasVariant("dark");
    }

    private void render() {
        if (isFinishing() || isDestroyed()) return;
        root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setBackgroundColor(BG);
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return insets;
        });
        setContentView(root);
        root.requestApplyInsets();
        if (root.getWindowInsetsController() != null) root.getWindowInsetsController().setSystemBarsAppearance(0, 24);
        ScrollView scroll = new ScrollView(this); scroll.setFillViewport(true);
        content = column(); content.setPadding(dp(22), dp(26), dp(22), dp(28));
        scroll.addView(content);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout brand = row();
        TextView mark = text("◈", 30, ACCENT); mark.setContentDescription("One UI Studio"); brand.addView(mark);
        TextView name = text("ONE UI STUDIO", 12, MUTED); name.setLetterSpacing(.14f); name.setPadding(dp(10), 0, 0, 0); brand.addView(name);
        content.addView(brand);
        space(content, 24);
        String[] titles = {"Make it\nyours.", "Your theme.\nYour rules.", "Know your\ndevice.", "Keep your\ncreations."};
        TextView title = text(titles[page], 38, TEXT); title.setTypeface(Typeface.DEFAULT, Typeface.BOLD); content.addView(title);
        space(content, 12);
        TextView message = text(status, 13, MUTED); message.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE); content.addView(message);
        space(content, 26);
        if (page == 0) library(); else if (page == 1) studio(); else if (page == 2) device(); else history();
        LinearLayout navigation = row(); navigation.setBackgroundColor(PANEL); navigation.setPadding(dp(8), dp(6), dp(8), dp(6));
        String[] tabs = {"Library", "Studio", "Device", "History"};
        for (int i = 0; i < tabs.length; i++) {
            final int selected = i;
            Button button = button(tabs[i], () -> { page = selected; render(); }, i == page);
            button.setTextSize(12); navigation.addView(button, new LinearLayout.LayoutParams(0, dp(52), 1));
        }
        root.addView(navigation);
    }

    private void library() {
        if (theme != null) {
            LinearLayout card = card();
            card.addView(text("CURRENT DRAFT", 11, ACCENT)); space(card, 10);
            card.addView(text(theme.getName(), 24, TEXT));
            card.addView(text("Saved locally · " + (dark ? "Dark" : "Light") + " variant", 13, MUTED));
            space(card, 12); card.addView(button("Continue editing", () -> { page = 1; render(); }, true));
            content.addView(card); space(content, 20);
        }
        section("START WITH A PALETTE");
        int[] accents = {0xff00e5ff, 0xff8a2be2, 0xffffe600};
        for (int i = 0; i < SLUGS.length; i++) {
            final String slug = SLUGS[i];
            LinearLayout card = card();
            LinearLayout palette = row();
            for (int color : new int[]{0xff080808, 0xff1b1c24, accents[i], 0xffeeeeee}) {
                View sample = new View(this); sample.setBackground(background(color, 12));
                LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(0, dp(38), 1); layout.setMargins(0, 0, dp(7), 0); palette.addView(sample, layout);
            }
            card.addView(palette); space(card, 14); card.addView(text(NAMES[i], 23, TEXT));
            card.addView(text("Dark + light · MIT licensed", 13, MUTED)); space(card, 12);
            card.addView(button("Use this source", () -> confirmReplace(() -> loadPreset(slug)), false));
            content.addView(card); space(content, 12);
        }
        space(content, 8); content.addView(button("Import .ouitheme", () -> {
            if (busy) return;
            confirmReplace(() -> {
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT); intent.addCategory(Intent.CATEGORY_OPENABLE); intent.setType("*/*");
                intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/zip", "application/octet-stream", "application/x-ouitheme"});
                startActivityForResult(intent, IMPORT);
            });
        }, true));
        space(content, 12); content.addView(text("Theme sources stay yours. Edit and export without connecting an apply bridge.", 14, MUTED));
    }

    private void studio() {
        if (theme == null) { content.addView(text("Choose or import a source from Library to start.", 17, MUTED)); return; }
        TextView name = text(theme.getName(), 22, TEXT); content.addView(name); space(content, 12);
        LinearLayout variants = row();
        for (boolean variant : new boolean[]{true, false}) {
            Button button = button(variant ? "Dark" : "Light", () -> {
                dark = variant; getPreferences(0).edit().putBoolean("dark", dark).apply(); render();
            }, dark == variant);
            button.setEnabled(!busy && theme.hasVariant(variant ? "dark" : "light"));
            variants.addView(button, new LinearLayout.LayoutParams(0, dp(48), 1));
        }
        content.addView(variants); space(content, 18);
        LinearLayout choices = row();
        String[] previews = {"Quick panel", "Settings", "Keyboard"};
        for (int i = 0; i < previews.length; i++) {
            final int index = i;
            Button button = button(previews[i], () -> { preview = index; render(); }, preview == i); button.setTextSize(11);
            choices.addView(button, new LinearLayout.LayoutParams(0, dp(48), 1));
        }
        content.addView(choices); space(content, 12);
        renderPreview(); space(content, 10);
        content.addView(text("Concept preview · actual phone rendering can differ", 12, MUTED)); space(content, 22);
        content.addView(button("Customize: " + APP_NAMES[appScope], () -> new AlertDialog.Builder(this).setTitle("Color scope")
            .setSingleChoiceItems(APP_NAMES, appScope, (dialog, which) -> { appScope = which; dialog.dismiss(); render(); }).show(), false));
        space(content, 12);
        if (appScope >= 4) content.addView(text("This app’s source overrides export with your theme. Current APK bindings are still needed.", 13, MUTED));
        section("COLORS");
        for (int i = 0; i < ROLES.length; i++) {
            final String role = ROLES[i], label = LABELS[i];
            LinearLayout row = row(); row.setPadding(dp(14), dp(10), dp(14), dp(10)); row.setBackground(background(PANEL, 14));
            View swatch = new View(this); swatch.setBackground(background(color(role, scopeKey()), 10)); row.addView(swatch, new LinearLayout.LayoutParams(dp(38), dp(38)));
            LinearLayout labels = column(); labels.setPadding(dp(14), 0, dp(8), 0);
            labels.addView(text(label, 16, TEXT)); labels.addView(text(hex(color(role, scopeKey())), 12, MUTED));
            row.addView(labels, new LinearLayout.LayoutParams(0, -2, 1)); row.addView(text("›", 25, MUTED));
            row.setContentDescription("Edit " + label + ", " + hex(color(role, scopeKey())));
            row.setMinimumHeight(dp(64)); row.setEnabled(!busy); row.setOnClickListener(view -> { if (!busy) editColor(role, label); });
            content.addView(row); space(content, 5);
        }
        space(content, 18); section("GEOMETRY");
        content.addView(text("Dialog and button corners have measured bindings. Other geometry controls remain preview and export values.", 13, MUTED));
        for (int i = 0; i < DIMENSIONS.length; i++) {
            final int index = i;
            content.addView(button(DIMENSION_NAMES[i] + "  ·  " + dimensionLabel(DIMENSIONS[i]), () -> editDimension(index), false));
        }
        space(content, 20); content.addView(button("Export theme source", this::exportSource, true));
        space(content, 12); content.addView(text("Imported icons, fonts and component styles are retained in export. Their editors and live rendering are still in development.", 13, MUTED));
    }

    private void renderPreview() {
        String scope = preview == 0 ? "systemui" : preview == 1 ? "settings" : "keyboard";
        String baseRole = preview == 0 ? "quickPanelBackground" : preview == 1 ? "settingsBackground" : "keyboardBackground";
        LinearLayout panel = column(); panel.setPadding(dp(18), dp(20), dp(18), dp(22)); panel.setBackground(background(color(baseRole, scope), 28));
        if (preview == 0) {
            TextView clock = text("09:41", 29, color("textPrimary", scope)); clock.setTypeface(Typeface.DEFAULT, Typeface.BOLD); panel.addView(clock);
            panel.addView(text("Saturday, September 19", 12, color("textSecondary", scope))); space(panel, 18);
            LinearLayout tiles = row();
            String[] labels = {"Wi-Fi", "Bluetooth", "Sound"};
            for (int i = 0; i < labels.length; i++) {
                boolean active = i != 2;
                TextView tile = text(labels[i], 12, color(active ? "quickTileIconActive" : "quickTileIconInactive", scope));
                tile.setGravity(Gravity.CENTER); tile.setBackground(background(color(active ? "quickTileActive" : "quickTileInactive", scope), 20));
                LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(0, dp(58), 1); layout.setMargins(0, 0, dp(6), 0); tiles.addView(tile, layout);
            }
            panel.addView(tiles); space(panel, 14);
            LinearLayout notification = column(); notification.setPadding(dp(14), dp(13), dp(14), dp(13)); notification.setBackground(background(color("notificationBackground", scope), 18));
            notification.addView(text("Your next idea", 16, color("notificationText", scope)));
            notification.addView(text("A fresh look, built around you.", 13, color("textSecondary", scope))); panel.addView(notification);
        } else if (preview == 1) {
            panel.addView(text("Settings", 27, color("textPrimary", scope))); space(panel, 16);
            LinearLayout settings = column(); settings.setPadding(dp(15), dp(10), dp(15), dp(10)); settings.setBackground(background(color("surface", scope), 18));
            for (String label : new String[]{"Connections", "Sounds and vibration", "Display"}) {
                LinearLayout line = row(); TextView icon = text("●", 20, color("settingsIcon", scope)); line.addView(icon);
                TextView title = text(label, 15, color("textPrimary", scope)); title.setPadding(dp(12), dp(12), 0, dp(12)); line.addView(title); settings.addView(line);
            }
            panel.addView(settings);
        } else {
            panel.addView(text("Type something beautiful", 18, color("textPrimary", scope))); space(panel, 18);
            for (String keys : new String[]{"QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"}) {
                LinearLayout line = row();
                for (char letter : keys.toCharArray()) {
                    TextView key = text(String.valueOf(letter), 13, color("keyboardKeyText", scope)); key.setGravity(Gravity.CENTER);
                    key.setBackground(background(color("keyboardKeyBackground", scope), 8));
                    LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(0, dp(35), 1); layout.setMargins(0, 0, dp(3), 0); line.addView(key, layout);
                }
                panel.addView(line); space(panel, 4);
            }
            TextView enter = text("↵", 19, color("onAccent", scope)); enter.setGravity(Gravity.CENTER); enter.setBackground(background(color("keyboardAccent", scope), 10)); panel.addView(enter, new LinearLayout.LayoutParams(-1, dp(35)));
        }
        content.addView(panel);
    }

    private void device() {
        LinearLayout card = card(); card.addView(text(android.os.Build.MODEL, 24, TEXT));
        card.addView(text("Android " + android.os.Build.VERSION.RELEASE + " · API " + android.os.Build.VERSION.SDK_INT, 14, MUTED));
        space(card, 12); card.addView(text(android.os.Build.DISPLAY, 12, MUTED)); space(card, 16);
        card.addView(text(device != null && device.optBoolean("measuredResourcesMatched") ? "Measured resources match" : "Resource match not yet verified", 16, ACCENT));
        card.addView(text("Theme application remains unverified", 13, MUTED)); content.addView(card); space(content, 18);
        content.addView(button("Verify installed targets", this::inspectDevice, true)); space(content, 12);
        if (device != null) {
            JSONArray targets = device.optJSONArray("targets");
            if (targets != null) for (int i = 0; i < targets.length(); i++) {
                JSONObject target = targets.optJSONObject(i); if (target == null) continue;
                LinearLayout item = card(); item.addView(text(target.optString("package"), 15, TEXT));
                item.addView(text(target.optBoolean("hashMatched") ? "APK hash matches this resource pack" : "Unverified or changed APK", 13, MUTED));
                if (target.has("reason")) item.addView(text(target.optString("reason"), 12, MUTED));
                content.addView(item); space(content, 10);
            }
            content.addView(button("Export device report", () -> createDocument(REPORT, "oneui-studio-device.json", "application/json"), false));
        }
        space(content, 20); section("FIRST COLLECTION");
        content.addView(text("Framework, quick panel, notifications and Settings have current resource sources. Phone, Contacts, Messages, My Files, Keyboard and Launcher still need their current APKs.", 15, MUTED));
        space(content, 20); section("APPLY BRIDGE");
        content.addView(text("A bridge is not connected. Export your source for the desktop compiler. Installation and phone appearance will be verified separately when your bridge is ready.", 15, MUTED));
        space(content, 14); content.addView(button("Review current coverage", () -> new AlertDialog.Builder(this).setTitle("Current collection")
            .setMessage("174 color resources and seven optional dialog/button dimensions are measured for build S948U1UEU4BZID. Shared active/dim tile states, fonts, icons and other geometry still need further mappings. A matching APK hash does not prove Samsung will accept an overlay.")
            .setPositiveButton("Done", null).show(), false));
    }

    private void history() {
        content.addView(text("Saved source changes and exports appear here. Application attempts will be recorded only after a real bridge is integrated.", 15, MUTED)); space(content, 20);
        if (history.length() == 0) content.addView(text("Your first creation starts in Library.", 17, TEXT));
        for (int i = history.length() - 1; i >= 0; i--) {
            JSONObject event = history.optJSONObject(i); if (event == null) continue;
            LinearLayout item = card(); item.addView(text(event.optString("description"), 16, TEXT));
            java.text.DateFormat date = java.text.DateFormat.getDateTimeInstance(java.text.DateFormat.MEDIUM, java.text.DateFormat.SHORT);
            item.addView(text(date.format(new java.util.Date(event.optLong("time"))), 12, MUTED)); content.addView(item); space(content, 10);
        }
    }

    private void editColor(String role, String label) {
        LinearLayout form = column(); form.setPadding(dp(20), dp(12), dp(20), dp(10));
        EditText hex = new EditText(this); hex.setSingleLine(true); hex.setText(hex(color(role, scopeKey()))); hex.setSelectAllOnFocus(true); form.addView(hex);
        View sample = new View(this); sample.setBackground(background(color(role, scopeKey()), 12)); form.addView(sample, new LinearLayout.LayoutParams(-1, dp(48))); space(form, 12);
        SeekBar[] channels = new SeekBar[4]; String[] names = {"Opacity", "Red", "Green", "Blue"}; boolean[] sync = {false};
        for (int i = 0; i < 4; i++) {
            form.addView(text(names[i], 12, MUTED)); SeekBar slider = new SeekBar(this); slider.setMax(255); channels[i] = slider;
            slider.setContentDescription(names[i]); form.addView(slider);
            slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
                public void onStartTrackingTouch(SeekBar view) {}
                public void onStopTrackingTouch(SeekBar view) {}
                public void onProgressChanged(SeekBar view, int value, boolean fromUser) {
                    if (!fromUser || sync[0]) return;
                    int color = Color.argb(channels[0].getProgress(), channels[1].getProgress(), channels[2].getProgress(), channels[3].getProgress());
                    hex.setText(MainActivity.hex(color));
                }
            });
        }
        Runnable update = () -> {
            String value = hex.getText().toString().trim();
            if (!value.matches("#[0-9a-fA-F]{8}")) return;
            int color = Color.parseColor(value); sync[0] = true;
            channels[0].setProgress(Color.alpha(color)); channels[1].setProgress(Color.red(color)); channels[2].setProgress(Color.green(color)); channels[3].setProgress(Color.blue(color));
            sync[0] = false; sample.setBackground(background(color, 12));
        };
        hex.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            public void onTextChanged(CharSequence s, int start, int before, int count) { update.run(); }
            public void afterTextChanged(Editable text) {}
        });
        update.run();
        ScrollView scroll = new ScrollView(this); scroll.addView(form);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle(label).setView(scroll).setNegativeButton("Cancel", null).setPositiveButton("Save color", null).create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
            try {
                String value = hex.getText().toString().trim().toUpperCase(Locale.ROOT);
                if (appScope == 0) theme.setColor(dark, role, value); else theme.setOverrideColor(dark, scopeKey(), role, value);
                dialog.dismiss(); persist("Saved " + label.toLowerCase(Locale.ROOT));
            } catch (Exception error) { hex.setError(error.getMessage()); }
        }));
        dialog.show();
    }

    private void editDimension(int index) {
        LinearLayout form = column(); form.setPadding(dp(20), dp(12), dp(20), dp(10));
        String unit = index == 4 ? "sp" : "dp";
        form.addView(text("Allowed: " + DIM_MIN[index] + "–" + DIM_MAX[index] + unit + ". This edits the global variant value.", 14, MUTED));
        EditText value = new EditText(this); value.setInputType(android.text.InputType.TYPE_CLASS_NUMBER | android.text.InputType.TYPE_NUMBER_FLAG_DECIMAL);
        value.setHint("Value in " + unit); form.addView(value);
        try { JSONObject token = theme.getTokens(dark).optJSONObject(DIMENSIONS[index]); if (token != null) value.setText(token.get("value").toString()); } catch (Exception ignored) {}
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle(DIMENSION_NAMES[index]).setView(form).setNegativeButton("Cancel", null).setPositiveButton("Save value", null).create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
            try {
                theme.setDimension(dark, DIMENSIONS[index], Double.parseDouble(value.getText().toString()), unit);
                dialog.dismiss(); persist("Saved " + DIMENSION_NAMES[index].toLowerCase(Locale.ROOT));
            } catch (Exception error) { value.setError("Enter a value in the allowed range"); }
        })); dialog.show();
    }

    private void loadPreset(String slug) {
        if (busy) return; busy = true; status = "Opening palette…"; render();
        worker.execute(() -> {
            try {
                ThemeSource opened = ThemeSource.builtin(getAssets(), "sources/" + slug + ".ouitheme");
                main.post(() -> { theme = opened; chooseAvailableVariant(); page = 1; busy = false; persist("Opened " + theme.getName()); });
            } catch (Exception error) { failure(error); }
        });
    }

    private void inspectDevice() {
        if (busy || pack == null) return; busy = true; status = "Checking installed resource APKs…"; render();
        worker.execute(() -> {
            try {
                JSONObject observed = DeviceInventory.inspect(this, pack);
                main.post(() -> { device = observed; busy = false; status = "Read-only inspection finished"; render(); });
            } catch (Exception error) { failure(error); }
        });
    }

    private void exportSource() {
        if (busy || theme == null) return;
        createDocument(EXPORT, theme.getId().replace('.', '-') + ".ouitheme", "application/octet-stream");
    }

    private void createDocument(int request, String filename, String mime) {
        if (busy) return;
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT); intent.addCategory(Intent.CATEGORY_OPENABLE); intent.setType(mime); intent.putExtra(Intent.EXTRA_TITLE, filename); startActivityForResult(intent, request);
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (result != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData(); busy = true; status = request == IMPORT ? "Checking imported source…" : "Writing your export…"; render();
        worker.execute(() -> {
            try {
                if (request == IMPORT) {
                    ThemeSource imported;
                    try (InputStream input = getContentResolver().openInputStream(uri)) {
                        if (input == null) throw new java.io.IOException("Could not read selected document");
                        imported = ThemeSource.read(input);
                    }
                    main.post(() -> { theme = imported; chooseAvailableVariant(); page = 1; busy = false; persist("Imported " + theme.getName()); });
                } else {
                    try (OutputStream output = getContentResolver().openOutputStream(uri, "wt")) {
                        if (output == null) throw new java.io.IOException("Could not write selected document");
                        if (request == EXPORT) theme.exportTo(output);
                        else if (request == REPORT && device != null) output.write(device.toString(2).getBytes(StandardCharsets.UTF_8));
                        else throw new java.io.IOException("No report is ready for export");
                    }
                    main.post(() -> { busy = false; persist(request == EXPORT ? "Exported " + theme.getName() : "Exported device report"); });
                }
            } catch (Exception error) { failure(error); }
        });
    }

    private void persist(String eventDescription) {
        if (theme == null) return;
        try {
            ThemeSource snapshot = theme.copy();
            JSONObject event = new JSONObject(); event.put("description", eventDescription); event.put("time", System.currentTimeMillis());
            history.put(event);
            while (history.length() > 50) history.remove(0);
            byte[] events = history.toString().getBytes(StandardCharsets.UTF_8);
            busy = true; status = "Saving your draft…"; render();
            worker.execute(() -> {
                AtomicFile draft = new AtomicFile(new File(getFilesDir(), "draft.ouitheme")); FileOutputStream output = null;
                try {
                    output = draft.startWrite(); snapshot.exportTo(output); draft.finishWrite(output); output = null;
                    AtomicFile journal = new AtomicFile(new File(getFilesDir(), "history.json"));
                    FileOutputStream historyOutput = journal.startWrite();
                    try { historyOutput.write(events); journal.finishWrite(historyOutput); } catch (Exception error) { journal.failWrite(historyOutput); throw error; }
                    main.post(() -> { busy = false; status = "Saved on this device"; render(); });
                } catch (Exception error) { if (output != null) draft.failWrite(output); failure(error); }
            });
        } catch (Exception error) { showError(error); }
    }

    private JSONArray readHistory() {
        try (InputStream input = new AtomicFile(new File(getFilesDir(), "history.json")).openRead()) {
            byte[] data = input.readNBytes(64 * 1024 + 1); if (data.length > 64 * 1024) return new JSONArray();
            return new JSONArray(new String(data, StandardCharsets.UTF_8));
        } catch (Exception ignored) { return new JSONArray(); }
    }

    private void confirmReplace(Runnable action) {
        if (busy) return;
        if (theme == null) { action.run(); return; }
        new AlertDialog.Builder(this).setTitle("Replace this draft?").setMessage("Export your current source first if you want to keep a separate copy.")
            .setNegativeButton("Cancel", null).setPositiveButton("Replace draft", (dialog, which) -> action.run()).show();
    }

    private String scopeKey() { return appScope == 0 ? null : APP_KEYS[appScope]; }

    private int color(String role, String scope) {
        try {
            JSONObject token = theme.getTokens(dark).optJSONObject(role);
            JSONObject overrides = theme.getOverrides(dark).optJSONObject(scope == null ? "" : scope);
            if (overrides != null && overrides.optJSONObject(role) != null) token = overrides.getJSONObject(role);
            if (token != null) return Color.parseColor(token.getString("value"));
            if (role.equals("quickTileActive") || role.endsWith("Accent") || role.equals("settingsIcon") || role.equals("link")) return color("accent", scope);
            if (role.equals("quickTileIconActive")) return color("onAccent", scope);
            if (role.endsWith("Background")) return color("surface", scope);
            return color(role.equals("quickTileIconInactive") || role.equals("outline") ? "textSecondary" : "textPrimary", scope);
        } catch (Exception ignored) { return MUTED; }
    }

    private String dimensionLabel(String role) {
        try { JSONObject token = theme.getTokens(dark).optJSONObject(role); return token == null ? "Original" : token.get("value") + token.getString("unit"); }
        catch (Exception ignored) { return "Original"; }
    }

    private void failure(Exception error) { main.post(() -> { if (isFinishing() || isDestroyed()) return; busy = false; status = "Operation did not finish"; render(); showError(error); }); }
    private void showError(Exception error) { if (!isFinishing() && !isDestroyed()) new AlertDialog.Builder(this).setTitle("Could not finish").setMessage(error.getMessage() == null ? error.getClass().getSimpleName() : error.getMessage()).setPositiveButton("OK", null).show(); }
    private void section(String label) { TextView view = text(label, 11, MUTED); view.setLetterSpacing(.09f); content.addView(view); space(content, 12); }
    private int dp(float value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private static String hex(int color) { return String.format(Locale.ROOT, "#%08X", color); }
    private LinearLayout column() { LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL); return layout; }
    private LinearLayout row() { LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.HORIZONTAL); layout.setGravity(Gravity.CENTER_VERTICAL); return layout; }
    private LinearLayout card() { LinearLayout card = column(); card.setPadding(dp(18), dp(18), dp(18), dp(18)); card.setBackground(background(PANEL, 22)); return card; }
    private TextView text(String value, float size, int color) { TextView view = new TextView(this); view.setText(value); view.setTextSize(size); view.setTextColor(color); view.setFontFeatureSettings("kern"); return view; }
    private Button button(String label, Runnable action, boolean primary) {
        Button view = new Button(this); view.setText(label); view.setTextSize(14); view.setAllCaps(false); view.setTextColor(primary ? BG : TEXT); view.setBackground(background(primary ? ACCENT : PANEL, 16)); view.setMinHeight(dp(48)); view.setPadding(dp(12), dp(8), dp(12), dp(8)); view.setEnabled(!busy); view.setOnClickListener(ignored -> action.run()); return view;
    }
    private GradientDrawable background(int color, int radius) { GradientDrawable shape = new GradientDrawable(); shape.setColor(color); shape.setCornerRadius(dp(radius)); return shape; }
    private void space(LinearLayout parent, int height) { parent.addView(new View(this), new LinearLayout.LayoutParams(1, dp(height))); }
}
