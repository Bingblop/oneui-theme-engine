# Draft One UI Studio theme source

These are design examples, not installable overlays or certified One UI 9 themes. The `.ouitheme` ZIP is imported by the proposed Studio application. Theme Park import of this format is not established.

Each example directory contains a manifest, dark semantic tokens, and the exact repository MIT license. Neon Violet also illustrates optional geometry tokens and per-app keyboard overrides. To form the proposed source container, include these relative entries:

```text
manifest.json
tokens/dark.json
LICENSE.txt
```

`LICENSE.txt` is the repository's MIT license, copied without changing its copyright notice. Preserve it when packaging the examples. Include any declared `overrides/dark.json` file too. Three deterministic draft source archives are available in `bundles/`, with `SHA256SUMS`; these are reviewable appearance sources for the proposed format, not overlay APKs or packages accepted by Samsung's theme engine. No overlay APKs have been built.

Validate manifests against `manifest.schema.json`, global tokens against `tokens.schema.json`, and per-app overrides against `overrides.schema.json`. Register the token schema's `urn:oneui-studio:tokens:1` identity to resolve override references locally. JSON Schema checks structure; the proposed importer additionally checks file existence, override/variant agreement, required API versions and style-pack dependencies, unique component and asset declarations, archive paths, asset type/extension agreement and limits, font references, and application eligibility. Schema acceptance alone is not proof of compatibility.

The contract declares 25 `#AARRGGBB` color roles including alpha, 5 bounded dimension roles in `dp`/`sp`, and 2 optional font-asset roles. `onAccent` is foreground content on an accent surface; `textPrimary` and `textSecondary` are foreground content on background/surface. `quickTileInactive` describes the desired inactive-tile surface. The token API is `oneui-studio.tokens/1`; it is deliberately independent of Android resource names. Font references must resolve to declared licensed TTF/OTF assets. Version 1 has no token aliases or embedded commands. The token representation is custom and does not claim DTCG compliance.

Optional `appearance.dark`/`appearance.light` settings bind semantic icon slots such as `quickPanel.wifi` to declared PNG/WebP assets, and define component shapes, fills, strokes, and radius roles. Matching appearance/override variants must exist in `variants`. Compatibility packs publish supported icon slots and shape mappings; the importer rejects unresolved required bindings. Arbitrary resource identifiers do not enter these declarations.

The standard component/override keys cover the first Samsung collection. Namespaced `extension:org.example/app.palette` keys permit additional targets when a matching pack defines them. They do not establish support for an arbitrary installed app. Unknown required extensions fail resolution; optional extensions are reported as omitted.

Versioned preview defaults are in `defaults/dark.json` and `defaults/light.json`. Precedence is defaults → style-pack defaults → global variant tokens → per-app variant overrides. Appearance component settings override their corresponding style-pack component settings. Missing font references preserve the original typeface. Before compilation, the editor exports the resolved chosen values explicitly; unresolved preview-only defaults never silently become device changes. A target mapping is always required even for an explicitly chosen value.

Requested components are intentions, not available features. Every seed component is optional. An application review must show omissions; it may not silently call a partial application a complete theme. Unknown builds allow preview/export and independently checked public APIs only, not system-overlay installation.

The palette ideas come from the repository's existing AMOLED Black, Neon Violet, and Cyberpunk Gold profiles. Foreground roles are added to make editable designs readable; the old Android/Samsung resource mappings have been discarded.

`initial-device.json` records fields observed in the user's screenshot and explicit unknowns. It is research metadata, not a production compatibility pack or signed catalog. No device operation is certified by these files.

See the [application design](../../superpowers/specs/2026-10-07-oneui9-studio-design.md) for compatibility packs, guided application, distribution, and feasibility gates.

The [Hex-style customization contract](../hex-customization-contract.md) covers typography, icons, styles, geometry, variants, per-app overrides, compiler outputs, and the user-owned bridge boundary. Those are source intentions until current target resources and bridge support are measured.
