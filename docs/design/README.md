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

The source archives are appearance data in a proposed new format. **No current firmware resource bindings, compiled overlay APKs, or device-certified overlays have been produced.** Old One UI 6.1.1 bindings are excluded from the replacement design.

The next required inputs are the actual resource-bearing APKs and device report. From the repository root on a laptop with an authorized phone and Android Platform Tools:

```bash
python3 tools/collect_oneui9_inputs.py --pull-apks --output oneui9-inputs
```

This first pass collects framework, SystemUI, and Settings. The collection guide includes all eight Samsung targets for the full suite. Supply `report.json` and the readable APKs from the output directory so the new bindings can be authored against real current resources. Collection performs no overlay or theme changes.

Source compilation and device application remain separate stages. Correct resource names and a successful build do not prove acceptance by Samsung's overlay policy or the user's bridge.
