# Native Studio asset synchronization

The native app bundles three measured theme sources and the resource binding pack. Their source files live in `themes/oneui9/{amoled-black,neon-violet,cyberpunk-gold}`; the pack lives in `compatibility/oneui9/sm-s948u1/S948U1UEU4BZID/resource-pack.json`. `tools/sync_oneui9_studio_assets.py` keeps these inputs and the four known app assets aligned without Android tools or network access.

From the repository root:

```sh
# Read-only comparison; --check is also the default.
python3 tools/sync_oneui9_studio_assets.py --check

# After intentional source or measured-pack changes, refresh known outputs.
python3 tools/sync_oneui9_studio_assets.py --write
```

Exit status is `0` when assets match or a requested write succeeds, `1` when a check detects drift, and `2` for validation, path, or I/O failures. JSON output lists expected hashes and byte sizes, changed output paths, and ZIP entries added, removed, or changed. If the payloads match but archive bytes differ, the report identifies a metadata or compression difference. Check mode creates no output directories and writes no files.

`--themes`, `--pack`, and `--assets` accept explicit local paths. Defaults are inferred from the script's repository location, so there are no committed workspace paths. The output directory must not overlap the theme source tree. Symlinks, escaping paths, non-directory parents, and input pack collisions with any known output are rejected. Unknown destination files are preserved.

Every source is validated using the desktop compiler's `read_source` function and the shared native archive constraints. Declared file sizes are checked before capture, actual reads are bounded, and the aggregate snapshot stays within native limits: 500 entries, 1 MiB per JSON/license, 80 MiB expanded source, and 20 MiB compressed archive. The pure-memory validator checks captured bytes against the schema-validated snapshot and applies native rules for baseline colors, uppercase color literals, exact dimension bounds, licenses, and asset container metadata. It writes no temporary validation files. The archive inventory contains exactly the declared manifest, license, token variants, overrides, and licensed assets. Source bytes are preserved; JSON is not reformatted and preview defaults are not merged. The measured pack's format, token API, Android API, fingerprint, known target identities, APK hash shape, and binding-array fields are checked, and its original bytes are copied. Missing, empty, or duplicate target records are rejected; framework evidence is required. This operation does not remeasure target APKs, certify mapping coverage, or establish Samsung overlay policy acceptance.

The explicit 0.3.0 ZIP profile is:

- Lexicographically sorted relative POSIX file paths, without directory entries.
- Timestamp `(1980, 1, 1, 0, 0, 0)` for every entry.
- Unix origin (`create_system=3`) and regular-file mode `0644` (`external_attr=0x81a40000`).
- DEFLATE **level 6**, empty extras, and empty file/archive comments.

Level 6 reproduces all published 0.3.0 asset hashes with Python 3.12.14 and zlib 1.3.2. The report records the active zlib version. Cross-version compressor differences can appear as byte drift even when payloads match.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `sources/amoled-black.ouitheme` | 2,052 | `f417e6286c443d40cddb9ce767c3eb37bfd5900e8777b28c5bc47b88b10c637f` |
| `sources/neon-violet.ouitheme` | 2,869 | `423847a4cf13b3feba08adbe59f58c3edb6fa237355eb6ee8a84cddf21e569e6` |
| `sources/cyberpunk-gold.ouitheme` | 2,053 | `3cc66bdcaf617bb9b1b1f9d3d4acedd5f52187f4fa1f597d0cff4ed1e192c977` |
| `resource-pack.json` | 217,876 | `92d9650f22b7620ec889e586fc7cb7e05e8cf45f97d7c890fe3c7f1e0c48287d` |

An explicit `--compression-level 9` uses the same file content and metadata but changes the three archive hashes. On the verified runtime, AMOLED becomes 2,050 bytes (`94c3386095b343f7276632d30c4833d6ee4035e51fef93422fb21d0d5e9f3c25`), Neon becomes 2,866 bytes (`d8018d62824045d62626cf724ca4eafef453261ea63e112ec5621a90a9d65e5c`), and Cyberpunk becomes 2,051 bytes (`bac4706160efdfac62041f24a849b182bc7f8e11571074cb18a2916f02f4cc30`). Use `--check --compression-level 9` to inspect this format change without updating published assets.

Write mode validates all inputs and stages every changed output before replacing any asset. Each replacement is atomic on the destination filesystem; the four files are not one filesystem transaction. A replacement-stage I/O failure returns nonzero, and a subsequent check identifies any remaining drift. Already matching files are not rewritten, preserving their modification times. The synchronizer does not touch Java files, app manifests, developer keys, APKs, or unrelated assets.

The stdlib tests run with the regular host suite:

```sh
python3 -m unittest discover -s tests -p test_oneui9_studio_assets.py -v
```

They use temporary inputs and outputs to cover deterministic inventories and metadata, raw pack copying, missing/drifting assets, read-only checks, unchanged-write behavior, native validation, unsafe paths, and staging failure cleanup. The production assets are checked without modification.
