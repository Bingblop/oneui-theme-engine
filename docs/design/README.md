# One UI Studio design package

The requested product is a native Hex-style application and a **fresh One UI 9 overlay collection**, with colors, fonts, icons, styles, shape/spacing controls, variants, and per-app customization. The user develops the apply bridge; the theme/compiler supplies current-target resources and an explicit bridge contract.

First target: **SM-S948U1 · One UI 9.0 · Android 17 · CP2A.260605.016.S948U1UEU4BZID**.

- [Application specification](../superpowers/specs/2026-10-07-oneui9-studio-design.md)
- [Screen concepts, PNG](oneui9-studio-concept.png) and [editable SVG](oneui9-studio-concept.svg)
- [Customization and external bridge contract](hex-customization-contract.md)
- [Fresh per-target collection and authoring workflow](oneui9-overlay-suite.md)
- [Theme source schemas, defaults, and examples](theme-source/README.md)
- Draft sources: [AMOLED Black](theme-source/bundles/amoled-black.ouitheme), [Neon Violet](theme-source/bundles/neon-violet.ouitheme), [Cyberpunk Gold](theme-source/bundles/cyberpunk-gold.ouitheme)
- [Read-only APK/input collection instructions](collect-oneui9-inputs.md)
- [Native Studio prototype, APK and build instructions](../../apps/oneui-studio/README.md)
- [Agent handoff and remaining work](../AGENT_HANDOFF.md)
- [Compile a native source export directly](native-source-to-overlays.md)
- [Reproduce and check native bundled assets](studio-asset-sync.md)
- [Detailed resource/XML/DEX-reference research snapshot](oneui9-resource-research.md)

The initial source archives above are design examples. The supplied firmware APKs have now been inspected, and a [first measured theme pack](oneui9-first-theme-pack.md) provides current resource mappings, materialized dark/light sources, a desktop compiler, generated projects, reports and **nine freshly compiled developer-signed APKs**. Device application and visual certification remain unverified. Old One UI 6.1.1 bindings are excluded.

The native **One UI Studio 0.3.0** prototype is implemented and packaged. It provides local source browsing, color/per-app editing, bounded dimensions, conceptual previews, durable drafts/history, strict import/export and read-only device diagnostics. SDK 37 compilation and packaging checks passed; phone execution remains unverified. Full font/icon/style editing and the rest of the Hex customization suite remain planned work.

The three base targets and device report have been received. Further Samsung app targets can be collected from the repository root on a laptop with an authorized phone and Android Platform Tools:

```bash
python3 tools/collect_oneui9_inputs.py --pull-apks --output oneui9-inputs
```

The default collects framework, SystemUI, and Settings. The collection guide includes all eight Samsung targets for the full suite, and the measured-pack guide includes Launcher as well. Current APKs are needed for fresh app-specific bindings. Collection performs no overlay or theme changes.

Source compilation and device application remain separate stages. Correct resource names and a successful build do not prove acceptance by Samsung's overlay policy or the user's bridge.
