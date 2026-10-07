#!/usr/bin/env python3
"""Check or atomically refresh the four known native Studio assets, offline."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import os
import re
import stat
import sys
import tempfile
import zipfile
import zlib

try:
    from . import build_oneui9_theme as compiler
    from . import oneui9_source_archive as native_source
except ImportError:
    import build_oneui9_theme as compiler
    import oneui9_source_archive as native_source


THEMES = ("amoled-black", "neon-violet", "cyberpunk-gold")
REPO = Path(__file__).resolve().parents[1]
MEASURED_PACK = REPO / "compatibility/oneui9/sm-s948u1/S948U1UEU4BZID/resource-pack.json"


class SyncError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise SyncError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def bounded_bytes(path, limit, label):
    require(path.stat().st_size <= limit, f"{label} exceeds byte limit {limit}: {path}")
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    require(len(data) <= limit, f"{label} grew beyond byte limit {limit}: {path}")
    return data


def checked_path(value, label, *, directory=False, missing=False):
    path = Path(value).expanduser()
    require(".." not in path.parts, f"Escaping {label} path: {path}")
    path = path.absolute()
    current = Path(path.anchor)
    parts = path.parts[1:]
    for index, part in enumerate(parts):
        current /= part
        require(not current.is_symlink(), f"Symlink in {label} path: {current}")
        if index < len(parts) - 1 and current.exists():
            require(current.is_dir(), f"Non-directory parent in {label} path: {current}")
    if path.exists():
        require(path.is_dir() if directory else path.is_file(), f"{label} has incorrect file type: {path}")
    else:
        require(missing, f"Missing {label}: {path}")
    return path.resolve()


def theme_archive(source, level):
    for path in source.rglob("*"):
        require(not path.is_symlink(), f"Symlink in source: {path}")
    validated = compiler.read_source(source)
    files = validated[3]
    require(0 < len(files) <= native_source.MAX_ENTRIES, "Source has too many declared files")
    sizes = {name: path.stat().st_size for name, path in files.items()}
    require(sum(sizes.values()) <= native_source.MAX_EXPANDED_BYTES, "Source exceeds expanded byte limit")
    payloads, expanded = {}, 0
    for name, path in files.items():
        limit = native_source.MAX_JSON_BYTES if name.endswith(".json") or name == "LICENSE.txt" else native_source.MAX_EXPANDED_BYTES
        limit = min(limit, native_source.MAX_EXPANDED_BYTES - expanded)
        payloads[name] = bounded_bytes(checked_path(path, "declared source file"), limit, "Source file")
        expanded += len(payloads[name])
    native_source.validate_source_payloads(payloads, validated)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=level) as archive:
        for name, data in sorted(payloads.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=level)
    data = buffer.getvalue()
    require(len(data) <= native_source.MAX_COMPRESSED_BYTES, "Theme archive exceeds compressed byte limit")
    return data


def archive_diff(actual, expected):
    """Describe bounded payload drift, without trusting destination ZIP paths."""
    try:
        with zipfile.ZipFile(io.BytesIO(actual)) as old, zipfile.ZipFile(io.BytesIO(expected)) as new:
            old_names, new_names = old.namelist(), new.namelist()
            if len(old_names) != len(set(old_names)):
                return {"archiveError": "duplicate entries"}
            if any(info.file_size > 16 * 1024 * 1024 for info in old.infolist()) or sum(info.file_size for info in old.infolist()) > 64 * 1024 * 1024:
                return {"archiveError": "destination archive exceeds comparison limits"}
            common = set(old_names) & set(new_names)
            changed = sorted(name for name in common if old.read(name) != new.read(name))
            return {"addedEntries": sorted(set(new_names) - set(old_names)), "removedEntries": sorted(set(old_names) - set(new_names)), "changedEntries": changed, "payloadsEqual": set(old_names) == set(new_names) and not changed, "archiveMetadataOrCompressionDiffers": set(old_names) == set(new_names) and not changed}
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
        return {"archiveError": str(exc)}


def expected_outputs(themes, pack, level):
    expected = {}
    for name in THEMES:
        source = checked_path(themes / name, "theme source", directory=True)
        expected["sources/" + name + ".ouitheme"] = theme_archive(source, level)
    metadata = compiler.read_json(pack)
    require(isinstance(metadata, dict) and metadata.get("format") == compiler.PACK_FORMAT and metadata.get("sourceTokenApi") == compiler.TOKEN_API and type(metadata.get("androidApiLevel")) is int and metadata["androidApiLevel"] == 37 and isinstance(metadata.get("buildFingerprint"), str) and metadata["buildFingerprint"], "Unsupported measured resource pack metadata")
    targets = metadata.get("targets")
    require(isinstance(targets, list) and 1 <= len(targets) <= 3, "Measured pack requires one to three target records")
    seen = set()
    for target in targets:
        require(isinstance(target, dict), "Measured pack target must be an object")
        key = target.get("key")
        require(isinstance(key, str) and key in compiler.TARGETS and key not in seen, "Incorrect or duplicate measured pack target")
        seen.add(key)
        require(target.get("package") == compiler.TARGETS[key], f"Incorrect measured package for {key}")
        require(isinstance(target.get("apkSha256"), str) and re.fullmatch(r"[0-9a-fA-F]{64}", target["apkSha256"]), f"Invalid measured APK SHA-256 for {key}")
        require(isinstance(target.get("bindings"), list), f"Invalid measured bindings for {key}")
    require("framework" in seen, "Measured pack requires framework target evidence")
    expected["resource-pack.json"] = bounded_bytes(pack, 4 * 1024 * 1024, "Measured pack")
    require(compiler.read_json(pack) == metadata, "Resource pack changed while checking")
    return expected


def synchronize(themes, pack, assets, *, write=False, compression_level=6):
    require(compression_level in (6, 9), "Compression level must be 6 or 9")
    themes = checked_path(themes, "themes", directory=True)
    pack = checked_path(pack, "measured pack")
    assets = checked_path(assets, "assets", directory=True, missing=True)
    require(not assets.is_relative_to(themes) and not themes.is_relative_to(assets), "Assets and theme source folders must not overlap")
    known = ["resource-pack.json"] + ["sources/" + name + ".ouitheme" for name in THEMES]
    require(all(assets / name != pack for name in known), "Asset outputs must not overwrite the input pack")
    expected = expected_outputs(themes, pack, compression_level)
    targets = {name: checked_path(assets / name, "asset output", missing=True) for name in expected}
    differences = []
    for name, data in expected.items():
        target = targets[name]
        limit = native_source.MAX_COMPRESSED_BYTES if name.endswith(".ouitheme") else 4 * 1024 * 1024
        actual = bounded_bytes(target, limit, "Existing asset") if target.exists() else None
        if actual == data:
            continue
        difference = {"path": name, "reason": "missing" if actual is None else "bytes-differ", "expectedSha256": sha256(data), "expectedBytes": len(data)}
        if actual is not None:
            difference.update({"actualSha256": sha256(actual), "actualBytes": len(actual)})
            if name.endswith(".ouitheme"):
                difference.update(archive_diff(actual, data))
        differences.append(difference)
    report = {"format": "oneui-studio.asset-sync/1", "mode": "write" if write else "check", "status": "drift" if differences else "in-sync", "compressionLevel": compression_level, "zlibVersion": zlib.ZLIB_RUNTIME_VERSION, "assets": {name: {"sha256": sha256(data), "sizeBytes": len(data)} for name, data in sorted(expected.items())}, "differences": differences, "written": []}
    if write and differences:
        assets.mkdir(parents=True, exist_ok=True)
        # Stage every replacement completely before changing any known asset.
        with tempfile.TemporaryDirectory(prefix=".studio-asset-sync-", dir=assets) as folder:
            stage = Path(folder)
            for difference in differences:
                name = difference["path"]
                staged = stage / name
                staged.parent.mkdir(parents=True, exist_ok=True)
                with staged.open("wb") as handle:
                    handle.write(expected[name])
                    handle.flush()
                    os.fsync(handle.fileno())
                staged.chmod(0o644)
            for difference in differences:
                name = difference["path"]
                # Recheck parents to reject symlinks created since validation.
                target = checked_path(assets / name, "asset output", missing=True)
                target.parent.mkdir(parents=True, exist_ok=True)
                (stage / name).replace(target)
                report["written"].append(name)
        report["status"] = "synchronized"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Compare without writing (default)")
    mode.add_argument("--write", action="store_true", help="Validate, stage, and atomically replace changed known outputs")
    parser.add_argument("--themes", default=str(REPO / "themes/oneui9"))
    parser.add_argument("--pack", default=str(MEASURED_PACK))
    parser.add_argument("--assets", default=str(REPO / "apps/oneui-studio/assets"))
    parser.add_argument("--compression-level", type=int, choices=(6, 9), default=6, help="6 reproduces the published 0.3.0 assets; 9 is an explicit format change")
    args = parser.parse_args()
    try:
        report = synchronize(args.themes, args.pack, args.assets, write=args.write, compression_level=args.compression_level)
    except (SyncError, compiler.BuildError, OSError, ValueError) as exc:
        print(f"Asset sync failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["status"] == "drift" else 0


if __name__ == "__main__":
    sys.exit(main())
