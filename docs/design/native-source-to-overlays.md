# Native source export to fresh overlays

The desktop compiler now accepts a Studio `.ouitheme` archive directly through `--source`, as well as the existing source-directory format. It snapshots and validates the archive before generating output. Both variants, per-app overrides and declared assets remain in the compiled bundle's source; compilation uses only explicit mapped values.

## Use an exported source

Edit a palette in [One UI Studio](../../apps/oneui-studio/README.md), export it through Android's document picker, and transfer that file to the computer with the verified firmware inputs and local Android tools. No manual archive extraction is needed.

From the repository root:

```bash
python3 tools/build_oneui9_theme.py \
  --source /path/to/YourTheme.ouitheme \
  --pack compatibility/oneui9/sm-s948u1/S948U1UEU4BZID/resource-pack.json \
  --inputs ../oneui9-inputs \
  --output ../your-theme-build \
  --aapt2 /path/to/aapt2 \
  --zipalign /path/to/zipalign
```

The output directory must be new. This produces compiled/aligned unsigned overlays and a source/project/report ZIP. For developer signing, add `--apksigner /path/to/apksigner --keystore /path/to/your-key.jks --key-alias YOUR_ALIAS`; the development password defaults to `android` and can be overridden with `--store-pass`. These signatures do not confer Samsung theme authority.

Archive ingestion uses Python's standard library. Keep `tools/build_oneui9_theme.py` and `tools/oneui9_source_archive.py` together if copying the compiler out of the repository. The original first-theme-pack download is an immutable earlier snapshot whose bundled compiler accepts directories; use the current repository or the integration download below for direct archive support.

## Validation and output

Limits match the native source container: 20 MiB compressed, 80 MiB expanded, 500 entries and 1 MiB per JSON/license file. The importer rejects ambiguous local/central ZIP records, traversal, symlinks, executable or undeclared entries, encryption, unsupported link metadata, CRC/size disagreement and bounded-decompression failures. It checks strict JSON, native source constraints and bounded image/font container metadata, then uses the compiler's existing schemas. This host inspection does not establish Android image decoding or rendering.

The compiler removes its private extraction directory after success or failure. Invalid archive/schema, firmware or resource evidence fails before output creation. Directory-source behavior stays backward compatible. No preview values are inserted into exported or compiled data.

`build-report.json` adds `sourceArchiveSha256` for archive input. `sourceSha256` remains the digest of the validated source-file hashes. Each target report records the exact replacement values, token origin, omissions and final APK digest. Final APKs are under `targets/framework/`, `targets/systemui/` and `targets/settings/`; a developer-signed build names them `overlay-signed.apk`.

The current pack emits 174 colors and seven optional dialog/button dimensions. Fonts/icons/styles and unbound controls are preserved and reported as unsupported rather than claimed as compiled. Read [current coverage and state constraints](oneui9-first-theme-pack.md) before integrating with the apply bridge.

## Verified integration example

- [Download edited native source, three signed overlays, projects, reports and current tools](../../artifacts/oneui9/native-export-0.3.0/oneui9-native-export-example.zip)
- [Native source export example](../../generated/oneui9/native-export-0.3.0/NativeExportExample.java)
- [Integration evidence](../../generated/oneui9/native-export-0.3.0/integration-report.json)
- [Archive tests](../../tests/test_oneui9_source_archive.py)

The exact production `ThemeSource.java` from Studio 0.3.0 ran with the documented host stubs and exported a modified Neon Violet source. It retains both variants, SystemUI/Settings overrides and distinct 20dp dark / 16dp light corner dimensions. The desktop compiler accepted that archive and built all three overlays against the supplied current Samsung APKs. Compilation, emitted-value readback, alignment and developer-signature verification passed.

This is a host-generated native-codec export, not an Android UI execution result. Its source ID/version remains `org.bingblop.neon-violet` / `0.2.0`, so the example uses the same overlay package identities as the baseline Neon theme. The bridge must treat it as a replacement example, not a separate installed palette. Device activation, Samsung policy and visual results are unverified.

To regenerate the example after running the portable codec harness, with its external output/classes and pinned JSON dependency available:

```bash
mkdir -p "$THEME_CODEC_OUTPUT/example-classes"
"$STUDIO_JDK/bin/javac" \
  -cp "$THEME_CODEC_OUTPUT/classes:$JSON_JAVA_JAR" \
  -d "$THEME_CODEC_OUTPUT/example-classes" \
  generated/oneui9/native-export-0.3.0/NativeExportExample.java
"$STUDIO_JDK/bin/java" \
  -cp "$THEME_CODEC_OUTPUT/example-classes:$THEME_CODEC_OUTPUT/classes:$JSON_JAVA_JAR" \
  NativeExportExample apps/oneui-studio/assets \
  "$THEME_CODEC_OUTPUT/neon-violet-edited-native.ouitheme"
```

Then pass that output file to the compiler command above. The example does not simulate document-picker or Android lifecycle behavior.

To include a real native export in the optional importer check:

```bash
ONEUI9_NATIVE_EXPORT=/path/to/YourTheme.ouitheme \
  python3 -m unittest discover -s tests -v
```

Without that environment variable, portable archive/CLI/attack tests still run and only the optional external-export check is skipped. The [asset-sync guide](studio-asset-sync.md) documents how to keep the editor's bundled sources aligned with the measured source directories.
