package org.bingblop.oneui.studio;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import org.json.JSONArray;
import org.json.JSONObject;

/** Durable source storage; publish a new UI source only after commit returns. */
public final class WorkspaceIO {
    private static final Object LOCK = new Object();
    private final File directory;

    public WorkspaceIO(File directory) { this.directory = directory; }

    public static final class Commit {
        public final ThemeSource source;
        public final JSONArray history;
        public final boolean historySaved;
        private Commit(ThemeSource source, JSONArray history, boolean historySaved) {
            this.source = source; this.history = history; this.historySaved = historySaved;
        }
    }

    public ThemeSource readDraft() throws IOException {
        synchronized (LOCK) {
            try (FileInputStream input = new FileInputStream(new File(directory, "draft.ouitheme"))) {
                return ThemeSource.read(input);
            }
        }
    }

    public JSONArray readHistory() {
        synchronized (LOCK) {
            try (FileInputStream input = new FileInputStream(new File(directory, "history.json"))) {
                byte[] data = input.readNBytes(64 * 1024 + 1);
                if (data.length > 64 * 1024) return new JSONArray();
                return new JSONArray(new String(data, StandardCharsets.UTF_8));
            } catch (Exception ignored) { return new JSONArray(); }
        }
    }

    public Commit save(ThemeSource candidate, JSONArray prior, String description) throws IOException {
        synchronized (LOCK) {
            ThemeSource snapshot = candidate.copy();
            if (!directory.isDirectory()) throw new IOException("Workspace directory is unavailable");
            File pending = File.createTempFile("source-", ".tmp", directory);
            try {
                try (FileOutputStream output = new FileOutputStream(pending)) {
                    snapshot.exportTo(output);
                    output.getFD().sync();
                }
                // Fail rather than overwrite non-atomically on unsupported filesystems.
                Files.move(pending.toPath(), new File(directory, "draft.ouitheme").toPath(),
                        StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
            } finally { pending.delete(); }
            JSONArray next;
            try {
                next = new JSONArray(prior.toString());
                JSONObject event = new JSONObject();
                event.put("description", description); event.put("time", System.currentTimeMillis());
                next.put(event);
                while (next.length() > 50) next.remove(0);
                byte[] bytes = next.toString().getBytes(StandardCharsets.UTF_8);
                if (bytes.length > 64 * 1024) throw new IOException("History exceeds storage limit");
                File journal = File.createTempFile("history-", ".tmp", directory);
                try {
                    try (FileOutputStream output = new FileOutputStream(journal)) {
                        output.write(bytes); output.getFD().sync();
                    }
                    Files.move(journal.toPath(), new File(directory, "history.json").toPath(),
                            StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
                } finally { journal.delete(); }
            } catch (Exception error) {
                // The source is already durably committed; do not pretend a
                // secondary history failure rolled back that successful save.
                return new Commit(snapshot, prior, false);
            }
            return new Commit(snapshot, next, true);
        }
    }
}
