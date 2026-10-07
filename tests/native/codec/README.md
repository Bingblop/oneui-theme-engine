# ThemeSource host codec tests

This harness compiles the repository's exact `ThemeSource.java` with real JSON-java and small Android host stubs. It runs 156 checks covering source preservation, canonical deterministic exports, copy/accessor isolation, both variants, typed edits, failed-edit atomicity, strict JSON/schema validation, declared asset references, image/font metadata, and hostile ZIP records. All selected ZIP policies are required checks, including rejected Unix link metadata, trailing bytes, and unknown directory records.

Use Bash, Python 3.10 or newer, and Java 17 or newer with a compiler. Host compilation uses Java 17 source and target levels. If `javac` is unavailable but the runtime includes `jdk.compiler`, the runner invokes `java com.sun.tools.javac.Main`.

JSON-java is pinned to version **20240303**, downloaded from:

```
https://repo.maven.apache.org/maven2/org/json/json/20240303/json-20240303.jar
SHA-256: 3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed
```

Download that jar into an external dependency directory, then select a licensed local TTF that may be used in temporary test fixtures. The font and jar are not copied into the repository. For example:

```bash
curl -fLsS https://repo.maven.apache.org/maven2/org/json/json/20240303/json-20240303.jar \
  -o "$JSON_JAVA_JAR"
bash tests/native/codec/run.sh \
  --json-jar "$JSON_JAVA_JAR" \
  --font "$THEME_CODEC_FONT" \
  --font-license "$THEME_CODEC_FONT_LICENSE" \
  --output "$THEME_CODEC_OUTPUT"
```

The caller supplies those paths and the font's license label. `JSON_JAVA_JAR`, `THEME_CODEC_FONT`, `THEME_CODEC_FONT_LICENSE`, and `THEME_CODEC_OUTPUT` also work without their corresponding CLI flags. An omitted output path creates a temporary directory and prints its location. The runner rejects output paths inside the repository and verifies the jar hash before compiling.

`--repo`, `--source`, `--workspace-source`, `--java`, `--javac`, and `--python` override inferred paths or tools; see `run.sh --help`. `THEME_SOURCE_JAVA` and `THEME_WORKSPACE_JAVA` provide the corresponding production-source overrides. Codec results are written to `results.json`; `source.sha256` records both exact tested production sources after verifying that neither changed during the run. Generated fixtures, fonts, classes, and downloaded dependencies belong in the external output/dependency directories.

The runner also compiles the exact production `WorkspaceIO.java` and invokes `WorkspaceIOTests` after `CodecTests`, with the same positional arguments: external output directory, then repository root. Its 18 checks cover preserving the old draft when saving fails before commit, failed atomic replacement and temporary-file cleanup, independent saved-source copies, source persistence when history recording fails, and the history limits of 50 events and 64 KiB. Durability outcomes are written to `workspace-results.json`, separately from the 156 codec checks. Failure cases use unavailable-workspace simulation and nonempty directory targets so they work without assumptions about permissions or the host user. The successful save checks require a host filesystem that supports atomic replacement; they do not simulate power loss.

`AssetManager` is a filesystem-backed host stub. `BitmapFactory` uses ImageIO for PNG/JPEG bounds and MIME types. These checks do not establish Android image decoding or WebP support, Android packaging/UI behavior, or bridge application. The generators need only Python's standard library; the supplied TTF is used only in generated parser fixtures.
