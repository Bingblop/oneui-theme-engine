import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Stream;
import org.bingblop.oneui.studio.ThemeSource;
import org.bingblop.oneui.studio.WorkspaceIO;
import org.json.JSONArray;
import org.json.JSONObject;

/** File-backed host checks for the exact production WorkspaceIO implementation. */
public final class WorkspaceIOTests {
    private static Path output;
    private static Path baseline;
    private static int passed;
    private static final List<String> failures = new ArrayList<>();
    private static final JSONArray results = new JSONArray();
    private interface Check { void run() throws Exception; }

    private static void test(String label, Check check) {
        JSONObject result = new JSONObject().put("name", label);
        try {
            check.run(); passed++; result.put("passed", true);
        } catch (Throwable error) {
            String detail = error.getClass().getSimpleName() + ": " + error.getMessage();
            failures.add(label + ": " + detail);
            result.put("passed", false).put("error", detail);
            System.out.println("FAIL " + label + ": " + detail);
        }
        results.put(result);
    }

    private static void require(boolean condition, String detail) {
        if (!condition) throw new AssertionError(detail);
    }

    private static void expectIOException(Check operation) throws Exception {
        try { operation.run(); }
        catch (IOException expected) { return; }
        throw new AssertionError("operation unexpectedly succeeded");
    }

    private static Path workspace() throws IOException {
        return Files.createTempDirectory(output, "workspace-");
    }

    private static ThemeSource source() throws IOException {
        try (InputStream input = Files.newInputStream(baseline)) { return ThemeSource.read(input); }
    }

    private static ThemeSource edited(String color) throws IOException {
        ThemeSource value = source(); value.setColor(true, "accent", color); return value;
    }

    private static byte[] export(ThemeSource value) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        value.exportTo(bytes); return bytes.toByteArray();
    }

    private static String accent(ThemeSource value) throws IOException {
        return value.getTokens(true).getJSONObject("accent").getString("value");
    }

    private static JSONArray history(int count) {
        JSONArray value = new JSONArray();
        for (int i = 0; i < count; i++) value.put(new JSONObject().put("description", "event-" + i).put("time", i));
        return value;
    }

    private static void noTemporaryFiles(Path directory) throws IOException {
        try (Stream<Path> entries = Files.list(directory)) {
            require(entries.noneMatch(path -> {
                String name = path.getFileName().toString();
                return (name.startsWith("source-") || name.startsWith("history-")) && name.endsWith(".tmp");
            }), "save left a temporary file");
        }
    }

    private static void checks() {
        test("successful commit writes readable source and history", () -> {
            Path directory = workspace(); WorkspaceIO io = new WorkspaceIO(directory.toFile());
            ThemeSource candidate = edited("#FF102030");
            WorkspaceIO.Commit commit = io.save(candidate, new JSONArray(), "first save");
            require(commit.historySaved, "history did not commit");
            require(Arrays.equals(export(candidate), Files.readAllBytes(directory.resolve("draft.ouitheme"))), "saved source differs");
            require(Arrays.equals(export(commit.source), export(io.readDraft())), "committed source differs from reopened draft");
            require(io.readHistory().length() == 1, "history event missing");
            require(io.readHistory().getJSONObject(0).getString("description").equals("first save"), "history description differs");
            require(io.readHistory().getJSONObject(0).getLong("time") > 0, "history timestamp missing");
            noTemporaryFiles(directory);
        });
        test("successful commit snapshots candidate instead of aliasing it", () -> {
            Path directory = workspace(); WorkspaceIO io = new WorkspaceIO(directory.toFile());
            ThemeSource candidate = edited("#FF102030");
            WorkspaceIO.Commit commit = io.save(candidate, new JSONArray(), "snapshot");
            byte[] saved = Files.readAllBytes(directory.resolve("draft.ouitheme"));
            candidate.setColor(true, "accent", "#FF405060");
            require(accent(commit.source).equals("#FF102030"), "candidate edit changed committed snapshot");
            require(Arrays.equals(saved, export(commit.source)), "snapshot changed after candidate edit");
            require(Arrays.equals(saved, Files.readAllBytes(directory.resolve("draft.ouitheme"))), "candidate edit changed persisted draft");
        });
        test("editing returned committed source does not mutate candidate or saved bytes", () -> {
            Path directory = workspace(); WorkspaceIO io = new WorkspaceIO(directory.toFile());
            ThemeSource candidate = edited("#FF102030");
            WorkspaceIO.Commit commit = io.save(candidate, new JSONArray(), "snapshot");
            byte[] saved = Files.readAllBytes(directory.resolve("draft.ouitheme"));
            commit.source.setColor(true, "accent", "#FF405060");
            require(accent(candidate).equals("#FF102030"), "committed source aliases candidate");
            require(Arrays.equals(saved, Files.readAllBytes(directory.resolve("draft.ouitheme"))), "returned source edit changed persisted draft");
            require(accent(io.readDraft()).equals("#FF102030"), "reopened draft changed without save");
        });
        test("successful history commit copies prior events", () -> {
            Path directory = workspace(); WorkspaceIO io = new WorkspaceIO(directory.toFile());
            JSONArray prior = history(2); String before = prior.toString();
            WorkspaceIO.Commit commit = io.save(source(), prior, "new");
            require(prior.toString().equals(before), "save mutated prior history");
            prior.getJSONObject(0).put("description", "mutated prior"); prior.put(new JSONObject());
            require(commit.history.length() == 3, "commit history aliases prior array");
            require(commit.history.getJSONObject(0).getString("description").equals("event-0"), "commit history aliases prior event");
            commit.history.getJSONObject(1).put("description", "mutated return");
            require(io.readHistory().getJSONObject(1).getString("description").equals("event-1"), "returned history aliases disk");
        });
        test("refused workspace preserves previously saved draft and history", () -> {
            Path directory = workspace(); WorkspaceIO io = new WorkspaceIO(directory.toFile());
            io.save(source(), new JSONArray(), "old");
            byte[] oldSource = Files.readAllBytes(directory.resolve("draft.ouitheme"));
            byte[] oldHistory = Files.readAllBytes(directory.resolve("history.json"));
            // Simulate an unavailable directory before commit without depending on OS
            // permissions or whether the host tests happen to run as root.
            File unavailable = new File(directory.toString()) {
                @Override public boolean isDirectory() { return false; }
            };
            expectIOException(() -> new WorkspaceIO(unavailable).save(edited("#FF405060"), io.readHistory(), "failed"));
            require(Arrays.equals(oldSource, Files.readAllBytes(directory.resolve("draft.ouitheme"))), "failed save changed old source");
            require(Arrays.equals(oldHistory, Files.readAllBytes(directory.resolve("history.json"))), "failed save changed old history");
            noTemporaryFiles(directory);
        });
        test("failed atomic source replacement preserves blocked target and cleans temporary file", () -> {
            Path directory = workspace(); WorkspaceIO io = new WorkspaceIO(directory.toFile());
            io.save(source(), new JSONArray(), "old");
            Path draft = directory.resolve("draft.ouitheme"); byte[] oldSource = Files.readAllBytes(draft);
            byte[] oldHistory = Files.readAllBytes(directory.resolve("history.json"));
            Files.delete(draft); Files.createDirectory(draft);
            Path retained = draft.resolve("retained.ouitheme"); Files.write(retained, oldSource);
            expectIOException(() -> io.save(edited("#FF405060"), io.readHistory(), "failed"));
            require(Files.isDirectory(draft), "failed move replaced blocked target");
            require(Arrays.equals(oldSource, Files.readAllBytes(retained)), "failed move changed retained old source");
            require(Arrays.equals(oldHistory, Files.readAllBytes(directory.resolve("history.json"))), "failed source move published history");
            noTemporaryFiles(directory);
        });
        test("missing workspace fails without creating it", () -> {
            Path directory = workspace().resolve("missing");
            expectIOException(() -> new WorkspaceIO(directory.toFile()).save(source(), new JSONArray(), "missing"));
            require(!Files.exists(directory), "save unexpectedly created unavailable workspace");
        });
        test("regular file workspace is preserved on failed save", () -> {
            Path path = workspace().resolve("not-a-directory"); byte[] marker = {1, 2, 3}; Files.write(path, marker);
            expectIOException(() -> new WorkspaceIO(path.toFile()).save(source(), new JSONArray(), "invalid workspace"));
            require(Arrays.equals(marker, Files.readAllBytes(path)), "failed save changed workspace file");
        });
        test("failed history replacement keeps committed source and cleans journal", () -> {
            Path directory = workspace(); WorkspaceIO io = new WorkspaceIO(directory.toFile());
            io.save(source(), new JSONArray(), "old"); JSONArray prior = io.readHistory(); String priorBytes = prior.toString();
            Path journal = directory.resolve("history.json"); Files.delete(journal); Files.createDirectory(journal);
            Path marker = journal.resolve("keep"); Files.writeString(marker, "retained history target");
            ThemeSource candidate = edited("#FF405060"); WorkspaceIO.Commit commit = io.save(candidate, prior, "new");
            require(!commit.historySaved, "history move failure was reported as success");
            require(accent(io.readDraft()).equals("#FF405060"), "history failure rolled back source");
            require(Arrays.equals(export(candidate), export(commit.source)), "failure result omitted committed snapshot");
            require(prior.toString().equals(priorBytes), "failed history save changed prior events");
            require(Files.readString(marker).equals("retained history target"), "failed history move changed blocked target");
            candidate.setColor(true, "accent", "#FF708090");
            require(accent(commit.source).equals("#FF405060"), "history failure returned aliased source");
            noTemporaryFiles(directory);
        });
        test("oversized history does not roll back saved source or replace previous history", () -> {
            Path directory = workspace(); WorkspaceIO io = new WorkspaceIO(directory.toFile());
            io.save(source(), new JSONArray(), "old"); JSONArray prior = io.readHistory();
            byte[] oldHistory = Files.readAllBytes(directory.resolve("history.json"));
            WorkspaceIO.Commit commit = io.save(edited("#FF405060"), prior, "x".repeat(64 * 1024));
            require(!commit.historySaved, "oversized history was accepted");
            require(accent(io.readDraft()).equals("#FF405060"), "history size failure rolled back source");
            require(Arrays.equals(oldHistory, Files.readAllBytes(directory.resolve("history.json"))), "history size failure replaced previous history");
            noTemporaryFiles(directory);
        });
        test("history retains the newest fifty events in order", () -> {
            Path directory = workspace(); WorkspaceIO io = new WorkspaceIO(directory.toFile()); JSONArray prior = history(100);
            WorkspaceIO.Commit commit = io.save(source(), prior, "latest");
            require(commit.historySaved, "bounded history did not save");
            require(commit.history.length() == 50 && io.readHistory().length() == 50, "history is not bounded to fifty");
            for (int i = 0; i < 49; i++) require(commit.history.getJSONObject(i).getString("description").equals("event-" + (i + 51)), "retained history order changed");
            require(commit.history.getJSONObject(49).getString("description").equals("latest"), "new event not retained");
            require(prior.length() == 100, "history trimming changed prior array");
            noTemporaryFiles(directory);
        });
        test("history under storage limit is saved", () -> {
            Path directory = workspace(); WorkspaceIO io = new WorkspaceIO(directory.toFile());
            WorkspaceIO.Commit commit = io.save(source(), new JSONArray(), "x".repeat(63 * 1024));
            require(commit.historySaved && io.readHistory().length() == 1, "history below byte limit was rejected");
            require(Files.size(directory.resolve("history.json")) <= 64 * 1024, "saved history exceeds byte bound");
            noTemporaryFiles(directory);
        });
        test("missing history returns an empty array", () -> {
            require(new WorkspaceIO(workspace().toFile()).readHistory().length() == 0, "missing history is not empty");
        });
        test("malformed history returns an empty array without rewriting it", () -> {
            Path directory = workspace(); Path path = directory.resolve("history.json"); byte[] invalid = "invalid JSON".getBytes(StandardCharsets.UTF_8); Files.write(path, invalid);
            require(new WorkspaceIO(directory.toFile()).readHistory().length() == 0, "malformed history was accepted");
            require(Arrays.equals(invalid, Files.readAllBytes(path)), "read rewrote malformed history");
        });
        test("history beyond read bound returns an empty array", () -> {
            Path directory = workspace(); Path path = directory.resolve("history.json");
            Files.writeString(path, new JSONArray().put("x".repeat(64 * 1024)).toString());
            require(Files.size(path) > 64 * 1024, "fixture does not exceed read limit");
            require(new WorkspaceIO(directory.toFile()).readHistory().length() == 0, "oversized history was read");
        });
        test("second successful save replaces complete source and appends history", () -> {
            Path directory = workspace(); WorkspaceIO first = new WorkspaceIO(directory.toFile());
            first.save(source(), new JSONArray(), "first");
            WorkspaceIO second = new WorkspaceIO(directory.toFile()); ThemeSource next = edited("#FF405060");
            second.save(next, second.readHistory(), "second");
            require(Arrays.equals(export(next), Files.readAllBytes(directory.resolve("draft.ouitheme"))), "replacement differs from complete exported source");
            require(first.readHistory().length() == 2, "second history event missing");
            require(accent(first.readDraft()).equals("#FF405060"), "other workspace instance reads stale source");
            noTemporaryFiles(directory);
        });
        test("missing draft reports an input failure", () -> {
            expectIOException(() -> new WorkspaceIO(workspace().toFile()).readDraft());
        });
        test("malformed draft fails without rewriting stored bytes", () -> {
            Path directory = workspace(); Path path = directory.resolve("draft.ouitheme"); byte[] bytes = {4, 5, 6}; Files.write(path, bytes);
            expectIOException(() -> new WorkspaceIO(directory.toFile()).readDraft());
            require(Arrays.equals(bytes, Files.readAllBytes(path)), "failed read changed stored source");
        });
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("Usage: WorkspaceIOTests OUTPUT REPO");
        output = Path.of(args[0]); Files.createDirectories(output);
        baseline = Path.of(args[1], "docs/design/theme-source/bundles/amoled-black.ouitheme");
        checks();
        JSONObject report = new JSONObject().put("passed", passed).put("failed", failures.size()).put("checks", results);
        Files.writeString(output.resolve("workspace-results.json"), report.toString(2) + "\n");
        System.out.println("WorkspaceIO checks: " + passed + " passed, " + failures.size() + " failed");
        if (!failures.isEmpty()) throw new AssertionError("WorkspaceIO checks failed: " + failures);
    }
}
