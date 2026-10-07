# One UI Studio

A native, offline theme-source editor for One UI 9 / Android 17. Version **0.3.0** is a prototype targeting API 37. Its first measured firmware is **SM-S948U1, CP2A.260605.016.S948U1UEU4BZID**.

- [Download the APK, source, build reports and checks](../../artifacts/oneui-studio/0.3.0/oneui-studio-0.3.0.zip)
- [Build evidence](../../generated/oneui-studio/0.3.0/)
- [Fresh framework, SystemUI and Settings overlay pack](../../docs/design/oneui9-first-theme-pack.md)
- [Continuation handoff](../../docs/AGENT_HANDOFF.md)

## Implemented behavior

Library opens three bundled dark/light palettes or imports a `.ouitheme` through Android's document picker. Studio edits 25 ARGB color roles globally or in eight per-app scopes, and five bounded dimensions. Quick-panel, Settings and keyboard concept previews respond to colors; tile/key corners and body size respond to their dimension values. Dialog/button corners have measured overlay bindings; navigation height is currently an exported source value.

Edits and imports commit a complete source to private app storage before the UI shows the saved draft. Same-directory atomic replacement preserves the prior draft on commit failure. A process-wide worker serializes saves and reads across Activity recreation. History retains the latest 50 events. A secondary history-write failure is reported without claiming the newly saved source was rolled back.

Import validates bounded ZIP records, strict JSON, source schemas, paths, declared assets and image/font structure. Exports preserve accepted assets, appearance declarations and overrides, and are prepared before opening the destination. Device inspection uses public build fields and read-only hashes of the three target APKs. A resource match is separate from bridge or Samsung policy acceptance. The app requests no network, root or broad storage permissions.

The APK has passed real SDK 37 compilation, resource-table storage/alignment, manifest, asset/dex and developer-signature checks. **It has not been installed or run on a phone or emulator.** Fonts, icons and component-style declarations survive import/export, but their native editors and preview renderers are unfinished. Device overlay application, rollback, full Hex parity, localization and additional Samsung app bindings remain outstanding.

## First device smoke test

Use an Android 17/API 37 device. Extract `oneui-studio.apk` from the download and install it through Android's package installer or an authorized `adb install /path/to/oneui-studio.apk`. This installs only the editor. The published certificate is a development certificate; a build signed with your own key cannot update it in place.

1. Open Library, choose each palette, and confirm both variants open independently.
2. Edit global and per-app colors, including alpha; confirm the concept preview updates where that role is used. Edit geometry within the displayed bounds.
3. Rotate during a save, reopen the app, and check that the saved draft and history remain. Repeat after returning from a document picker.
4. Export a source, import it again, and compare both variants, overrides and any declared assets. A malformed source must leave the previous saved draft intact.
5. Run Device inspection on the exact supplied firmware. Record its report, any unreadable APKs or splits, and the inspection time. This result must not be interpreted as theme activation.
6. Try export cancellation and an unavailable document destination. Record errors or crashes and preserve the source for reproduction.

Capture actual runtime results before claiming these scenarios pass. The portable [codec/storage checks](../../tests/native/codec/README.md) and [real-tool builder checks](../../tests/native/app-builder/README.md) document what has been verified on the host.

## Offline build

The native app uses Android platform APIs and Java source files directly. No Gradle, Maven resolution, AndroidX, or network access is needed during a build. Its package is `org.bingblop.oneui.studio`; compile, minimum, and target SDK levels are 37. Java source and bytecode levels are 8. The Java bootclasspath contains the Android SDK stub jar and Build Tools' `core-lambda-stubs.jar`, which supplies compiler hooks for lambdas. This avoids the desktop JDK's API library.

Prepare local copies of the official Android SDK Platform **37.0 revision 2**, Android Build Tools **37.0.0**, a JDK with `java` and `javac` (the verified setup uses Debian OpenJDK **21.0.12.1**), and an existing developer signing key. AAPT2 can come from Build Tools or Google's Maven distribution; the verified setup uses **9.4.1-15978811**. Use Google's Maven **R8/D8 9.5.23**, paired with the unchanged official Build Tools `d8` wrapper and its jar at `lib/d8.jar`. Build Tools 37's bundled older D8 warns that API 37 is unsupported; the builder rejects that warning. Download and verify these tools separately. The builder does not fetch them or create a signing key.

From the repository root, supply your local paths:

```sh
python3 tools/build_oneui9_studio_app.py \
  --source apps/oneui-studio \
  --output build/oneui-studio-0.3.0 \
  --android-jar "$STUDIO_SDK/platforms/android-37/android.jar" \
  --lambda-stubs "$STUDIO_SDK/build-tools/37.0.0/core-lambda-stubs.jar" \
  --aapt2 "$STUDIO_AAPT2" \
  --javac "$STUDIO_JDK/bin/javac" \
  --java "$STUDIO_JDK/bin/java" \
  --d8 "$STUDIO_D8" \
  --zipalign "$STUDIO_SDK/build-tools/37.0.0/zipalign" \
  --apksigner "$STUDIO_SDK/build-tools/37.0.0/apksigner" \
  --tool-provenance "$STUDIO_PROVENANCE" \
  --keystore "$STUDIO_KEY" \
  --key-alias oneui9dev
```

`STUDIO_SDK`, `STUDIO_AAPT2`, `STUDIO_D8`, `STUDIO_JDK`, `STUDIO_PROVENANCE`, and `STUDIO_KEY` are local paths you set before running the command. The SDK folder name can differ from `android-37`; use the actual location of the installed `android.jar`. Keep the keystore outside the app source and output folders. The default key password is `android` for the development key; `--store-pass` can override it. Passwords and key contents are excluded from reports and APK payloads.

The optional provenance JSON uses an `installed_tools` object containing `sha256` for `android_jar`, `lambda_stubs`, `aapt2`, `javac`, `java`, `java_modules`, `d8_script`, `d8_jar`, `zipalign`, `apksigner_script`, and `apksigner_jar`. The builder checks each supplied digest before creating outputs. It also retains available official archive records (`sdk_platform`, `build_tools`, `maven_aapt2`, `maven_r8`, `jdk_packages`). Without `--tool-provenance`, actual tool and input hashes are still recorded, with external provenance marked unverified.

The output folder must be new and outside the app source. A successful build creates `oneui-studio.apk`, `build-report.json`, `signature-verification.txt`, `manifest-badging.txt`, and inspectable intermediates. The builder generates `R.java`, compiles every Java file under `src/`, converts classes with D8, packs all dex files and assets, normalizes APK ZIP ordering and timestamps, aligns the APK, signs it, and checks its signature, SDK metadata, dex contents, and embedded assets. It keeps `resources.arsc` uncompressed and checks its four-byte alignment, as modern Android installation requires. Tool failures produce a failed report without publishing the final APK. The verified RSA development key and pinned toolchain produce identical APK bytes for unchanged sources; signing algorithms such as ECDSA can use randomness. Changed or newly added input files during compilation are rejected.

Developer signing supports normal Android package installation. This build does not install the app, run it on a device, grant theme privileges, or certify Samsung overlay policy acceptance.
