# Collect current One UI 9 design inputs

Run [collect_oneui9_inputs.py](../../tools/collect_oneui9_inputs.py) on a laptop with Python 3.9 or later and Android Platform Tools installed. The confirmed reference phone is an SM-S948U1 running One UI 9, Android 17, build `CP2A.260605.016.S948U1UEU4BZID`. Collection records the actual phone's values and warns when its model, Android release, or display build differs.

A new native Hex successor needs fresh target resources and overlay policy evidence from this Android 17 build. Old One UI 6.1.1 resource maps and compiled Hex overlays cannot establish current resource names, types, overlayable groups, or permitted actors. This collector supplies inputs for that work; it does not generate or certify new overlays.

## Prepare the phone yourself

Install Android Platform Tools on the laptop, enable the phone's debugging option, connect it, and authorize the laptop through Android's normal prompt. For wireless debugging, complete pairing and connection yourself first. Check `adb devices` and make sure your intended phone is listed in the `device` state.

The collector never authorizes or pairs a phone, starts Shizuku or device services, invokes root or `su`, installs APKs, changes settings, fabricates overlays, or enables/disables overlays. Normal ADB client behavior may start the laptop's local ADB server; that does not authorize a phone. Shizuku can be relevant to a future apply bridge, but is not needed for this laptop collector.

## Minimal diagnostics

From the repository root:

```bash
python3 tools/collect_oneui9_inputs.py --output oneui9-diagnostics
```

Without `--serial`, exactly one authorized device must be visible. With several authorized devices, choose one explicitly:

```bash
python3 tools/collect_oneui9_inputs.py --serial YOUR_ADB_SERIAL --output oneui9-diagnostics-phone
```

The default is read-only diagnostics: ADB device selection, shell `id`, nine specific `getprop` values, `cmd overlay help`, `cmd overlay list`, and package paths/version fields for `android`, `com.android.systemui`, and `com.android.settings`. It does not take full property, environment, process, or application-data dumps. Package dump output is reduced to `versionCode`, `versionName`, `minSdk`, and `targetSdk` before it enters the report. Missing properties and unsupported/denied commands are reported.

Use `--include-overlay-dump` only when the initial overlay help/list output leaves a policy question that `dumpsys overlay` can help investigate. This additional command is read-only and can still be unavailable. It does not replace examining overlayable declarations in current APK resources.

## Copy the fresh target APKs

APK copying is optional because diagnostics alone cannot provide resource tables. To collect the base targets and the Samsung apps in the design scope:

```bash
python3 tools/collect_oneui9_inputs.py \
  --output oneui9-target-apks \
  --pull-apks \
  --packages android com.android.systemui com.android.settings \
    com.samsung.android.dialer com.samsung.android.honeyboard \
    com.sec.android.app.myfiles com.samsung.android.messaging \
    com.samsung.android.app.contacts
```

`--packages` replaces the default list, so include the three base targets when collecting the full suite. Package names are candidates, not a claim that the build installs every app. Each name is checked with `pm path`; only paths returned by that query and accepted by the collector are copied. Split APKs are retained individually. Allowed locations are Android partition `app`, `priv-app`, `framework`, and `overlay` directories; `/data/app` APKs; and APEX `app`, `priv-app`, and `framework` directories. Traversal, unexpected characters, non-APK paths, and private app-data locations are rejected. Denied reads remain evidence gaps; the tool never retries with elevated access.

For exact optional launcher and Theme Park version detection, explicitly include these candidates in `--packages`:

```text
com.sec.android.app.launcher
com.samsung.android.themedesigner
com.samsung.android.themepark
```

The Theme Park candidates are checked separately; neither is assumed to be the current package name. An installed app's version fields and `pm path` result provide build-specific evidence. Leave off `--pull-apks` when only version detection is needed. A screenshot can document the stock launcher, Theme Park, and app baselines, but a baseline screenshot does not prove a theme matches the intended design.

## Output and next design work

Every run requires a new output folder and writes `report.json`. With `--pull-apks`, successful copies appear under `apks/<candidate-package>/`, each with size and SHA-256 in the report. Partial/failed copies are removed. There is no automatic archive. Reports record command argument lists, exit codes, stdout, stderr, timeouts, warnings, and errors; individual command text is bounded at 256 KiB. Package stdout contains only the selected version fields. Device serial/build identifiers appear in the report, so review it before sharing.

Exit code `0` means collection completed without recorded errors, with warnings still possible. `1` means the report contains errors or incomplete collection. `2` means command-line/output setup or report writing failed. A missing candidate package is a warning; it never becomes a supported target. Existing output paths are refused without issuing any ADB command. Use `--timeout SECONDS` for a different per-command timeout and `--adb /path/to/adb` for a specific Platform Tools executable. Run `--help` for CLI options.

The next step is to inspect each current APK's compiled resource table and overlayable declarations with an Android resource inspection tool, then create a new mapping from theme tokens to the verified names and types. Check each target's signature/actor policy and later test acceptance on this exact build through the separately designed apply bridge. A readable APK, available `cmd overlay` command, or successful collection is not certification of overlay installation, activation, full Hex customization coverage, or visual fidelity.
