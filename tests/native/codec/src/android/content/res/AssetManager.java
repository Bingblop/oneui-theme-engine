package android.content.res;

import java.io.*;
import java.nio.file.*;

/** Host-only filesystem-backed test stub; it is not an Android AssetManager. */
public class AssetManager {
    private final Path root;
    public AssetManager(Path root) { this.root = root; }
    public InputStream open(String name) throws IOException { return Files.newInputStream(root.resolve(name)); }
}
