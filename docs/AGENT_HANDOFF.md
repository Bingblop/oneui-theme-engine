# One UI Studio agent handoff

## Repository and publication

- Repository: `Bingblop/oneui-theme-engine`; branch: `design/oneui9-studio`.
- Draft PR: https://github.com/Bingblop/oneui-theme-engine/pull/2
- Published design: `9d27c35`; measured overlays/compiler: `e19b1d8`; native scaffold: `b86d786`; secure codec/durable saves: `32a85e2`.
- The native APK and portable checks are published in the next checkpoint after `32a85e2`; inspect `git log` for its exact commit.
- The user authorizes ongoing implementation, commits and pushes. Publish small checkpoints and update this document before stopping. The user specifically wants another agent to continue if this session runs low on resources.
- GitHub pushes work. Commit with `git -c user.name=Bingblop -c user.email=61481058+Bingblop@users.noreply.github.com commit ...`; GitHub blocks the earlier private email. Never print credentials or commit signing keys.

## Confirmed target and inputs

SM-S948U1; One UI 9.0; Android 17/API 37; build `CP2A.260605.016.S948U1UEU4BZID`; fingerprint `samsung/m3quew/m3q:17/CP2A.260605.016/S948U1UEU4BZID_OYM4BZID:user/release-keys`; security patch `2026-09-05`.

Read-only collector inputs: https://drive.google.com/drive/folders/1jjMuBDvXSsO-7lH8RH2CX4OoxBNt9uU6. The supplied framework/SystemUI/Settings APKs were retrieved and their complete hashes verified. Originals are not committed. The initial report is partial because informational overlay help exited255 and long package dumps lost version fields; APK manifests establish version37/name17. Collector regressions are fixed and tested. Do not require recollection solely for those recovered version fields.

## Completed theme/compiler work

- Design/specification, screen concepts, customization and bridge contract: `docs/design/` and `docs/superpowers/specs/2026-10-07-oneui9-studio-design.md`.
- Fresh measured resource pack: `compatibility/oneui9/sm-s948u1/S948U1UEU4BZID/resource-pack.json`.
- AMOLED Black, Neon Violet and Cyberpunk Gold: `themes/oneui9/`, with explicit dark/light variants.
- Desktop compiler: `tools/build_oneui9_theme.py`. APK hash/resource-identity/collector guards, explicit tokens and per-app overrides, original-alpha multiplication, readback/sign/align checks, deterministic ZIP export, no overwrite/device/network operations.
- Generated projects/reports: `generated/oneui9/S948U1UEU4BZID/`.
- Download: `artifacts/oneui9/S948U1UEU4BZID/oneui9-first-theme-pack.zip`; nine final developer-signed overlays, source/projects/reports/tools. SHA-256: `577e3aabd2ed18ac71eb9b5fe75a6490b506858b6f3b73688fbafe4e2e0df12f`.
- **33 desktop tests passed** before the native APK checkpoint. All nine actual overlay APKs passed compilation, value readback, signing and alignment. ZIP integrity and exactly nine final signed APKs were checked.

Coverage: 174 colors plus seven optional dialog/button dimensions, 250 configured bindings. Neon explicitly requests the geometry; the other sources omit it. Shared framework primary/on-primary and SystemUI active/dim tile bindings are withheld to preserve contrast across coupled consumers. Do not reintroduce them simply to increase counts. Full Hex parity is not achieved.

## Completed native prototype

`apps/oneui-studio/`, package `org.bingblop.oneui.studio`, version0.3.0, min/target/compileAPI37. Native Java platform widgets; no WebView, AndroidX or network dependency. Manifest grants no internet/root/broad-storage permissions. No install/enable/bridge operations exist in the editor.

Implemented: three bundled source palettes, 25 ARGB color roles, global/eight per-app scopes, separate dark/light variants, five bounded dimensions, conceptual quick-panel/Settings/keyboard previews, strict SAF import/export, durable private draft/history and read-only device inspection/report export. Accepted imported fonts/icons/styles/assets are preserved; their native editors/renderers remain unfinished. Current source overrides for unmeasured apps are exported honestly rather than claimed to affect the phone.

`ThemeSource.java` validates strict JSON and schemas, bounded ZIP envelope/central-local records/CRC/paths/modes, declared assets and image/font structure. Limits:20MiB compressed,80MiB expanded,500entries,1MiB perJSON. Deterministic canonical exports; mutations validate before changing state; accessors are defensive. Copying shares only private immutable asset bytes and deep-copies editable JSON. Missing requested variants fail explicitly.

`WorkspaceIO.java` writes a candidate snapshot to a same-directory temporary file, synchronizes it and atomically replaces the draft. Failed source commits preserve the prior draft. History is secondary: its failure is reported without pretending the committed source rolled back. History limits50events/64KiB. The static process-wide Activity worker serializes saves and reads across rotation; UI source changes only after a successful durable commit. SAF results wait for startup, exports snapshot/prepare before opening the destination, and queued saves survive Activity destruction. This is host-tested behavior; actual Android lifecycle execution remains unverified.

`DeviceInventory.java` compares public build/fingerprint/API and hashes three base target APKs. Unknown splits and unreadable APKs prevent a match. The UI labels cached reports with inspection time and separates resource match from unverified application/policy.

## Native artifact and verification

Download: `artifacts/oneui-studio/0.3.0/oneui-studio-0.3.0.zip`. It contains the APK, app source/assets/resources, offline builder, portable checks, build evidence and tool provenance. Original Samsung APKs, SDK/JDK binaries, JSON dependency, fixture fonts and signing keys are excluded.

- APK:70309bytes; SHA-256 `8e3aca67b31dff96ee7027c2e048b16f8437b84cd500a8e1fe314200016046b1`.
- App source matches production checkpoint `32a85e2`; per-file hashes: `generated/oneui-studio/0.3.0/build-report.json`.
- SDK37 compilation, manifest/package/API metadata, dex/assets, uncompressed/four-byte-aligned `resources.arsc`, ZIP alignment and developer signature passed.
- Official R8/D8 **9.5.23** produces no API37 warning. The older D8 bundled in Build Tools37 warns that37 is unsupported and is rejected; do not switch back to it.
- OpenJDK21.0.12.1 with Android37 and `core-lambda-stubs.jar` bootstrap libraries; Java source/bytecode8. Desktop-only Java APIs are rejected. Sources/tool hashes and changed/new inputs are guarded.
- **156 codec +18 storage host checks passed**, with exact tested source hashes and results in the generated evidence directory. Use `tests/native/codec/README.md` for pinned JSON-java20240303 and a licensed local TTF. Host compilation requires Java17+. Host image stubs do not verify Android/WebP decoding.
- **12 real-tool builder checks passed**:11 required plus optional old-D8 warning rejection. Use `tests/native/app-builder/README.md`. Signed-byte repeatability requires the same RSA key and tools.
- **No phone or emulator installation/execution has occurred.** Do not claim UI/lifecycle/rendering verification, Samsung policy acceptance or theme activation. The APK is developer-signed and its key is not published.

The app README includes a concrete manual smoke test and portable offline build command. The initial native candidates with compressed resource tables were superseded; only the final APK above is publishable.

## Work in progress after this checkpoint

A subsequent checkpoint is connecting a native exported `.ouitheme` directly to the desktop compiler, preserving directory-source compatibility, rejecting hostile archives before output, and recording the archive digest. Another independent task makes the three bundled sources/resource pack reproducibly checkable so native assets cannot silently drift from measured sources. Inspect current files and later handoff updates before repeating either task.

## Local workspace aids

These paths are session-specific, not dependencies hardcoded into tools:

- Repository: `/workspace/oneui-theme-engine`; verified input directory: `/workspace/oneui9-inputs`.
- Detailed resource analysis: `/workspace/oneui9-analysis/{framework,systemui,settings}`.
- Overlay builds: `/workspace/oneui9-final/{amoled-black,neon-violet,cyberpunk-gold}`.
- Final native build: `/workspace/oneui9-studio-final`.
- Toolchain/provenance: `/workspace/toolchains/android-theme/provenance.json`; official SDK under `sdk/`, R8/D8 under `r8/9.5.23/`, JDK under `jdk-debian/usr/lib/jvm/java-21-openjdk-amd64/`.
- Development key: `/workspace/oneui9-signing/studio-dev.jks`, alias`oneui9dev`, development password`android`; uncommitted. Generate a new key on another machine; a different key changes APK signatures and cannot update this published editor in place.

Overlay build provenance remains beside the measured resource pack. New native provenance is separate under `generated/oneui-studio/0.3.0/`, preserving the published overlay evidence/artifact hashes.

## Next priorities and boundaries

1. Run the app's manual smoke test on the actual Android17 phone; capture crashes, lifecycle/import/export behavior, screenshots and the exported device report. Fix observed runtime bugs before claiming support.
2. Complete exported-source compiler integration and bundled-asset drift checks if not already published by a later checkpoint. Run focused tests and a real three-target build; update this handoff and push.
3. Add native font/icon/component-style editors and source metadata/library management. Preserve unknown/unmapped declarations. Validate assets and license inputs before adding them; no silent fallback into compiled values.
4. Obtain current Phone, Keyboard, Contacts, Messages, My Files and Launcher APKs using the read-only command in `docs/design/oneui9-first-theme-pack.md`. Their resource bindings cannot be invented from old Hex names.
5. Author fresh font/icon/drawable/Lottie and state-aware geometry mappings, then verify consumers, contrast, light/dark states and rollback on the phone.
6. User owns the apply bridge. Agree a concrete bridge protocol and verify installation, activation, active resource lookup and visual results separately. No observed overlayable group: do not invent `targetName`, Samsung authority, root bypasses or fake applied-theme settings.

Existing legacy engine/HexNext/HexBridge claims are not support evidence for this build. Do not invoke their stale resource maps or installation scripts from new Studio. Keep PR#2 draft until runtime/bridge coverage is established. The original published overlay ZIP and native0.3.0 download should remain immutable; publish further versions separately when source changes.

## Resume procedure

Fetch/check out `design/oneui9-studio`, inspect PR#2 and newest handoff/git log, run `python3 -m unittest discover -s tests -v`, then consult portable native-check READMEs. Work from the newest completed source/artifact checkpoint rather than restarting. Commit/push each meaningful completed step and update evidence, artifact hashes, PR description and this handoff before stopping.
