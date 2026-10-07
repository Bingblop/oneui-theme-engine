# Fresh One UI 9 overlay collection

The user reports that the old Hex Installer overlays target One UI 6.1.1 and no longer work. This collection must be authored anew for **SM-S948U1 / Android 17 / One UI 9.0 / CP2A.260605.016.S948U1UEU4BZID**. The current repository's resource names are unverified inputs and must not be copied into a production One UI 9 compatibility pack.

The supplied framework, SystemUI and Settings APKs and report have now been inspected. The [first measured pack](oneui9-first-theme-pack.md) contains nine compiled developer-signed APKs with current resource bindings. There are currently **zero device-verified new overlays**. The user develops the apply bridge; compilation and actual application compatibility are tracked separately.

## Collection boundaries

Start with the Samsung targets already represented by the repository's HexNext concept. Package names below are discovery candidates and must be confirmed on the phone. “All new” means every shipped binding has current resource and policy provenance; it does not mean every installed app can be overlaid.

| New component | Candidate target | Desired coverage | Current status |
| --- | --- | --- | --- |
| Framework palette | `android` | Accessible background, foreground, accent and dynamic palette roles | Resources/policy not inventoried |
| SystemUI | `com.android.systemui` | Quick panel, tiles, notification surfaces, supported status/navigation styling | Resources/policy not inventoried |
| Settings | `com.android.settings` | Supported page/card backgrounds, labels and accents | Resources/policy not inventoried |
| Samsung Phone | `com.samsung.android.dialer` | Supported dialer colors and surfaces | Package/resources/policy not inventoried |
| Samsung Keyboard | `com.samsung.android.honeyboard` | Supported keyboard/key surfaces and accents | Package/resources/policy not inventoried |
| My Files | `com.sec.android.app.myfiles` | Supported file-manager surfaces and accents | Package/resources/policy not inventoried |
| Samsung Messages | `com.samsung.android.messaging` | Supported messaging surfaces and accents, if installed | Package/resources/policy not inventoried |
| Samsung Contacts | `com.samsung.android.app.contacts` | Supported contacts surfaces and accents | Package/resources/policy not inventoried |

Third-party Hex coverage is a separate inventory: enumerate requested apps, obtain their current APK identities/resources, and establish whether they permit overlays. An absent Samsung Messages package is an omitted component; Google Messages is a different target and must not inherit its mappings. Fonts, layout alterations, drawables, and application code changes require additional eligibility; a color overlay cannot recreate arbitrary app behavior.

## Two separate compatibility reports per component

1. **Resource proof:** identify the current target package/version and resource-bearing splits; extract the actual resource table, type, qualifiers, overlayable group, and policy. Trace the resource's use in the intended visible surface. Resources drawn in code, Compose, or images may not have a replaceable color entry.
2. **Application proof:** through the user's bridge, demonstrate that the phone accepts the generated artifacts, displays their intended effect, and permits restoration. This proof is independent of source compilation. Package installation, matching names, or an overlay listing alone do not pass it.

Current AOSP rejects shell fabrication, both in the shell command and the service. Shizuku running as shell is not a substitute for root or Samsung's signing authority. A freshly compiled RRO still must satisfy resource-overlay policy. A renamed package or modified theme-state string is not an application proof.

## New source authoring workflow

1. Use the [collector](collect-oneui9-inputs.md) to record the device identity and obtain readable current APKs. Begin with framework/SystemUI/Settings; collect each Samsung application when its slice begins.
2. Use a pinned Android SDK `aapt2` to inventory resources and configurations. Use `apksigner` for certificate identity; record SHA-256 for all resource-bearing APKs/splits. Parse actual overlayable declarations and any backend-specific Samsung metadata available legitimately.
3. Compare a small before/after sample created through Samsung's normal Theme Park UI. Establish what its current backend changes. Theme Park's ability to create its own themes is not evidence that Studio can import arbitrary packages or call a private API.
4. Author fresh bindings from semantic roles to measured target resources or a demonstrated Samsung source contract. Each binding records package identity, resource name/type/qualifiers, overlayable group/policy, transformation, expected result, and evidence. An unavailable role stays unavailable; do not search for a similarly named resource and guess.
5. For an eligible RRO route, create a new manifest with the measured target package and actual overlayable `targetName` where required; generate new resource XML and qualifier directories; link using the current target resource inputs and pinned Android SDK tools. Signing and installation must follow the accepted policy. A generic developer key does not satisfy a Samsung-signature requirement.
6. Test a single benign color first, then expand by target. Distinguish generated, compiled, policy-approved, enabled, readback-confirmed, visually confirmed, persistent, and restorable states.
7. Publish only matching certified compatibility packs. Theme sources remain independent of these firmware bindings, so an update replaces the adapter without forcing creators to redesign their palette.

There is no fabricated sample `res/values/colors.xml` in this design, because actual replacement names and permissions are unknown. Such a file would falsely imply a usable overlay source. The first new resource XML is produced from the collected current target inputs.

## Acceptance and failure handling

For each target, test day/night variants, relevant display qualifiers, another Samsung theme, app restart where needed, Shizuku shutdown, reboot, app update, and OTA invalidation. Capture restoration before considering the component releasable. A first screenshot of the Settings version page confirms firmware, not any of these outcomes.

If the unrooted firmware rejects a bridge's application route, mark application blocked and retain the valid source/build report. Do not conflate a denied application method with failure to author resources. The app may provide Samsung setup instructions as a fallback, but that does not establish that generated overlay artifacts work through the user's bridge.

See the [full application design](../superpowers/specs/2026-10-07-oneui9-studio-design.md) and [draft appearance-source format](theme-source/README.md).
