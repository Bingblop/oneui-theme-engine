# One UI Studio agent handoff

## Repository and publication

- Repository: `Bingblop/oneui-theme-engine`; branch: `design/oneui9-studio`.
- Draft PR: https://github.com/Bingblop/oneui-theme-engine/pull/2
- Published design: `9d27c35`; measured overlays/compiler: `e19b1d8`; native scaffold: `b86d786`; secure codec/durable saves: `32a85e2`.
- Published native APK/checks: `dc649a7`; detailed firmware resource research: `048b689`. Source-to-overlay integration and asset sync are in the following checkpoint; inspect `git log` for its exact commit.
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
- Preserved research: `artifacts/oneui9/S948U1UEU4BZID/oneui9-resource-research.zip`, 1,081 files / 28,691,341 bytes, SHA-256 `4577b046e3251c2903064ee24a1ec2fe54b49e0bec64d6016975b634c91e461a`. Resource/manifest/configuration dumps, selected XML, indexes, static DEX references and exploratory candidate scripts are included with a per-file inventory. Candidate maps are not production bindings; exploratory scripts retain some original workspace paths. See `docs/design/oneui9-resource-research.md`.

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

## Completed source-to-overlay integration and asset sync

`tools/build_oneui9_theme.py --source /path/to/export.ouitheme` now accepts native archives directly. Directory input remains compatible. Adjacent `tools/oneui9_source_archive.py` snapshots bounded bytes, validates exact ZIP records/CRC/paths/modes and native constraints, uses existing source schemas, enforces declared-file inventory and removes its private extraction after success/failure. `sourceArchiveSha256` supplements the existing file-inventory digest. No outputs are created before archive/schema/firmware/resource preflight. The shared pure-memory `validate_source_payloads` checks captured data without filesystem access. Numeric bounds, precise decimals, schema-snapshot mismatch and external-CWD imports were reviewed and corrected.

`tools/sync_oneui9_studio_assets.py --check` is read-only and reproduces all four published asset hashes exactly. Default DEFLATE6, fixed metadata and raw source bytes reproduce0.3.0; explicit9 is a separate byte-format change. `--write` validates all three inputs and pack before staging/replacing only changed known outputs. Reads are bounded, input-pack collisions/symlinks/escaping paths are rejected, unrelated files remain, and each replacement is atomic; all four files are not one filesystem transaction. **Published themes/app assets were not rewritten.** Guide: `docs/design/studio-asset-sync.md`.

The exact production native codec ran with host stubs and exported edited Neon Violet: both variants, SystemUI/Settings overrides,20dp dark/16dp light corners. Source archive SHA-256 `3613d3665a7602419a890d47c6e3c9cede79b665809743f32c1e93a51ccf0419`. All three real target overlays then compiled and passed value readback, signing and alignment against the supplied firmware APKs. This is a host native-codec integration, **not an Android UI execution**. Original source ID/version and baseline Neon overlay identities are retained, so this is a replacement example.

- Integration source/projects/reports: `generated/oneui9/native-export-0.3.0/`.
- Download: `artifacts/oneui9/native-export-0.3.0/oneui9-native-export-example.zip`; edited native export, exactly three final signed overlays, evidence and latest tools. Adjacent SHA-256 file.
- Workflow/reproduction commands: `docs/design/native-source-to-overlays.md`.
- Latest host suite: **80 tests passed, no skips**, including33 original compiler/collector tests,30 archive tests and17 asset-sync tests. The optional external-native-export case was enabled.
- The integration download was extracted into a fresh external folder and its included suite also passed all80 tests, checking that the packaged tools, source assets and test dependencies are complete. The download does not bundle SDK/JDK, JSON-java or a test font; those are required only for the opt-in native checks.
- Independent review: no remaining Critical/Important findings;65 native schema fixtures matched expected acceptance, and the native fixture corpus was cross-checked. Review fixed malformed-decimal error handling, native/desktop constraints, sibling imports, pack input overwrite and target preflight before publication.
- Native0.3.0 artifact and first overlay-pack ZIP remain immutable. Latest compiler/helper/sync tools are in the new integration download and current repository; older download snapshots do not include direct archive support.

## Local workspace aids

These paths are session-specific, not dependencies hardcoded into tools:

- Repository: `/workspace/oneui-theme-engine`; verified input directory: `/workspace/oneui9-inputs`.
- Detailed resource analysis: `/workspace/oneui9-analysis/{framework,systemui,settings}`.
- Overlay builds: `/workspace/oneui9-final/{amoled-black,neon-violet,cyberpunk-gold}`.
- Final native build: `/workspace/oneui9-studio-final`.
- Final native-export integration: `/workspace/oneui9-native-interop/overlay-build-final`; source export and example Java are in its parent folder.
- Toolchain/provenance: `/workspace/toolchains/android-theme/provenance.json`; official SDK under `sdk/`, R8/D8 under `r8/9.5.23/`, JDK under `jdk-debian/usr/lib/jvm/java-21-openjdk-amd64/`.
- Development key: `/workspace/oneui9-signing/studio-dev.jks`, alias`oneui9dev`, development password`android`; uncommitted. Generate a new key on another machine; a different key changes APK signatures and cannot update this published editor in place.

Overlay build provenance remains beside the measured resource pack. New native provenance is separate under `generated/oneui-studio/0.3.0/`, preserving the published overlay evidence/artifact hashes.

## Next priorities and boundaries

1. Run the app's manual smoke test on the actual Android17 phone; capture crashes, lifecycle/import/export behavior, screenshots and the exported device report. Fix observed runtime bugs before claiming support.
2. Run the current host suite with the committed native export and check asset drift:

   ```bash
   ONEUI9_NATIVE_EXPORT=generated/oneui9/native-export-0.3.0/neon-violet-edited-native.ouitheme \
     python3 -m unittest discover -s tests -v
   python3 tools/sync_oneui9_studio_assets.py --check
   ```

   Exported-source compilation and sync are already complete; use their guides and reports instead of rebuilding those features. New app source changes require a new APK version/artifact and focused host/build checks.
3. Add native font/icon/component-style editors and source metadata/library management. Preserve unknown/unmapped declarations. Validate assets and license inputs before adding them; no silent fallback into compiled values.
4. Obtain current Phone, Keyboard, Contacts, Messages, My Files and Launcher APKs using the read-only command in `docs/design/oneui9-first-theme-pack.md`. Their resource bindings cannot be invented from old Hex names.
5. Author fresh font/icon/drawable/Lottie and state-aware geometry mappings, then verify consumers, contrast, light/dark states and rollback on the phone.
6. User owns the apply bridge. Agree a concrete bridge protocol and verify installation, activation, active resource lookup and visual results separately. No observed overlayable group: do not invent `targetName`, Samsung authority, root bypasses or fake applied-theme settings.

Existing legacy engine/HexNext/HexBridge claims are not support evidence for this build. Do not invoke their stale resource maps or installation scripts from new Studio. Keep PR#2 draft until runtime/bridge coverage is established. The original published overlay ZIP and native0.3.0 download should remain immutable; publish further versions separately when source changes.

## Resume procedure

Fetch/check out `design/oneui9-studio`, inspect PR#2 and newest handoff/git log, run `python3 -m unittest discover -s tests -v`, then consult portable native-check READMEs. Work from the newest completed source/artifact checkpoint rather than restarting. Commit/push each meaningful completed step and update evidence, artifact hashes, PR description and this handoff before stopping.
