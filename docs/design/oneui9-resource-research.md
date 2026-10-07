# Preserved One UI 9 resource research

[Download the detailed research snapshot](../../artifacts/oneui9/S948U1UEU4BZID/oneui9-resource-research.zip) and [verify its SHA-256](../../artifacts/oneui9/S948U1UEU4BZID/RESEARCH_SHA256SUMS).

The snapshot preserves 1,081 analysis files used while authoring the first fresh pack for **SM-S948U1, CP2A.260605.016.S948U1UEU4BZID, Android17/API37**. The 28,691,341-byte ZIP contains resource/manifest/configuration dumps, selected decoded XML, resource indexes, static DEX-reference scans, candidate mappings and authoring notes/scripts. `inventory.json` records every file's size and SHA-256. It contains no original APK, DEX binary, SDK/JDK, signing key or device personal files.

Extract it to a new directory. Target folders are `analysis/framework`, `analysis/systemui` and `analysis/settings`; their reports explain the measured resource identities and selected consumer references. The complete tables and indexes help locate new fonts, drawables, component styles and state relationships without repeating the original inspection. Input APK identities and dump/tool provenance accompany the evidence.

Candidate maps are exploratory; the reviewed production map remains [resource-pack.json](../../compatibility/oneui9/sm-s948u1/S948U1UEU4BZID/resource-pack.json). Do not automatically promote candidates into bindings. An XML reference or aligned DEX constant does not prove live control flow, rendering, overlay policy acceptance or the correctness of every state. Some exploratory scripts retain session-specific paths; adapt them before reuse. The portable supported compiler and its tests live separately in `tools/` and `tests/`.

The current pack withholds shared framework primary/on-primary and SystemUI active/dim tile colors because changing one consumer breaks contrast in another. Use the preserved evidence to design state-aware replacements and then verify them on the phone. The snapshot does not add coverage or compatibility claims beyond the [first measured theme pack](oneui9-first-theme-pack.md).

Original firmware APKs remain available through the user's Drive input link in [the continuation handoff](../AGENT_HANDOFF.md). Additional Samsung app targets still need fresh collection before their resource bindings can be authored.
