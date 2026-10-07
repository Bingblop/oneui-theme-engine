# Native app builder checks

These opt-in integration checks use real local Android tools. They are excluded from normal Python unit-test discovery so the standard test suite does not require an SDK or signing key. Every project and output is created in a temporary folder and removed afterward. No SDK download, device connection, installation, or overlay application occurs.

Use Python 3.10+, a POSIX environment, the toolchain documented in [the app README](../../../apps/oneui-studio/README.md#offline-build), a matching tool-provenance JSON, and an external **RSA development key** for the signed-byte reproducibility check. From the repository root:

```sh
python3 tests/native/app-builder/run_checks.py \
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
  --key-alias oneui9dev \
  --legacy-d8 "$STUDIO_SDK/build-tools/37.0.0/d8"
```

Each required path also has an environment equivalent: `STUDIO_ANDROID_JAR`, `STUDIO_LAMBDA_STUBS`, `STUDIO_AAPT2`, `STUDIO_JAVAC`, `STUDIO_JAVA`, `STUDIO_D8`, `STUDIO_ZIPALIGN`, `STUDIO_APKSIGNER`, `STUDIO_TOOL_PROVENANCE`, and `STUDIO_KEYSTORE`. Optional variables are `STUDIO_KEY_ALIAS`, `STUDIO_STORE_PASS`, and `STUDIO_LEGACY_D8`. Explicit CLI arguments take precedence. The key password defaults to `android`; keep the key and password out of version control.

The eleven required checks cover:

1. Real compilation including a Java lambda and generated `R.java`; signature verification, uncompressed/aligned resource table, exact assets and dex, and identical RSA-signed APK bytes across two output folders.
2. Refusal to overwrite an existing output and preservation of a sentinel file.
3. Incorrect package and minimum SDK rejection before output creation.
4. Modified tool-provenance digest rejection before output creation.
5. Symlinked asset rejection before output creation.
6. Keystore inside app sources rejection before output creation.
7. Rejection of a desktop-only Java API, with a failed report and no final APK.
8. A real tool-stage failure, with a failed report and no final APK.
9. A new Java source added during compilation, with publication rejected.
10. A success-report publication failure, with final APK cleanup.
11. Explicit JDK precedence over a failing `java` executable on inherited `PATH`.

Supplying `--legacy-d8` runs a twelfth check: the older bundled D8's unsupported-API37 warning must fail the build without a final APK. Without that optional tool, this check is reported as skipped. The checks establish desktop build behavior; they do not exercise the app on Android hardware.
