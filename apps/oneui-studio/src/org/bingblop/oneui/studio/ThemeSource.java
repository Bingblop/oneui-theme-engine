package org.bingblop.oneui.studio;

import android.content.res.AssetManager;
import android.graphics.BitmapFactory;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.math.BigDecimal;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.zip.CRC32;
import java.util.zip.Deflater;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import java.util.zip.ZipOutputStream;

/**
 * Validated, editable appearance source. This class never extracts files to disk,
 * executes theme data, installs packages, or makes device/bridge calls.
 *
 * JSON accessors and entry snapshots are defensive copies. Successful mutation
 * preserves every unedited accepted field and asset. Source validation establishes
 * format validity only; compatibility packs and application eligibility are separate.
 */
public final class ThemeSource {
    public static final int MAX_COMPRESSED_BYTES = 20 * 1024 * 1024;
    public static final int MAX_EXPANDED_BYTES = 80 * 1024 * 1024;
    public static final int MAX_ENTRIES = 500;
    public static final int MAX_JSON_BYTES = 1024 * 1024;
    public static final int MAX_RASTER_DIMENSION = 8192;

    private static final Set<String> COLORS = set("background", "surface", "accent", "onAccent",
            "textPrimary", "textSecondary", "quickTileInactive", "quickTileActive",
            "quickTileIconActive", "quickTileIconInactive", "quickPanelBackground",
            "notificationBackground", "notificationText", "settingsBackground", "settingsIcon",
            "keyboardBackground", "keyboardKeyBackground", "keyboardKeyText", "keyboardAccent",
            "statusBarIcons", "navigationBarBackground", "navigationBarIcons", "outline", "link", "error");
    private static final Set<String> BASE_COLORS = set("background", "surface", "accent", "onAccent",
            "textPrimary", "textSecondary", "quickTileInactive");
    private static final Set<String> DIMENSIONS = set("cornerRadius", "quickTileRadius",
            "keyboardKeyRadius", "navigationBarHeight", "bodyTextSize");
    private static final Set<String> FONTS = set("bodyFont", "headlineFont");
    private static final Set<String> TARGETS = set("framework", "systemui", "settings", "phone",
            "keyboard", "files", "messages", "contacts");
    private static final Set<String> COMPONENTS = set("device.palette", "quick-panel.palette",
            "settings.palette", "keyboard.palette", "wallpaper", "launcher.icons", "phone.palette",
            "contacts.palette", "messages.palette", "files.palette", "typography", "systemui.geometry",
            "component.drawables");
    private static final Set<String> STYLE_COMPONENTS = set("quickTile", "keyboardKey", "card", "dialog", "button");
    private static final String EXTENSION = "^extension:[a-z][a-z0-9.-]+/[a-z][a-z0-9.-]+$";
    private static final String ID = "^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$";
    private static final String VERSION = "^[0-9]+\\.[0-9]+\\.[0-9]+$";
    private static final String ASSET = "^assets/[A-Za-z0-9_-]+\\.(png|jpg|jpeg|webp|ttf|otf)$";

    private JSONObject manifest;
    private final Map<String, JSONObject> variants;
    private final Map<String, JSONObject> overrides;
    private final Map<String, byte[]> entries;

    private ThemeSource(JSONObject manifest, Map<String, JSONObject> variants,
                        Map<String, JSONObject> overrides, Map<String, byte[]> entries) {
        this.manifest = manifest;
        this.variants = variants;
        this.overrides = overrides;
        this.entries = entries;
    }

    /** Reads one complete ZIP; does not close the caller's stream. */
    public static ThemeSource read(InputStream input) throws IOException {
        if (input == null) throw error("Missing source stream");
        byte[] archive = readBounded(input, MAX_COMPRESSED_BYTES, "Compressed source");
        Map<String, ZipMetadata> metadata = inspectZip(archive);
        Map<String, byte[]> files = new TreeMap<>();
        Set<String> seen = new HashSet<>();
        long total = 0;
        try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(archive), StandardCharsets.UTF_8)) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                String path = entry.getName();
                ZipMetadata meta = metadata.get(path);
                if (meta == null || !seen.add(path)) throw error("ZIP entry disagreement: " + path);
                int limit = path.endsWith(".json") || path.equals("LICENSE.txt") ? MAX_JSON_BYTES : MAX_EXPANDED_BYTES;
                byte[] bytes = readBounded(zip, (int) Math.min(limit, MAX_EXPANDED_BYTES - total), path);
                total += bytes.length;
                CRC32 crc = new CRC32(); crc.update(bytes);
                if (bytes.length != meta.expandedSize || crc.getValue() != meta.crc)
                    throw error("ZIP size or CRC disagreement: " + path);
                if (entry.isDirectory()) {
                    if (bytes.length != 0 || !set("tokens/", "overrides/", "assets/").contains(path))
                        throw error("Unknown source directory: " + path);
                } else {
                    files.put(path, bytes);
                }
                zip.closeEntry();
            }
        } catch (IllegalArgumentException ex) {
            throw new IOException("Invalid ZIP encoding", ex);
        }
        if (seen.size() != metadata.size()) throw error("ZIP has unread or hidden entries");
        return validateFiles(files);
    }

    public static ThemeSource builtin(AssetManager assets, String assetPath) throws IOException {
        if (assets == null || assetPath == null) throw error("Missing built-in source");
        try (InputStream input = assets.open(assetPath)) { return read(input); }
    }

    public synchronized String getId() { return manifest.optString("id"); }
    public synchronized String getName() { return manifest.optString("name"); }
    public synchronized JSONObject getManifest() { return uncheckedCopy(manifest); }
    public synchronized boolean hasVariant(String variant) { return variants.containsKey(variant); }

    /** Requires the exact requested variant; never silently substitutes day/night. */
    public synchronized JSONObject getTokens(boolean dark) throws IOException {
        return copyObject(requireVariant(dark ? "dark" : "light"));
    }

    public synchronized JSONObject getOverrides(boolean dark) throws IOException {
        String variant = dark ? "dark" : "light";
        requireVariant(variant);
        JSONObject value = overrides.get(variant);
        return value == null ? new JSONObject() : copyObject(value);
    }

    public synchronized void setColor(boolean dark, String role, String argb) throws IOException {
        setColor(dark ? "dark" : "light", role, argb);
    }

    public synchronized void setColor(String variant, String role, String argb) throws IOException {
        JSONObject original = requireVariant(variant);
        checkColor(role, argb);
        JSONObject changed = copyObject(original);
        put(changed, role, color(argb));
        variants.put(variant, changed);
    }

    public synchronized void setDimension(boolean dark, String role, double value, String unit) throws IOException {
        String variant = dark ? "dark" : "light";
        JSONObject original = requireVariant(variant);
        checkDimension(role, value, unit);
        JSONObject token = new JSONObject();
        put(token, "type", "dimension"); put(token, "value", value); put(token, "unit", unit);
        JSONObject changed = copyObject(original);
        put(changed, role, token);
        variants.put(variant, changed);
    }

    public synchronized void setOverrideColor(boolean dark, String targetKey, String role, String argb) throws IOException {
        String variant = dark ? "dark" : "light";
        requireVariant(variant);
        checkTarget(targetKey);
        checkColor(role, argb);
        JSONObject old = overrides.get(variant);
        JSONObject changed = old == null ? new JSONObject() : copyObject(old);
        JSONObject target = changed.has(targetKey) ? object(value(changed, targetKey), targetKey) : new JSONObject();
        put(target, role, color(argb));
        put(changed, targetKey, target);
        JSONObject changedManifest = copyObject(manifest);
        JSONObject paths = changedManifest.has("overrides")
                ? object(value(changedManifest, "overrides"), "overrides") : new JSONObject();
        put(paths, variant, "overrides/" + variant + ".json");
        put(changedManifest, "overrides", paths);
        // Commit both only after every validation and JSON operation succeeded.
        manifest = changedManifest;
        overrides.put(variant, changed);
    }

    /** Copies editable JSON while sharing private asset bytes that can never be mutated. */
    public synchronized ThemeSource copy() throws IOException {
        return new ThemeSource(copyObject(manifest), copyObjects(variants), copyObjects(overrides), entries);
    }

    /** Sorted entries, canonical JSON, fixed timestamp and fixed deflate level. */
    public synchronized void exportTo(OutputStream output) throws IOException {
        if (output == null) throw error("Missing export stream");
        Map<String, byte[]> snapshot = snapshot(false);
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(new LimitedOutputStream(buffer, MAX_COMPRESSED_BYTES), StandardCharsets.UTF_8)) {
            zip.setLevel(Deflater.BEST_COMPRESSION);
            for (Map.Entry<String, byte[]> file : snapshot.entrySet()) {
                ZipEntry entry = new ZipEntry(file.getKey());
                entry.setTime(0L);
                zip.putNextEntry(entry);
                zip.write(file.getValue());
                zip.closeEntry();
            }
        }
        output.write(buffer.toByteArray());
    }

    public synchronized Map<String, byte[]> getRawEntries() throws IOException {
        return Collections.unmodifiableMap(snapshot(true));
    }

    private Map<String, byte[]> snapshot(boolean defensiveBytes) throws IOException {
        Map<String, byte[]> result = new TreeMap<>();
        for (Map.Entry<String, byte[]> entry : entries.entrySet())
            result.put(entry.getKey(), defensiveBytes ? entry.getValue().clone() : entry.getValue());
        result.put("manifest.json", canonicalBytes(manifest));
        for (Map.Entry<String, JSONObject> entry : variants.entrySet())
            result.put("tokens/" + entry.getKey() + ".json", canonicalBytes(entry.getValue()));
        for (Map.Entry<String, JSONObject> entry : overrides.entrySet())
            result.put("overrides/" + entry.getKey() + ".json", canonicalBytes(entry.getValue()));
        return result;
    }

    private static Map<String, JSONObject> copyObjects(Map<String, JSONObject> objects) throws IOException {
        Map<String, JSONObject> result = new LinkedHashMap<>();
        for (Map.Entry<String, JSONObject> entry : objects.entrySet())
            result.put(entry.getKey(), copyObject(entry.getValue()));
        return result;
    }

    private JSONObject requireVariant(String variant) throws IOException {
        JSONObject value = variants.get(variant);
        if (value == null) throw error("Source has no " + variant + " variant");
        return value;
    }

    private static ThemeSource validateFiles(Map<String, byte[]> files) throws IOException {
        if (!files.containsKey("manifest.json") || !files.containsKey("LICENSE.txt"))
            throw error("Source needs manifest.json and LICENSE.txt");
        String license = decodeUtf8(files.get("LICENSE.txt"));
        if (license.trim().isEmpty() || license.indexOf('\0') >= 0) throw error("License must be nonempty UTF-8 text");
        JSONObject manifest = parseObject(files.get("manifest.json"));
        keys(manifest, set("format", "id", "version", "name", "author", "license", "licenseFile", "tokenApi",
                "targetIntent", "variants", "assets", "components", "overrides", "stylePack", "appearance"),
                set("format", "id", "version", "name", "author", "license", "licenseFile", "tokenApi",
                        "targetIntent", "variants", "assets", "components"), "manifest");
        exact(manifest, "format", "oneui-studio.source/1");
        exact(manifest, "tokenApi", "oneui-studio.tokens/1");
        exact(manifest, "licenseFile", "LICENSE.txt");
        pattern(string(manifest, "id", 1, 128), ID, "theme id");
        pattern(string(manifest, "version", 1, MAX_JSON_BYTES), VERSION, "theme version");
        string(manifest, "name", 1, 80); string(manifest, "author", 1, 120); string(manifest, "license", 1, 100);
        JSONObject intent = object(value(manifest, "targetIntent"), "targetIntent");
        keys(intent, set("manufacturer", "uiFamily", "uiMajor"), set("manufacturer", "uiFamily", "uiMajor"), "targetIntent");
        exact(intent, "manufacturer", "Samsung"); exact(intent, "uiFamily", "One UI");
        if (decimal(value(intent, "uiMajor"), "uiMajor").compareTo(BigDecimal.valueOf(9)) != 0)
            throw error("Unsupported UI intention");

        Set<String> allowed = set("manifest.json", "LICENSE.txt");
        Map<String, String> assets = new HashMap<>();
        JSONArray assetList = array(value(manifest, "assets"), "assets");
        if (assetList.length() > 100) throw error("Too many declared assets");
        for (int i = 0; i < assetList.length(); i++) {
            JSONObject asset = object(arrayValue(assetList, i), "asset");
            keys(asset, set("path", "kind", "license"), set("path", "kind", "license"), "asset");
            String path = string(asset, "path", 1, 160); pattern(path, ASSET, "asset path");
            String kind = string(asset, "kind", 1, 20);
            if (!set("wallpaper", "icon", "font").contains(kind)) throw error("Unknown asset kind");
            string(asset, "license", 1, 100);
            if (assets.put(path, kind) != null) throw error("Duplicate asset declaration: " + path);
            byte[] bytes = files.get(path);
            if (bytes == null) throw error("Missing declared asset: " + path);
            validateAsset(path, kind, bytes); allowed.add(path);
        }

        JSONArray components = array(value(manifest, "components"), "components");
        if (components.length() == 0 || components.length() > 128) throw error("Invalid component count");
        Set<String> componentIds = new HashSet<>();
        for (int i = 0; i < components.length(); i++) {
            JSONObject component = object(arrayValue(components, i), "component");
            keys(component, set("id", "required"), set("id", "required"), "component");
            String id = string(component, "id", 1, 160);
            if (!COMPONENTS.contains(id) && !id.matches(EXTENSION)) throw error("Unknown component: " + id);
            if (!(value(component, "required") instanceof Boolean)) throw error("Component required must be boolean");
            if (!componentIds.add(id)) throw error("Duplicate component declaration: " + id);
        }
        if (manifest.has("stylePack")) {
            JSONObject pack = object(value(manifest, "stylePack"), "stylePack");
            keys(pack, set("id", "version"), set("id", "version"), "stylePack");
            pattern(string(pack, "id", 1, 128), ID, "style-pack id");
            pattern(string(pack, "version", 1, MAX_JSON_BYTES), VERSION, "style-pack version");
        }

        Map<String, JSONObject> variants = new LinkedHashMap<>();
        JSONObject paths = object(value(manifest, "variants"), "variants");
        keys(paths, set("dark", "light"), Collections.emptySet(), "variants");
        if (paths.length() == 0) throw error("At least one variant is required");
        for (String variant : names(paths)) {
            String path = "tokens/" + variant + ".json"; exact(paths, variant, path);
            JSONObject tokens = parseRequired(files, path); validateTokens(tokens, true, assets);
            variants.put(variant, tokens); allowed.add(path);
        }
        Map<String, JSONObject> overrides = new LinkedHashMap<>();
        if (manifest.has("overrides")) {
            JSONObject overridePaths = object(value(manifest, "overrides"), "overrides");
            keys(overridePaths, set("dark", "light"), Collections.emptySet(), "overrides");
            if (overridePaths.length() == 0) throw error("Empty override declaration");
            for (String variant : names(overridePaths)) {
                if (!variants.containsKey(variant)) throw error("Overrides reference missing variant");
                String path = "overrides/" + variant + ".json"; exact(overridePaths, variant, path);
                JSONObject targets = parseRequired(files, path);
                if (targets.length() == 0) throw error("Empty per-app overrides");
                for (String target : names(targets)) {
                    checkTarget(target); validateTokens(object(value(targets, target), target), false, assets);
                }
                overrides.put(variant, targets); allowed.add(path);
            }
        }
        if (manifest.has("appearance")) validateAppearance(object(value(manifest, "appearance"), "appearance"), variants, assets);
        for (String path : files.keySet()) if (!allowed.contains(path)) throw error("Undeclared source file: " + path);
        Map<String, byte[]> owned = new TreeMap<>();
        // validateFiles only receives freshly read or privately created byte arrays.
        // No caller ever obtains these arrays: public snapshots clone them.
        owned.putAll(files);
        return new ThemeSource(manifest, variants, overrides, Collections.unmodifiableMap(owned));
    }

    private static void validateTokens(JSONObject tokens, boolean baseline, Map<String, String> assets) throws IOException {
        if (tokens.length() == 0) throw error("Empty token values");
        if (baseline) for (String role : BASE_COLORS) if (!tokens.has(role)) throw error("Missing baseline color: " + role);
        for (String role : names(tokens)) {
            JSONObject token = object(value(tokens, role), role);
            if (COLORS.contains(role)) {
                keys(token, set("type", "value"), set("type", "value"), role);
                exact(token, "type", "color"); checkColor(role, string(token, "value", 9, 9));
            } else if (DIMENSIONS.contains(role)) {
                keys(token, set("type", "value", "unit"), set("type", "value", "unit"), role);
                exact(token, "type", "dimension");
                Object dimension = value(token, "value");
                checkDimension(role, number(dimension, role), string(token, "unit", 2, 2));
                exactRange(dimension, dimensionMin(role), dimensionMax(role), role);
            } else if (FONTS.contains(role)) {
                keys(token, set("type", "value"), set("type", "value"), role);
                exact(token, "type", "fontAsset");
                String path = string(token, "value", 1, 160);
                if (!path.matches("^assets/[A-Za-z0-9_-]+\\.(ttf|otf)$") || !"font".equals(assets.get(path)))
                    throw error("Unresolved declared font: " + path);
            } else throw error("Unknown semantic token: " + role);
        }
    }

    private static void validateAppearance(JSONObject appearance, Map<String, JSONObject> variants,
                                           Map<String, String> assets) throws IOException {
        keys(appearance, set("dark", "light"), Collections.emptySet(), "appearance");
        if (appearance.length() == 0) throw error("Empty appearance settings");
        for (String variant : names(appearance)) {
            if (!variants.containsKey(variant)) throw error("Appearance references missing variant");
            JSONObject settings = object(value(appearance, variant), "appearance variant");
            keys(settings, set("icons", "components"), Collections.emptySet(), "appearance variant");
            if (settings.length() == 0) throw error("Empty appearance variant");
            if (settings.has("icons")) {
                JSONObject icons = object(value(settings, "icons"), "icons");
                if (icons.length() == 0 || icons.length() > 128) throw error("Invalid icon binding count");
                for (String slot : names(icons)) {
                    pattern(slot, "^[a-z][A-Za-z0-9]*(?:\\.[a-z][A-Za-z0-9]*)+$", "semantic icon slot");
                    String path = string(icons, slot, 1, 160);
                    if (!path.matches("^assets/[A-Za-z0-9_-]+\\.(png|webp)$") || !"icon".equals(assets.get(path)))
                        throw error("Unresolved declared icon: " + path);
                }
            }
            if (settings.has("components")) {
                JSONObject components = object(value(settings, "components"), "appearance components");
                keys(components, STYLE_COMPONENTS, Collections.emptySet(), "appearance components");
                if (components.length() == 0) throw error("Empty component styles");
                for (String component : names(components)) {
                    JSONObject style = object(value(components, component), "component style");
                    keys(style, set("shape", "fillRole", "strokeRole", "strokeWidthDp", "radiusRole"),
                            set("shape", "fillRole"), "component style");
                    String shape = string(style, "shape", 1, 32);
                    if (!set("rectangle", "roundedRectangle", "circle").contains(shape)) throw error("Unknown declarative shape");
                    if (!COLORS.contains(string(style, "fillRole", 1, 80))) throw error("Unknown shape fill role");
                    if (style.has("strokeRole") && !COLORS.contains(string(style, "strokeRole", 1, 80))) throw error("Unknown shape stroke role");
                    if (style.has("radiusRole") && !set("cornerRadius", "quickTileRadius", "keyboardKeyRadius")
                            .contains(string(style, "radiusRole", 1, 80))) throw error("Unknown shape radius role");
                    if (style.has("strokeWidthDp")) {
                        exactRange(value(style, "strokeWidthDp"), 0, 8, "strokeWidthDp");
                    }
                }
            }
        }
    }

    private static void checkColor(String role, String argb) throws IOException {
        if (!COLORS.contains(role)) throw error("Unknown color role: " + role);
        if (argb == null || !argb.matches("^#[0-9A-F]{8}$")) throw error("Color must be #AARRGGBB");
    }

    private static JSONObject color(String argb) throws IOException {
        JSONObject token = new JSONObject(); put(token, "type", "color"); put(token, "value", argb); return token;
    }

    private static void checkDimension(String role, double value, String unit) throws IOException {
        if (!DIMENSIONS.contains(role) || !Double.isFinite(value)) throw error("Unknown or nonfinite dimension");
        double min = dimensionMin(role), max = dimensionMax(role);
        if (value < min || value > max || !(role.equals("bodyTextSize") ? "sp" : "dp").equals(unit))
            throw error("Invalid " + role + " dimension or unit");
    }

    private static double dimensionMin(String role) {
        return role.equals("navigationBarHeight") ? 16 : role.equals("bodyTextSize") ? 10 : 0;
    }
    private static double dimensionMax(String role) {
        return role.equals("navigationBarHeight") ? 96 : role.equals("bodyTextSize") ? 28
                : role.equals("keyboardKeyRadius") ? 24 : 32;
    }
    private static BigDecimal decimal(Object value, String label) throws IOException {
        number(value, label);
        try { return new BigDecimal(value.toString()); }
        catch (NumberFormatException ex) { throw new IOException("Invalid " + label + " number", ex); }
    }
    private static void exactRange(Object value, double min, double max, String label) throws IOException {
        BigDecimal number = decimal(value, label);
        if (number.compareTo(BigDecimal.valueOf(min)) < 0 || number.compareTo(BigDecimal.valueOf(max)) > 0)
            throw error(label + " outside its allowed range");
    }

    private static void checkTarget(String target) throws IOException {
        if (target == null || target.length() > 160 || (!TARGETS.contains(target) && !target.matches(EXTENSION)))
            throw error("Unknown abstract override target: " + target);
    }

    private static void validateAsset(String path, String kind, byte[] bytes) throws IOException {
        String extension = path.substring(path.lastIndexOf('.') + 1);
        if (kind.equals("font")) {
            if (!set("ttf", "otf").contains(extension)) throw error("Font extension mismatch");
            validateFont(bytes, extension); return;
        }
        if (!set("png", "jpg", "jpeg", "webp").contains(extension)) throw error("Raster extension mismatch");
        String mime;
        if (extension.equals("png")) {
            byte[] signature = {(byte)137,80,78,71,13,10,26,10};
            if (bytes.length < 33 || !Arrays.equals(Arrays.copyOf(bytes, 8), signature)) throw error("Invalid PNG signature");
            int cursor = 8; boolean end = false, data = false, header = false;
            while (cursor < bytes.length) {
                if (cursor + 12L > bytes.length) throw error("Truncated PNG chunk");
                long length = be32(bytes, cursor);
                if (length + cursor + 12L > bytes.length) throw error("PNG chunk outside asset");
                String type = new String(bytes, cursor + 4, 4, StandardCharsets.US_ASCII);
                if (!header && (!type.equals("IHDR") || length != 13)) throw error("Missing PNG header");
                header = true;
                CRC32 crc = new CRC32(); crc.update(bytes, cursor + 4, (int) length + 4);
                if (crc.getValue() != be32(bytes, cursor + 8 + (int)length)) throw error("PNG CRC mismatch");
                cursor += (int) length + 12;
                if (type.equals("IDAT")) data = true;
                if (type.equals("IEND")) { if (length != 0 || cursor != bytes.length) throw error("Trailing PNG content"); end = true; break; }
            }
            if (!end || !data) throw error("Incomplete PNG"); mime = "image/png";
        } else if (extension.equals("webp")) {
            if (bytes.length < 20 || !ascii(bytes, 0, "RIFF") || !ascii(bytes, 8, "WEBP")
                    || le32(bytes, 4) + 8 != bytes.length) throw error("Invalid WebP container");
            mime = "image/webp";
        } else {
            if (bytes.length < 4 || (bytes[0]&255) != 255 || (bytes[1]&255) != 216
                    || (bytes[bytes.length-2]&255) != 255 || (bytes[bytes.length-1]&255) != 217)
                throw error("Invalid JPEG container");
            mime = "image/jpeg";
        }
        BitmapFactory.Options options = new BitmapFactory.Options(); options.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(bytes, 0, bytes.length, options);
        if (options.outWidth < 1 || options.outHeight < 1 || options.outWidth > MAX_RASTER_DIMENSION
                || options.outHeight > MAX_RASTER_DIMENSION || !mime.equals(options.outMimeType))
            throw error("Invalid raster or dimensions exceed 8192: " + path);
    }

    private static void validateFont(byte[] bytes, String extension) throws IOException {
        if (bytes.length < 12) throw error("Truncated font");
        boolean otf = ascii(bytes, 0, "OTTO");
        boolean ttf = be32(bytes, 0) == 0x00010000L || ascii(bytes, 0, "true");
        if (!(extension.equals("otf") ? otf : ttf)) throw error("Font signature/extension mismatch");
        int count = be16(bytes, 4);
        if (count == 0 || count > 256 || 12L + 16L * count > bytes.length) throw error("Invalid font table directory");
        Map<String, int[]> tables = new HashMap<>();
        for (int i=0; i<count; i++) {
            int pos = 12 + i*16; String tag = new String(bytes, pos, 4, StandardCharsets.US_ASCII);
            long offset = be32(bytes, pos+8), length = be32(bytes, pos+12);
            if (offset < 12L + 16L*count || length == 0 || offset + length > bytes.length || tables.containsKey(tag))
                throw error("Invalid font table bounds");
            tables.put(tag, new int[]{(int)offset,(int)length});
        }
        int[] head=tables.get("head"), cmap=tables.get("cmap"), name=tables.get("name");
        if (head==null || head[1]<54 || cmap==null || cmap[1]<4 || name==null || name[1]<6
                || be32(bytes,head[0]+12)!=0x5f0f3cf5L) throw error("Missing or invalid font metadata");
        int units=be16(bytes,head[0]+18); if (units<16 || units>16384) throw error("Invalid font units");
        int records=be16(bytes,name[0]+2), stringOffset=be16(bytes,name[0]+4);
        if (records==0 || records>2048 || 6L+records*12L>name[1] || stringOffset>name[1]) throw error("Invalid font names");
        for (int i=0;i<records;i++) {
            int pos=name[0]+6+i*12;
            if ((long)stringOffset+be16(bytes,pos+10)+be16(bytes,pos+8)>name[1]) throw error("Font name outside table");
        }
    }

    private static JSONObject parseRequired(Map<String, byte[]> files, String path) throws IOException {
        if (!files.containsKey(path)) throw error("Missing declared JSON: " + path);
        return parseObject(files.get(path));
    }

    private static JSONObject parseObject(byte[] bytes) throws IOException {
        if (bytes.length > MAX_JSON_BYTES) throw error("JSON exceeds 1 MiB");
        return object(new StrictJson(decodeUtf8(bytes)).parse(), "JSON document");
    }

    private static JSONObject copyObject(JSONObject object) throws IOException { return parseObject(canonicalBytes(object)); }
    private static JSONObject uncheckedCopy(JSONObject object) {
        try { return copyObject(object); } catch (IOException ex) { throw new IllegalStateException("Validated JSON changed unexpectedly", ex); }
    }

    private static byte[] canonicalBytes(JSONObject object) throws IOException {
        StringBuilder text=new StringBuilder(); writeCanonical(object,text); text.append('\n');
        byte[] bytes=text.toString().getBytes(StandardCharsets.UTF_8);
        if (bytes.length>MAX_JSON_BYTES) throw error("JSON exceeds 1 MiB"); return bytes;
    }

    private static void writeCanonical(Object value, StringBuilder text) throws IOException {
        if (value instanceof JSONObject) {
            JSONObject object=(JSONObject)value; text.append('{'); boolean first=true;
            for (String key:names(object)) { if(!first)text.append(','); first=false; text.append(JSONObject.quote(key)).append(':'); writeCanonical(value(object,key),text); }
            text.append('}');
        } else if (value instanceof JSONArray) {
            JSONArray array=(JSONArray)value; text.append('[');
            for(int i=0;i<array.length();i++){if(i>0)text.append(',');writeCanonical(arrayValue(array,i),text);} text.append(']');
        } else if (value instanceof String) text.append(JSONObject.quote((String)value));
        else if (value instanceof Boolean || value instanceof Number) text.append(value.toString());
        else if (value==JSONObject.NULL) text.append("null"); else throw error("Unsupported JSON value");
    }

    private static String decodeUtf8(byte[] bytes) throws IOException {
        try { return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString(); }
        catch (CharacterCodingException ex) { throw new IOException("Malformed UTF-8",ex); }
    }

    private static byte[] readBounded(InputStream input, int limit, String label) throws IOException {
        ByteArrayOutputStream output=new ByteArrayOutputStream(); byte[] buffer=new byte[8192]; int count;
        while((count=input.read(buffer))!=-1){
            if(count==0){int next=input.read();if(next==-1)break;if(output.size()>=limit)throw error(label+" exceeds limit");output.write(next);continue;}
            if((long)output.size()+count>limit)throw error(label+" exceeds limit");output.write(buffer,0,count);
        }
        return output.toByteArray();
    }

    private static Map<String, ZipMetadata> inspectZip(byte[] zip) throws IOException {
        int eocd=-1;
        for(int i=zip.length-22;i>=Math.max(0,zip.length-65557);i--)
            if(le32(zip,i)==0x06054b50L && (long)i+22+le16(zip,i+20)==zip.length){eocd=i;break;}
        if(eocd<0)throw error("Missing ZIP central directory");
        int count=le16(zip,eocd+10);
        if(le16(zip,eocd+4)!=0 || le16(zip,eocd+6)!=0 || le16(zip,eocd+8)!=count
                || count==0 || count>MAX_ENTRIES)throw error("Unsupported ZIP disk/count");
        long directorySize=le32(zip,eocd+12), directoryOffset=le32(zip,eocd+16);
        if(directoryOffset+directorySize!=eocd || directoryOffset>zip.length)throw error("Invalid ZIP directory bounds");
        Map<String, ZipMetadata> result=new LinkedHashMap<>(); int cursor=(int)directoryOffset; long expanded=0;
        for(int i=0;i<count;i++){
            if((long)cursor+46>eocd || le32(zip,cursor)!=0x02014b50L)throw error("Invalid ZIP directory record");
            int flags=le16(zip,cursor+8), method=le16(zip,cursor+10), nameLength=le16(zip,cursor+28), extraLength=le16(zip,cursor+30), commentLength=le16(zip,cursor+32);
            long compressed=le32(zip,cursor+20), size=le32(zip,cursor+24), offset=le32(zip,cursor+42), attrs=le32(zip,cursor+38);
            long next=(long)cursor+46+nameLength+extraLength+commentLength;
            if(next>eocd || le16(zip,cursor+34)!=0 || le16(zip,cursor+6)>20 || (flags&~0x080e)!=0
                    || (method!=0 && method!=8) || compressed==0xffffffffL || size==0xffffffffL || offset==0xffffffffL)
                throw error("Unsupported encrypted/ZIP64 ZIP entry");
            String name=decodeUtf8(Arrays.copyOfRange(zip,cursor+46,cursor+46+nameLength)); checkPath(name);
            int mode=(int)(attrs>>>16), kind=mode&0xf000;
            if(kind==0xa000 || (kind!=0 && kind!=0x8000 && kind!=0x4000))throw error("ZIP symlink/special entry rejected");
            if(kind==0x8000 && (mode&0111)!=0)throw error("Executable ZIP entry rejected");
            if(kind==0x4000 && !name.endsWith("/"))throw error("ZIP directory name mismatch");
            if(offset>=directoryOffset || compressed>MAX_COMPRESSED_BYTES || size>MAX_EXPANDED_BYTES)throw error("ZIP entry outside source limits");
            expanded+=size;if(expanded>MAX_EXPANDED_BYTES)throw error("Expanded source exceeds 80 MiB");
            checkExtra(zip,cursor+46+nameLength,extraLength);
            ZipMetadata meta=new ZipMetadata(name, flags, method, compressed, size, le32(zip,cursor+16), (int)offset);
            if(result.put(name,meta)!=null)throw error("Duplicate ZIP path: "+name);
            cursor=(int)next;
        }
        if(cursor!=eocd)throw error("Unclaimed ZIP directory bytes");
        List<ZipMetadata> ordered=new ArrayList<>(result.values()); Collections.sort(ordered,(a,b)->Integer.compare(a.offset,b.offset));
        int expected=0;
        for(ZipMetadata meta:ordered){
            int offset=meta.offset;
            if(offset!=expected || (long)offset+30>directoryOffset || le32(zip,offset)!=0x04034b50L)throw error("Overlapping/hidden ZIP local entry");
            int names=le16(zip,offset+26), extras=le16(zip,offset+28);long dataOffset=(long)offset+30+names+extras;
            if(dataOffset+meta.compressedSize>directoryOffset || le16(zip,offset+4)>20
                    || le16(zip,offset+6)!=meta.flags || le16(zip,offset+8)!=meta.method)throw error("ZIP local metadata mismatch");
            String name=decodeUtf8(Arrays.copyOfRange(zip,offset+30,offset+30+names));
            if(!meta.name.equals(name))throw error("ZIP local/central path mismatch");checkExtra(zip,offset+30+names,extras);
            long localCrc=le32(zip,offset+14), localCompressed=le32(zip,offset+18), localSize=le32(zip,offset+22);
            if((meta.flags&8)==0){
                if(localCrc!=meta.crc || localCompressed!=meta.compressedSize || localSize!=meta.expandedSize)throw error("ZIP local size/CRC mismatch");
            }else if((localCrc!=0 && localCrc!=meta.crc) || (localCompressed!=0 && localCompressed!=meta.compressedSize)
                    || (localSize!=0 && localSize!=meta.expandedSize))throw error("ZIP descriptor metadata mismatch");
            long end=dataOffset+meta.compressedSize;
            if((meta.flags&8)!=0){
                if(end+12>directoryOffset)throw error("Truncated ZIP descriptor");
                if(le32(zip,(int)end)==0x08074b50L)end+=4;
                if(end+12>directoryOffset || le32(zip,(int)end)!=meta.crc || le32(zip,(int)end+4)!=meta.compressedSize
                        || le32(zip,(int)end+8)!=meta.expandedSize)throw error("ZIP descriptor disagreement");end+=12;
            }
            expected=(int)end;
        }
        if(expected!=directoryOffset)throw error("Hidden ZIP data before central directory");
        return result;
    }

    private static void checkExtra(byte[] bytes,int offset,int length)throws IOException{
        int end=offset+length;
        while(offset<end){if(offset+4>end)throw error("Truncated ZIP extra field");int tag=le16(bytes,offset),size=le16(bytes,offset+2);offset+=4;
            if(offset+size>end)throw error("Truncated ZIP extra field");
            // Reject link/mode/alternate-name metadata, including PKWARE and ASi
            // Unix link targets. Only benign timestamp and uid/gid metadata is read.
            if(tag==0x5455){if(size<1||size>13||(bytes[offset]&~7)!=0)throw error("Invalid ZIP timestamp metadata");}
            else if(tag==0x000a){if(size!=32||le16(bytes,offset+4)!=1||le16(bytes,offset+6)!=24)throw error("Unsupported NTFS ZIP metadata");}
            else if(tag==0x7875){
                if(size<5||bytes[offset]!=1)throw error("Invalid ZIP uid/gid metadata");
                int uid=bytes[offset+1]&255;
                if(uid<1||uid>8||uid+3>size)throw error("Invalid ZIP uid metadata");
                int gid=bytes[offset+2+uid]&255;
                if(gid<1||gid>8||uid+gid+3!=size)throw error("Invalid ZIP gid metadata");
            }else throw error("Unsupported ZIP link/extra metadata");
            offset+=size;
        }
    }
    private static void checkPath(String path)throws IOException{
        if(path.isEmpty() || path.length()>160 || !path.matches("^[A-Za-z0-9._/-]+$") || path.startsWith("/"))throw error("Unsafe ZIP path");
        String[] parts=path.split("/",-1);
        for(int i=0;i<parts.length;i++)if(parts[i].equals(".") || parts[i].equals("..") || (parts[i].isEmpty() && i!=parts.length-1))throw error("Unsafe ZIP path");
        if(!set("manifest.json", "LICENSE.txt", "tokens/dark.json", "tokens/light.json",
                "overrides/dark.json", "overrides/light.json", "tokens/", "overrides/", "assets/").contains(path)
                && !path.matches(ASSET))throw error("Unknown or executable source path: "+path);
    }
    private static final class ZipMetadata{
        final String name;final int flags,method,offset;final long compressedSize,expandedSize,crc;
        ZipMetadata(String name,int flags,int method,long compressed,long expanded,long crc,int offset){this.name=name;this.flags=flags;this.method=method;compressedSize=compressed;expandedSize=expanded;this.crc=crc;this.offset=offset;}
    }
    private static final class LimitedOutputStream extends OutputStream{
        final OutputStream target;final long limit;long count;
        LimitedOutputStream(OutputStream target,long limit){this.target=target;this.limit=limit;}
        public void write(int value)throws IOException{if(++count>limit)throw error("Export exceeds compressed source limit");target.write(value);}
        public void write(byte[] bytes,int offset,int length)throws IOException{if(count+length>limit)throw error("Export exceeds compressed source limit");target.write(bytes,offset,length);count+=length;}
    }

    private static final class StrictJson{
        final String text;int at;
        StrictJson(String text){this.text=text;}
        Object parse()throws IOException{Object value=read(0);space();if(at!=text.length())throw error("Trailing JSON content");return value;}
        Object read(int depth)throws IOException{
            if(depth>64)throw error("JSON nesting exceeds 64");space();if(at>=text.length())throw error("Truncated JSON");char c=text.charAt(at);
            if(c=='{'){at++;JSONObject result=new JSONObject();space();if(take('}'))return result;
                do{space();if(at>=text.length()||text.charAt(at)!='\"')throw error("JSON object needs quoted key");String key=quoted();space();expect(':');
                    if(result.has(key))throw error("Duplicate JSON key: "+key);put(result,key,read(depth+1));space();if(take('}'))return result;expect(',');}while(true);}
            if(c=='['){at++;JSONArray result=new JSONArray();space();if(take(']'))return result;
                do{result.put(read(depth+1));space();if(take(']'))return result;expect(',');}while(true);}
            if(c=='\"')return quoted();if(c=='t'){literal("true");return Boolean.TRUE;}if(c=='f'){literal("false");return Boolean.FALSE;}if(c=='n'){literal("null");return JSONObject.NULL;}
            int start=at;if(take('-') && at>=text.length())throw error("Invalid JSON number");
            if(take('0')){if(at<text.length()&&Character.isDigit(text.charAt(at)))throw error("Leading JSON zero");}
            else{if(at>=text.length()||text.charAt(at)<'1'||text.charAt(at)>'9')throw error("Invalid JSON value");while(at<text.length()&&digit(text.charAt(at)))at++;}
            boolean decimal=false;if(take('.')){decimal=true;int before=at;while(at<text.length()&&digit(text.charAt(at)))at++;if(before==at)throw error("Invalid JSON fraction");}
            if(at<text.length()&&(text.charAt(at)=='e'||text.charAt(at)=='E')){decimal=true;at++;if(at<text.length()&&(text.charAt(at)=='+'||text.charAt(at)=='-'))at++;int before=at;while(at<text.length()&&digit(text.charAt(at)))at++;if(before==at)throw error("Invalid JSON exponent");}
            String number=text.substring(start,at);if(number.length()>128)throw error("JSON number too long");
            try{if(!decimal)return Long.valueOf(number);}catch(NumberFormatException ignored){}
            try{BigDecimal value=new BigDecimal(number);if(!Double.isFinite(value.doubleValue()))throw error("Nonfinite JSON number");return value;}catch(NumberFormatException ex){throw new IOException("Invalid JSON number",ex);}
        }
        String quoted()throws IOException{
            expect('\"');StringBuilder result=new StringBuilder();
            while(at<text.length()){char c=text.charAt(at++);if(c=='\"'){String value=result.toString();
                    for(int i=0;i<value.length();i++){char v=value.charAt(i);if(Character.isHighSurrogate(v)){if(++i>=value.length()||!Character.isLowSurrogate(value.charAt(i)))throw error("Unpaired JSON surrogate");}else if(Character.isLowSurrogate(v))throw error("Unpaired JSON surrogate");}return value;}
                if(c<32)throw error("Unescaped JSON control character");if(c!='\\'){result.append(c);continue;}if(at>=text.length())throw error("Truncated JSON escape");c=text.charAt(at++);
                switch(c){case '\"':case '\\':case '/':result.append(c);break;case 'b':result.append('\b');break;case 'f':result.append('\f');break;case 'n':result.append('\n');break;case 'r':result.append('\r');break;case 't':result.append('\t');break;
                    case 'u':if(at+4>text.length())throw error("Truncated Unicode escape");int code=0;for(int i=0;i<4;i++){char digit=text.charAt(at++);int hex=digit>='0'&&digit<='9'?digit-'0':digit>='a'&&digit<='f'?digit-'a'+10:digit>='A'&&digit<='F'?digit-'A'+10:-1;if(hex<0)throw error("Invalid Unicode escape");code=code*16+hex;}result.append((char)code);break;default:throw error("Unknown JSON escape");}
            }throw error("Unterminated JSON string");
        }
        void literal(String word)throws IOException{if(!text.startsWith(word,at))throw error("Invalid JSON literal");at+=word.length();}
        void space(){while(at<text.length()&&" \t\r\n".indexOf(text.charAt(at))>=0)at++;}
        boolean take(char c){if(at<text.length()&&text.charAt(at)==c){at++;return true;}return false;}
        void expect(char c)throws IOException{if(!take(c))throw error("Expected JSON "+c);}
        static boolean digit(char c){return c>='0'&&c<='9';}
    }

    private static Set<String> set(String... values){return new HashSet<>(Arrays.asList(values));}
    private static List<String> names(JSONObject object){List<String> result=new ArrayList<>();Iterator<String> keys=object.keys();while(keys.hasNext())result.add(keys.next());Collections.sort(result);return result;}
    private static void keys(JSONObject object,Set<String> allowed,Set<String> required,String label)throws IOException{
        for(String key:names(object))if(!allowed.contains(key))throw error("Unknown "+label+" field: "+key);
        for(String key:required)if(!object.has(key))throw error("Missing "+label+" field: "+key);
    }
    private static Object value(JSONObject object,String key)throws IOException{try{return object.get(key);}catch(JSONException ex){throw new IOException("Missing JSON value: "+key,ex);}}
    private static Object arrayValue(JSONArray array,int index)throws IOException{try{return array.get(index);}catch(JSONException ex){throw new IOException("Missing array value",ex);}}
    private static JSONObject object(Object value,String label)throws IOException{if(!(value instanceof JSONObject))throw error(label+" must be object");return (JSONObject)value;}
    private static JSONArray array(Object value,String label)throws IOException{if(!(value instanceof JSONArray))throw error(label+" must be array");return (JSONArray)value;}
    private static String string(JSONObject object,String key,int min,int max)throws IOException{
        Object value=value(object,key);if(!(value instanceof String))throw error(key+" must be string");String text=(String)value;int length=text.codePointCount(0,text.length());
        if(length<min||length>max)throw error("Invalid "+key+" length");return text;
    }
    private static double number(Object value,String label)throws IOException{if(!(value instanceof Number)||!Double.isFinite(((Number)value).doubleValue()))throw error(label+" must be finite number");return ((Number)value).doubleValue();}
    private static void exact(JSONObject object,String key,String expected)throws IOException{if(!expected.equals(value(object,key)))throw error("Invalid "+key);}
    private static void pattern(String text,String regex,String label)throws IOException{if(!text.matches(regex))throw error("Invalid "+label);}
    private static void put(JSONObject object,String key,Object value)throws IOException{try{object.put(key,value);}catch(JSONException ex){throw new IOException("Invalid JSON value",ex);}}
    private static IOException error(String message){return new IOException(message);}
    private static int le16(byte[] bytes,int at){return (bytes[at]&255)|((bytes[at+1]&255)<<8);}
    private static long le32(byte[] bytes,int at){return (long)le16(bytes,at)|((long)le16(bytes,at+2)<<16);}
    private static int be16(byte[] bytes,int at){return ((bytes[at]&255)<<8)|(bytes[at+1]&255);}
    private static long be32(byte[] bytes,int at){return ((long)be16(bytes,at)<<16)|be16(bytes,at+2);}
    private static boolean ascii(byte[] bytes,int at,String value){if(at<0||at+value.length()>bytes.length)return false;for(int i=0;i<value.length();i++)if(bytes[at+i]!=(byte)value.charAt(i))return false;return true;}
}
