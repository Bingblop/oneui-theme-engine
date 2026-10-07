# Hex-style customization and bridge contract

The user wants a fresh One UI 9 theme with the customization breadth of old Hex Installer and will work out the apply bridge. The theme/compiler boundary therefore needs to remain usable independently of that bridge.

This is a proposed customization contract, not a claim that every historic Hex control has an equivalent on One UI 9. The repository includes a limited HexNext prototype, not the original Hex implementation or a complete inventory of its plugins. Historic 100+ app coverage cannot be inferred from that prototype. Current target resources determine which controls can be compiled, and the bridge determines which artifacts can be applied.

## Customization breadth

| Area | Theme-source controls | Required target evidence |
| --- | --- | --- |
| Core colors | Background, surface, accent, on-accent, primary/secondary text, outline, links, errors | Actual color resources and configurations for each target |
| Quick panel | Active/inactive tile surfaces and icons, panel background, tile radius | Current SystemUI resources, drawables and supported geometry |
| Notifications | Background and foreground roles | Resource-driven portions of SystemUI; app-drawn content may differ |
| Samsung apps | Settings, Phone, Contacts, Messages, Files and Keyboard overrides | Current package/split resources per application |
| Typography | Licensed body/headline font assets and body text size | Replaceable font/typeface/text resources or a supported bridge function |
| Icons | Licensed raster icons and an abstract icon/style pack | Actual drawable references, densities and supported launcher/app import route |
| Component style | Rounded/flat/custom declarative shapes, outlines and keyboard-key appearance | Current drawable structure and safe resource-backed changes |
| Geometry and tweaks | Corner radius, quick-tile radius, keyboard-key radius, navigation-bar height | Current dimensions and code use; unavailable if the layout is not resource driven |
| Variants | Independent light/dark tokens, saved presets, per-app overrides | Appropriate target qualifiers and backend behavior |
| Scope | Component toggles, optional/required components and partial coverage report | Valid dependency/conflict plan |

The token schema declares more than 16 color roles, alpha/transparency, optional dimensions/font references, and typed icon/shape declarations in the manifest. A sparse source uses [dark](theme-source/defaults/dark.json) or [light](theme-source/defaults/light.json) preview defaults. Precedence is defaults → style-pack defaults → global variant tokens → per-app overrides; explicit appearance settings override style-pack component settings. A missing font asset preserves the target's original typeface. Before compilation the editor materializes the chosen resolved values into an export; unaccepted preview-only defaults do not become device changes. **Generation never invents a missing target binding.** Light variants are separate files rather than automatic inversions.

`appearance.<variant>.icons` maps semantic slots such as `quickPanel.wifi` to declared licensed PNG/WebP assets. The compatibility pack lists which slots it supports. `appearance.<variant>.components` defines `quickTile`, `keyboardKey`, `card`, `dialog`, and `button` shapes using rectangle/rounded rectangle/circle choices, semantic fill/stroke roles, bounded stroke width, and radius-token roles. These definitions are generator inputs, not Android XML. Every declared asset reference must exist and match its declared kind.

Style packs replace Hex's executable plugin dependency with licensed assets and declarative generator settings. Creator presets can change colors, assets and geometry. Trusted pack-maintainer code generates resource XML; downloaded source packages cannot execute scripts or inject XML/shell expressions.

Per-app override files use abstract keys `framework`, `systemui`, `settings`, `phone`, `keyboard`, `files`, `messages`, and `contacts`, or namespaced `extension:org.example/app.palette` keys. A compatibility pack binds those keys to discovered current packages; unknown required extensions fail resolution and optional ones are reported as omitted. An override contains a subset of known semantic roles; it is merged over global variant tokens before generation. Required components with unresolved roles fail compilation; optional unsupported roles are reported, not silently reassigned.

## Compiler outputs

For each target, produce:

- New resource project: manifest, resource XML and qualifiers, generated drawables/assets where supported, and build metadata.
- An RRO APK only when that is the selected bridge input format and compilation succeeds. A Samsung-native theme source requires the bridge author's actual format contract before that exporter is implemented.
- `build-report.json`: source and pack digests, exact target APK hashes, compiler/tool versions, supported and omitted controls, and compilation results.
- A machine-readable application plan with dependencies, expected resource changes and requested restoration behavior. It is not a shell script.

Keep all stale One UI 6.1.1 resource bindings out of these outputs. Palette values can be reusable appearance choices; compiled resources are generated anew from the current measured target.

## Bridge integration boundary

The separately implemented bridge advertises a versioned `BridgeCapabilities` response with protocol version, accepted artifact formats, target identities, supported operation kinds, current authorization state, and restoration/readback capabilities. The compiler does not depend on its implementation language or whether it uses Shizuku internally.

An apply request passes a plan ID, selected components, exact artifact digests, source/pack digests, and expected target identities. Artifact transfer uses explicit read-only handles or file grants. The bridge validates these identities before mutation and returns per-component structured outcomes:

```text
not-attempted → accepted → applied → readback-confirmed
                         ↘ failed / partially-applied / recovery-needed
```

The Studio app records user-confirmed appearance separately. A build result is `generated`, `compiled`, or `failed`; it cannot become `applied` because the compiler finished. No bridge API is presumed to bypass Android/Samsung policy.

The first useful integration experiment is one benign current SystemUI or framework color, provided a real replaceable resource exists. That validates the source-to-bridge contract before expanding the collection and its controls.

See [the application specification](../superpowers/specs/2026-10-07-oneui9-studio-design.md), [fresh collection plan](oneui9-overlay-suite.md), and [source schemas/examples](theme-source/README.md).
