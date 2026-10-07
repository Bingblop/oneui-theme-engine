# First measured One UI 9 theme pack

This pack is authored from the APKs collected on **SM-S948U1, One UI 9.0, Android 17 / API 37, CP2A.260605.016.S948U1UEU4BZID**. It replaces legacy resource assumptions with measured names, types, IDs, configuration values and APK hashes.

The first release contains **AMOLED Black, Neon Violet and Cyberpunk Gold**, each with explicit dark and light source tokens and three freshly compiled, aligned, developer-signed overlay APKs. All nine APKs passed compiled-value readback and signature verification. **Device application, Samsung policy acceptance and visual behavior remain untested.** A separate [native Studio 0.3.0 prototype](../../apps/oneui-studio/README.md) now provides source editing and import/export; its phone execution is also unverified.

## Files

- [Download the complete first pack](../../artifacts/oneui9/S948U1UEU4BZID/oneui9-first-theme-pack.zip)
- [Measured resource pack](../../compatibility/oneui9/sm-s948u1/S948U1UEU4BZID/resource-pack.json)
- [AMOLED Black source](../../themes/oneui9/amoled-black/manifest.json), [Neon Violet source](../../themes/oneui9/neon-violet/manifest.json), [Cyberpunk Gold source](../../themes/oneui9/cyberpunk-gold/manifest.json)
- [Compiler](../../tools/build_oneui9_theme.py) and [compiler tests](../../tests/test_oneui9_theme_builder.py)
- [Generated projects and build reports](../../generated/oneui9/S948U1UEU4BZID/)
- [Artifact hashes](../../artifacts/oneui9/S948U1UEU4BZID/SHA256SUMS)

The download contains source tokens, resource maps, generated Android resource projects, nine signed APKs, per-target reports, signatures, the compiler and collector. The original Samsung firmware APKs remain collection inputs, and signing keys are not included.

## Current coverage

| Target | Color resources | Optional dimension resources | Configured resource bindings |
| --- | ---: | ---: | ---: |
| Framework (`android`) | 96 | 2 | 102 |
| SystemUI | 51 | 2 | 105 |
| Settings | 27 | 3 | 43 |
| Total | 174 | 7 | 250 |

Color coverage includes framework text/backgrounds, selected controls, the Samsung quick-panel background and inactive tile colors, notification surfaces/text, Settings preference surfaces, text, icons and controls, and the navigation-bar background. Neon Violet explicitly requests a 24dp corner radius, mapped to seven observed dialog/button dimensions. AMOLED Black and Cyberpunk Gold leave those dimensions unchanged.

Each APK targets one package. Dark/light configurations are compiled together. Existing resources with named dark/light variants keep their observed qualifier; shared resources use separate default and night bindings. Author-added night configurations are explicitly marked in the pack. Source color alpha is multiplied by the original per-configuration alpha, preserving the measured translucency factor rather than replacing every color with an opaque value. Existing selector XML and animation payloads are retained.

These are static, reviewed bindings. They do not establish which rendering branch runs on the phone. A shared foreground can affect multiple consumers; the following coupled resources are withheld until a state/style-aware mapping can preserve all consumers:

- Framework `system_primary_dark` and `system_on_primary_dark`: the latter also supplies on-accent text to a light DeviceDefault theme.
- SystemUI `qs_tile_round_background_on` and `qs_tile_icon_on_dim_tint_color`: the icon resource also supplies dimmed states and notification app-primary colors. Changing it alone creates poor contrast in a stock dimmed light tile.
- Status/navigation glyph pipelines, panel and tile geometry, global font replacement, drawable/icon replacement and Lottie animation edits.

The source format retains those customization controls for further authoring, but the compiler reports unbound controls and unsupported appearance/assets explicitly. This first collection does **not** achieve full Hex customization parity.

Settings routing was checked against actual attribute IDs: `Theme.Settings.Home` sets `colorBackground` through `settingslib_materialColorSurfaceContainerLow`; its inherited window background uses framework `tw_screen_background_dark/light`. `sec_widget_round_and_bgcolor` serves system bars and particular layout backgrounds. `preference_background` is a simple color drawable referencing `materialColorSurfaceContainer`. The round-button foreground is mapped to `onAccent`, and `sesl_control_normal_color_light` receives a night binding because both theme parents reference that leaf despite its suffix.

## Rebuild from the repository

Use Python 3.9 or newer, Java, AAPT2, ZIP alignment and APK signer. The tested toolchain used Google Maven AAPT2 `9.4.1-15978811` and Android SDK Build Tools `37.0.0` for `zipalign` and `apksigner`. Select the supplied tools through the flags if they are not on `PATH`.

From the repository root, with the collected `oneui9-inputs` directory alongside the repository:

```bash
python3 tools/build_oneui9_theme.py \
  --source themes/oneui9/amoled-black \
  --pack compatibility/oneui9/sm-s948u1/S948U1UEU4BZID/resource-pack.json \
  --inputs ../oneui9-inputs \
  --output ../oneui9-build-amoled
```

This creates aligned, unsigned APKs and source/report archives. The output directory must be new. Add `--aapt2 /path/to/aapt2 --zipalign /path/to/zipalign` when needed. For developer signing, additionally supply `--apksigner /path/to/apksigner --keystore /path/to/your-key.jks --key-alias YOUR_ALIAS --store-pass YOUR_PASSWORD`. The supplied test artifacts use a development certificate, whose public certificate digest is recorded in the signature reports.

The compiler performs no network or device operations. It verifies complete APK hashes and every mapped resource identity before output generation. When `report.json` is present, it checks the collected fingerprint, API level, APK paths, hashes and sizes; a partial collector status caused by informational overlay help does not invalidate matching APK evidence. It checks emitted values again after compilation and signing. A failed build produces no successful bundle. It imports only explicit source values and per-app overrides; preview defaults are not silently compiled.

```bash
python3 -m unittest discover -s tests -v
```

The tests cover path escapes, changed APKs, metadata mismatch, wrong/missing resource IDs, malformed colors/dimensions, per-app precedence, alpha multiplication, default/night separation, failures, repeatability and archive contents. Collector tests cover version fields appearing after large dumps and the observed complete-help/exit-255 behavior while preserving actual error and timeout reporting.

## Handoff to the apply bridge

The bundle places final artifacts at `compiled/<theme>/targets/<target>/overlay-signed.apk`. Each target's build report records its overlay package, target package, target hash, source and resource-pack digests, exact replacements and omissions. `applied`, `policyVerified` and `compatibilityCertification` are false.

No overlayable group name was observed in the supplied resource tables, so manifests omit `targetName`; a group is never invented. Developer signing is separate from Samsung authorization. The bridge can consume the generated projects if it needs different packaging or signing, and must establish accepted installation/application, active resource lookup and visual results on this exact firmware before marking a theme compatible. Resource geometry, state transitions, blur, light/dark transitions and rollback need device verification.

## Inputs for the rest of the collection

The supplied folder contains the three base targets. Phone, Keyboard, Contacts, Messages, My Files and Launcher still require their current resource-bearing APKs before their fresh bindings can be authored. Collect into a new directory:

```bash
python3 tools/collect_oneui9_inputs.py --pull-apks --output oneui9-full-inputs \
  --packages android com.android.systemui com.android.settings \
    com.samsung.android.dialer com.samsung.android.honeyboard \
    com.samsung.android.app.contacts com.samsung.android.messaging \
    com.sec.android.app.myfiles com.sec.android.app.launcher
```

Missing package candidates are recorded as warnings. The collector remains read-only. There is no need to repeat the original collection merely to recover its truncated package version fields: the supplied APK manifests already establish API and package version 37 / 17.
