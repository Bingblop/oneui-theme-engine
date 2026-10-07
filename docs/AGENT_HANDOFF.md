# One UI Studio agent handoff

## Repository and publication

- Repository: `Bingblop/oneui-theme-engine`
- Working branch: `design/oneui9-studio`
- Draft PR: https://github.com/Bingblop/oneui-theme-engine/pull/2
- Published design checkpoint: `9d27c35`
- Published measured theme/compiler checkpoint: `e19b1d8`
- The user authorizes ongoing implementation, commits and pushes. Publish small checkpoints and update this document before stopping.
- GitHub pushes work after the connector installation was corrected. Use the user's public noreply identity for new commits: `git -c user.name=Bingblop -c user.email=61481058+Bingblop@users.noreply.github.com commit ...`. GitHub blocks the prior private commit email. Never print credentials or commit signing keys.

## Confirmed target

SM-S948U1; One UI 9.0; Android 17/API 37; build `CP2A.260605.016.S948U1UEU4BZID`; fingerprint `samsung/m3quew/m3q:17/CP2A.260605.016/S948U1UEU4BZID_OYM4BZID:user/release-keys`; security patch `2026-09-05`.

The user supplied a read-only collector directory through Google Drive: https://drive.google.com/drive/folders/1jjMuBDvXSsO-7lH8RH2CX4OoxBNt9uU6. Its report and framework/SystemUI/Settings APKs were retrieved and their sizes and SHA-256 hashes verified. Input APKs are not committed. The original collector report is partial because complete overlay help exited255 and long package dumps lost metadata; collection itself succeeded. The APK manifests recover version37/name17. Collector regressions are fixed and tested; don't require another base collection solely for those metadata fields.

## Completed and published

- Native Studio design/specification, screen concepts, customization and bridge contract in `docs/design/` and `docs/superpowers/specs/2026-10-07-oneui9-studio-design.md`.
- Fresh measured pack: `compatibility/oneui9/sm-s948u1/S948U1UEU4BZID/resource-pack.json`.
- Three materialized sources in `themes/oneui9/`: AMOLED Black, Neon Violet, Cyberpunk Gold, with explicit dark/light variants.
- Desktop compiler: `tools/build_oneui9_theme.py`. Hash/resource identity preflight, collector metadata guard, explicit source/per-app values, per-config alpha multiplication, compile/readback/sign/align checks, deterministic ZIP export, no device/network operations and no overwrite.
- Generated source projects and reports: `generated/oneui9/S948U1UEU4BZID/`.
- Download: `artifacts/oneui9/S948U1UEU4BZID/oneui9-first-theme-pack.zip`. Nine final developer-signed overlay APKs, source/projects/reports/tools. SHA-256 in adjacent `SHA256SUMS`.
- `python3 -m unittest discover -s tests -v`: **33 passed** at this checkpoint. All nine actual overlay APKs compiled, passed value readback, signing and alignment; final ZIP integrity and nine-final-APK inventory checked.

The pack covers174 color resources plus seven optional dialog/button dimensions,250 configured bindings. Neon explicitly emits dimensions; the other sources leave them unchanged. Coupled shared framework primary/on-primary and SystemUI active/dim tile bindings are withheld for contrast/state correctness. Do not reintroduce them just to raise coverage counts.

## Current next checkpoint: native editor prototype

The user asked to keep working and push all progress before credits run low. Continue with a new native Java Android app under `apps/oneui-studio/`, package `org.bingblop.oneui.studio`, min/targetAPI37. The intended first executable milestone is source browsing, local draft persistence, native color editing and conceptual previews, safe `.ouitheme` import/export, firmware/coverage diagnostics and source history. It must not claim automatic system application or invent the user's apply bridge.

Current file ownership while parallel work runs:

- Root: Activity/UI, Android manifest/resources/assets, app integration, checkpoints and this document.
- `repo_audit`: `apps/oneui-studio/src/org/bingblop/oneui/studio/ThemeSource.java`, bounded source codec and adversarial validation tests. Proposed API: `read(InputStream)`, `builtin(AssetManager,String)`, `copy()`, `exportTo(OutputStream)`, `getId()`, `getName()`, `getManifest()`, `hasVariant(String)`, `getTokens(boolean)`, `setColor(boolean,String,String)`, `getOverrides(boolean)`. Defensive JSON access; absent requested variant is an error. Original spec import limits20MiB compressed/80MiB expanded/500 entries/1MiB perJSON; no traversal, symlinks, executable data, undeclared assets or duplicate paths.
- `platform_research`: `tools/build_oneui9_studio_app.py` and app README build section. Install official platformAPI37/JDK/D8 outside repo and implement a reproducible offlinejavac/AAPT2/D8/zipalign/apksigner builder. Explicit local tool paths, no committed workspace-specific defaults.

Native source scaffold now exists: `MainActivity.java` implements the four native screens, 25 color controls, per-app color scope, five typed dimensions, conceptual quick-panel/Settings/keyboard previews, SAF import/export, local atomic draft/history storage and a read-only device-report export. `DeviceInventory.java` compares fingerprint/API/base APK hashes and explicitly leaves application/policy unverified. The manifest grants no network, root or storage permissions; three current `.ouitheme` sources and the measured pack are bundled as assets.

The source codec is implemented and SDK37 compilation succeeded;156 host checks passed for strict schemas/JSON, hostile ZIP metadata, size limits, asset structure, canonical export and copy/mutation isolation. `ThemeSource.copy()` deep-copies editable JSON while sharing only private immutable asset bytes, avoiding full image/font revalidation during each edit. A portable copy of the host harness is being prepared; its Android image/font/runtime limits must remain explicit.

Review fixes now add `WorkspaceIO.java` and a process-wide serialized Activity worker. New edits/imports are persisted before publishing the new UI source; same-directory atomic replacement preserves prior drafts on write failure. Secondary history failure is reported without pretending it rolled back a saved source. Startup restoration and SAF results are coordinated; exports snapshot and prepare content before opening/truncating the destination. Rotation does not cancel queued durable saves. Conceptual tile/key radii and body size now respond to edited dimensions; navigation height remains an export value.

The app compiled once, but that candidate is superseded by the review fixes. **No final app APK is published yet.** The builder is correcting APK resource-table compression/alignment and checking official D8 support forAPI37. Device/UI execution remains unverified. Check later handoff updates and `git log` rather than restarting completed work.

## Local workspace aids

These paths exist in the current workspace but are not portable to another agent's machine:

- Repository: `/workspace/oneui-theme-engine`
- Verified inputs: `/workspace/oneui9-inputs`
- Detailed offline APK analysis: `/workspace/oneui9-analysis/{framework,systemui,settings}`
- Final overlay builds: `/workspace/oneui9-final/{amoled-black,neon-violet,cyberpunk-gold}`
- Official resource tools: `/workspace/toolchains/android-theme/bin/{aapt2,zipalign,apksigner}`
- Development signing key: `/workspace/oneui9-signing/studio-dev.jks`, alias`oneui9dev`, public development password`android`. Key is uncommitted. A new environment should generate its own development key; do not expect byte-identical signatures across different keys.

Build tool provenance is committed alongside the resource pack. No Android device or emulator has been used for app or overlay runtime validation yet.

## Important boundaries and remaining work

- User owns the apply bridge. Keep generation, packaging, accepted installation, resource readback and visual confirmation as separate outcomes.
- No overlayable group was observed. Do not invent `targetName`, Samsung signing authority, root bypasses or a fake applied-theme setting.
- Full Hex customization parity is outstanding: Phone, Keyboard, Contacts, Messages, My Files and Launcher need current APKs. Collection command is in `docs/design/oneui9-first-theme-pack.md`.
- Fonts/icons/drawables/Lottie and state-aware geometry need fresh mappings. Unsupported source declarations are preserved/reported rather than falsely compiled.
- Existing legacy engine/HexNext/HexBridge claims are not support evidence for this build. New Studio should not invoke their stale resource maps or install scripts.
- Actual phone validation, accepted bridge protocol, rollback and on-device appearance are outstanding. Preserve these unknowns in reports/UI/PR descriptions.

## Resume procedure

1. Fetch/check out `design/oneui9-studio` and inspect PR#2 plus the newest version of this document.
2. Run existing desktop tests. Review newly added native source/build reports before redoing work.
3. Complete the in-progress native checkpoint, run focused codec and real APK build checks, and commit/push immediately.
4. Update this handoff and PR description with concrete completed behavior, commands/results, known failures and next tasks. Keep the PR draft until device/bridge coverage is established.
