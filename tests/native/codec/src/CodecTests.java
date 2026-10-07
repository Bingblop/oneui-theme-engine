import android.content.res.AssetManager;
import org.bingblop.oneui.studio.ThemeSource;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;

/** Host codec behavior tests against the exact repository source. */
public final class CodecTests {
    static Path ROOT;
    static Path BUNDLES;
    static Path ASSETS;
    static final List<String> failures = new ArrayList<>();
    static int passed;
    interface Check { void run() throws Exception; }

    static void test(String label, Check check) {
        try { check.run(); passed++; }
        catch (Throwable e) {
            String failure = label + ": " + e.getClass().getSimpleName() + ": " + e.getMessage();
            failures.add(failure); System.out.println("FAIL " + failure);
        }
    }
    static void require(boolean success, String message) { if (!success) throw new AssertionError(message); }
    static ThemeSource load(Path path) throws IOException {
        try (InputStream in = Files.newInputStream(path)) { return ThemeSource.read(in); }
    }
    static byte[] dump(ThemeSource source) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream(); source.exportTo(out); return out.toByteArray();
    }
    static Map<String, byte[]> entries(byte[] data) throws IOException {
        TreeMap<String, byte[]> result = new TreeMap<>();
        try (ZipInputStream in = new ZipInputStream(new ByteArrayInputStream(data))) {
            ZipEntry entry;
            while ((entry = in.getNextEntry()) != null) {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                byte[] chunk = new byte[8192]; int count;
                while ((count = in.read(chunk)) != -1) bytes.write(chunk, 0, count);
                if (!entry.isDirectory()) require(result.put(entry.getName(), bytes.toByteArray()) == null, "export has duplicate file names");
            }
        }
        return result;
    }
    static JSONObject json(byte[] bytes) { return new JSONObject(new String(bytes, StandardCharsets.UTF_8)); }
    static void preserved(Path path) throws IOException {
        byte[] input = Files.readAllBytes(path);
        ThemeSource source = load(path);
        byte[] output = dump(source);
        Map<String, byte[]> before = entries(input), after = entries(output);
        require(before.keySet().equals(after.keySet()), "archive file inventory changed: " + after.keySet());
        for (String name : before.keySet()) {
            if (name.endsWith(".json")) require(json(before.get(name)).similar(json(after.get(name))), "JSON changed: " + name);
            else require(Arrays.equals(before.get(name), after.get(name)), "payload changed: " + name);
        }
        require(Arrays.equals(output, dump(source)), "repeat export is not deterministic");
        require(Arrays.equals(output, dump(ThemeSource.read(new ByteArrayInputStream(output)))), "export/read/export is not stable");
        require(source.getId().equals(json(before.get("manifest.json")).getString("id")), "wrong id");
        require(source.getName().equals(json(before.get("manifest.json")).getString("name")), "wrong name");
    }
    static void mustReject(Path fixture) throws Exception {
        try { load(fixture); throw new AssertionError("accepted invalid source"); }
        catch (IOException expected) { }
    }
    static void invalidMutation(String label, CheckFactory change) {
        test("mutation rollback / " + label, () -> {
            ThemeSource source = load(BUNDLES.resolve("amoled-black.ouitheme"));
            byte[] before = dump(source);
            boolean rejected = false;
            try { change.run(source); } catch (IOException expected) { rejected = true; }
            require(rejected, "invalid mutation was accepted");
            require(Arrays.equals(before, dump(source)), "failed mutation changed source");
        });
    }
    interface CheckFactory { void run(ThemeSource source) throws Exception; }

    static void fixtureTests(Path expectations) throws IOException {
        if (!Files.exists(expectations)) throw new IOException("Missing required fixture index: " + expectations);
        JSONArray cases = new JSONArray(Files.readString(expectations));
        for (int i = 0; i < cases.length(); i++) {
            JSONObject item = cases.getJSONObject(i);
            String name = item.getString("path");
            Path path = ROOT.resolve("fixtures").resolve(name);
            test((item.getBoolean("accept") ? "accept / " : "reject / ") + name,
                () -> { if (item.getBoolean("accept")) preserved(path); else mustReject(path); });
        }
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("Usage: CodecTests <external-output-directory> <repository-root>");
        ROOT = Paths.get(args[0]).toAbsolutePath().normalize();
        Path repo = Paths.get(args[1]).toAbsolutePath().normalize();
        BUNDLES = repo.resolve("docs/design/theme-source/bundles");
        ASSETS = repo.resolve("apps/oneui-studio/assets");
        for (String name : new String[] {"amoled-black", "neon-violet", "cyberpunk-gold"}) {
            test("seed source roundtrip / " + name, () -> preserved(BUNDLES.resolve(name + ".ouitheme")));
        }
        test("builtin reads actual app asset bundle", () -> {
            Path assets = ASSETS;
            ThemeSource source = ThemeSource.builtin(new AssetManager(assets), "sources/amoled-black.ouitheme");
            require(source.getId().equals("org.bingblop.amoled-black"), "wrong builtin source");
            require(Arrays.equals(dump(source), dump(load(assets.resolve("sources/amoled-black.ouitheme")))), "builtin source differs from direct asset read");
            require(source.hasVariant("dark") && source.hasVariant("light"), "builtin variant inventory differs");
        });
        fixtureTests(ROOT.resolve("fixtures/schema/expectations.json"));
        fixtureTests(ROOT.resolve("fixtures/zip/expectations.json"));
        test("canonical determinism across JSON and ZIP ordering", () -> {
            byte[] a = dump(load(ROOT.resolve("fixtures/schema/valid-rich.ouitheme")));
            byte[] b = dump(load(ROOT.resolve("fixtures/schema/valid-rich-reordered.ouitheme")));
            require(Arrays.equals(a, b), "semantically equal source exports have different bytes");
        });
        test("copy independence and deep defensive JSON accessors", () -> {
            ThemeSource original = load(ROOT.resolve("fixtures/schema/valid-rich.ouitheme"));
            byte[] before = dump(original);
            ThemeSource copy = original.copy();
            require(Arrays.equals(before, dump(copy)), "copy changes source");
            copy.setColor(true, "accent", "#80123456");
            require(Arrays.equals(before, dump(original)), "editing copy changes original");
            byte[] copiedAfterEdit = dump(copy);
            original.setColor(false, "accent", "#FF112233");
            require(Arrays.equals(copiedAfterEdit, dump(copy)), "editing original changes copy");
            before = dump(original);
            JSONObject manifest = original.getManifest();
            manifest.put("name", "mutated externally");
            manifest.getJSONObject("variants").put("dark", "evil.json");
            manifest.getJSONArray("assets").getJSONObject(0).put("license", "changed");
            require(Arrays.equals(before, dump(original)), "getManifest exposes mutable internals");
            JSONObject tokens = original.getTokens(true);
            tokens.getJSONObject("accent").put("value", "#FF000001");
            require(Arrays.equals(before, dump(original)), "getTokens exposes mutable internals");
            Map<String, byte[]> raw = original.getRawEntries();
            raw.get("manifest.json")[0] = 0;
            raw.get("assets/icon.png")[0] = 0;
            try { raw.remove("tokens/dark.json"); } catch (UnsupportedOperationException readOnlyMap) { }
            require(Arrays.equals(before, dump(original)), "getRawEntries exposes mutable internals");
        });
        test("missing variant is explicit", () -> {
            ThemeSource source = load(BUNDLES.resolve("amoled-black.ouitheme"));
            require(source.hasVariant("dark") && !source.hasVariant("light"), "incorrect variant declaration");
            try { source.getTokens(false); throw new AssertionError("missing light variant returned tokens"); }
            catch (IOException expected) { }
        });
        test("successful colors dimensions and override edits preserve other source declarations", () -> {
            ThemeSource source = load(ROOT.resolve("fixtures/schema/valid-rich.ouitheme"));
            Map<String, byte[]> before = entries(dump(source));
            JSONObject oldManifest = source.getManifest();
            source.setColor(true, "accent", "#80123456");
            source.setColor("light", "background", "#FFEEDDCC");
            source.setDimension(true, "cornerRadius", 0, "dp");
            source.setDimension(true, "bodyTextSize", 10, "sp");
            source.setOverrideColor(true, "extension:org.example/app.palette", "accent", "#00112233");
            source.setOverrideColor(true, "settings", "settingsBackground", "#FF101112");
            ThemeSource readback = ThemeSource.read(new ByteArrayInputStream(dump(source)));
            require(oldManifest.similar(readback.getManifest()), "existing manifest declarations changed");
            require(readback.getTokens(true).getJSONObject("accent").getString("value").equals("#80123456"), "dark color not edited");
            require(readback.getTokens(false).getJSONObject("background").getString("value").equals("#FFEEDDCC"), "light color not edited");
            require(readback.getTokens(true).getJSONObject("cornerRadius").getDouble("value") == 0, "dimension not edited");
            Map<String, byte[]> after = entries(dump(readback));
            require(json(after.get("overrides/dark.json")).getJSONObject("keyboard").similar(json(before.get("overrides/dark.json")).getJSONObject("keyboard")), "untouched keyboard override lost");
            require(json(after.get("overrides/dark.json")).getJSONObject("settings").getJSONObject("settingsBackground").getString("value").equals("#FF101112"), "new override not exported");
            for (String name : before.keySet()) if (!name.equals("tokens/dark.json") && !name.equals("tokens/light.json") && !name.equals("overrides/dark.json")) {
                require(Arrays.equals(before.get(name), after.get(name)), "unrelated file changed: " + name);
            }
        });
        test("new override declaration is persisted", () -> {
            ThemeSource source = load(BUNDLES.resolve("amoled-black.ouitheme"));
            source.setOverrideColor(true, "keyboard", "keyboardAccent", "#80112233");
            ThemeSource loaded = ThemeSource.read(new ByteArrayInputStream(dump(source)));
            require(loaded.getManifest().getJSONObject("overrides").getString("dark").equals("overrides/dark.json"), "new override file undeclared");
            require(json(entries(dump(loaded)).get("overrides/dark.json")).getJSONObject("keyboard").getJSONObject("keyboardAccent").getString("value").equals("#80112233"), "new override not persisted");
        });
        test("read handles a short-read stream with available zero", () -> {
            byte[] bytes = Files.readAllBytes(BUNDLES.resolve("amoled-black.ouitheme"));
            InputStream slow = new ByteArrayInputStream(bytes) {
                @Override public int available() { return 0; }
                @Override public synchronized int read(byte[] b, int off, int len) { return super.read(b, off, Math.min(len, 1)); }
            };
            require(ThemeSource.read(slow).getId().equals("org.bingblop.amoled-black"), "short read input failed");
        });

        invalidMutation("unknown color role", s -> s.setColor(true, "rawResource", "#FF112233"));
        invalidMutation("dimension role as color", s -> s.setColor(true, "cornerRadius", "#FF112233"));
        invalidMutation("lowercase color", s -> s.setColor(true, "accent", "#ffaabbcc"));
        invalidMutation("six digit color", s -> s.setColor(true, "accent", "#AABBCC"));
        invalidMutation("null color", s -> s.setColor(true, "accent", null));
        invalidMutation("missing light color", s -> s.setColor(false, "accent", "#FF112233"));
        invalidMutation("unknown variant color", s -> s.setColor("dusk", "accent", "#FF112233"));
        invalidMutation("null variant color", s -> s.setColor((String)null, "accent", "#FF112233"));
        invalidMutation("negative dimension", s -> s.setDimension(true, "cornerRadius", -1, "dp"));
        invalidMutation("dimension above maximum", s -> s.setDimension(true, "quickTileRadius", 33, "dp"));
        invalidMutation("keyboard radius above maximum", s -> s.setDimension(true, "keyboardKeyRadius", 25, "dp"));
        invalidMutation("navigation below minimum", s -> s.setDimension(true, "navigationBarHeight", 15, "dp"));
        invalidMutation("body text below minimum", s -> s.setDimension(true, "bodyTextSize", 9, "sp"));
        invalidMutation("body text wrong unit", s -> s.setDimension(true, "bodyTextSize", 16, "dp"));
        invalidMutation("radius wrong unit", s -> s.setDimension(true, "cornerRadius", 16, "sp"));
        invalidMutation("color role as dimension", s -> s.setDimension(true, "accent", 16, "dp"));
        invalidMutation("NaN dimension", s -> s.setDimension(true, "cornerRadius", Double.NaN, "dp"));
        invalidMutation("infinite dimension", s -> s.setDimension(true, "cornerRadius", Double.POSITIVE_INFINITY, "dp"));
        invalidMutation("missing light dimension", s -> s.setDimension(false, "cornerRadius", 16, "dp"));
        invalidMutation("unknown override target", s -> s.setOverrideColor(true, "com.android.systemui", "accent", "#FF112233"));
        invalidMutation("invalid extension override target", s -> s.setOverrideColor(true, "extension:INVALID/app", "accent", "#FF112233"));
        invalidMutation("null override target", s -> s.setOverrideColor(true, null, "accent", "#FF112233"));
        invalidMutation("unknown override color", s -> s.setOverrideColor(true, "keyboard", "unknown", "#FF112233"));
        invalidMutation("bad new override color", s -> s.setOverrideColor(true, "keyboard", "accent", "#AABBCC"));
        invalidMutation("missing light override", s -> s.setOverrideColor(false, "keyboard", "accent", "#FF112233"));

        JSONObject report = new JSONObject().put("passed", passed).put("failed", failures.size()).put("failures", new JSONArray(failures));
        Files.writeString(ROOT.resolve("results.json"), report.toString(2) + "\n");
        System.out.println("RESULT " + passed + " passed, " + failures.size() + " failed");
        if (!failures.isEmpty()) System.exit(1);
    }
}
