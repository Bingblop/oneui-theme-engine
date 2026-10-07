#!/usr/bin/env python3
"""Deterministic standalone adversarial .ouitheme ZIP fixture generator.

Only writes below its output directory; it never changes the repository input.
The ZIP records are built directly so local and central metadata can be changed
independently. This is test data, not a production ZIP writer.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import io
import json
from pathlib import Path
import stat
import struct
import zipfile
import zlib


MIB = 1024 * 1024
COMPRESSED_LIMIT = 20 * MIB
EXPANDED_LIMIT = 80 * MIB
JSON_LIMIT = MIB
ENTRY_LIMIT = 500
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASELINE = REPO_ROOT / "docs/design/theme-source/bundles/amoled-black.ouitheme"


@dataclasses.dataclass
class Entry:
    name: str
    data: bytes
    method: int = 8
    flags: int = 0
    local_name: str | None = None
    central_name: str | None = None
    local_flags: int | None = None
    central_flags: int | None = None
    local_extra: bytes = b""
    central_extra: bytes = b""
    external_attr: int = (stat.S_IFREG | 0o644) << 16
    descriptor: str | None = None
    local_crc: int | None = None
    central_crc: int | None = None
    local_compressed_size: int | None = None
    local_uncompressed_size: int | None = None
    central_compressed_size: int | None = None
    central_uncompressed_size: int | None = None
    compressed_payload: bytes | None = None
    central_present: bool = True


def raw_deflate(data: bytes) -> bytes:
    stream = zlib.compressobj(9, zlib.DEFLATED, -15)
    return stream.compress(data) + stream.flush()


def make_zip(entries: list[Entry]) -> bytes:
    local_records: list[bytes] = []
    central_records: list[bytes] = []
    offset = 0
    for entry in entries:
        local_name = (entry.local_name or entry.name).encode("utf-8")
        central_name = (entry.central_name or entry.name).encode("utf-8")
        flags = entry.flags | (8 if entry.descriptor else 0)
        local_flags = flags if entry.local_flags is None else entry.local_flags
        central_flags = flags if entry.central_flags is None else entry.central_flags
        crc = zlib.crc32(entry.data) & 0xFFFFFFFF
        payload = entry.compressed_payload
        if payload is None:
            payload = entry.data if entry.method == 0 else raw_deflate(entry.data)
        compressed_size = len(payload)
        uncompressed_size = len(entry.data)
        default_local = (0, 0, 0) if entry.descriptor else (crc, compressed_size, uncompressed_size)
        local_crc = default_local[0] if entry.local_crc is None else entry.local_crc
        local_compressed_size = default_local[1] if entry.local_compressed_size is None else entry.local_compressed_size
        local_uncompressed_size = default_local[2] if entry.local_uncompressed_size is None else entry.local_uncompressed_size
        central_crc = crc if entry.central_crc is None else entry.central_crc
        central_compressed_size = compressed_size if entry.central_compressed_size is None else entry.central_compressed_size
        central_uncompressed_size = uncompressed_size if entry.central_uncompressed_size is None else entry.central_uncompressed_size
        # Fixed DOS timestamp 1980-01-01 00:00:00; no environment-dependent dates.
        local = struct.pack(
            "<IHHHHHIIIHH", 0x04034B50, 20, local_flags, entry.method, 0, 33,
            local_crc, local_compressed_size, local_uncompressed_size,
            len(local_name), len(entry.local_extra),
        ) + local_name + entry.local_extra + payload
        if entry.descriptor:
            descriptor = struct.pack("<III", crc, compressed_size, uncompressed_size)
            if entry.descriptor == "signed":
                descriptor = struct.pack("<I", 0x08074B50) + descriptor
            elif entry.descriptor != "unsigned":
                raise ValueError("descriptor must be signed or unsigned")
            local += descriptor
        if entry.central_present:
            central_records.append(struct.pack(
                "<IHHHHHHIIIHHHHHII", 0x02014B50, (3 << 8) | 20, 20,
                central_flags, entry.method, 0, 33, central_crc,
                central_compressed_size, central_uncompressed_size,
                len(central_name), len(entry.central_extra), 0, 0, 0,
                entry.external_attr, offset,
            ) + central_name + entry.central_extra)
        local_records.append(local)
        offset += len(local)
    central = b"".join(central_records)
    eocd = struct.pack(
        "<IHHHHIIH", 0x06054B50, 0, 0, len(central_records), len(central_records),
        len(central), offset, 0,
    )
    return b"".join(local_records) + central + eocd


def extra_field(identifier: int, body: bytes) -> bytes:
    return struct.pack("<HH", identifier, len(body)) + body


def asi_unix_extra(mode: int, link: bytes = b"") -> bytes:
    # Info-ZIP ASi Unix: CRC32, mode, size/device, uid, gid, optional link target.
    body = struct.pack("<HIHH", mode, len(link), 1000, 1000) + link
    return extra_field(0x756E, struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF) + body)


def read_baseline(path: Path) -> list[Entry]:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("baseline CRC failed")
        return [Entry(info.filename, archive.read(info.filename)) for info in archive.infolist()]


def clone(entries: list[Entry]) -> list[Entry]:
    return [dataclasses.replace(entry) for entry in entries]


def named(entries: list[Entry], name: str) -> Entry:
    return next(entry for entry in entries if entry.name == name)


def png_with_padding(padding: int) -> bytes:
    """Valid 1x1 RGBA PNG with an ignored private ancillary npAd chunk."""
    def chunk(kind: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
            + chunk(b"npAd", b" " * padding)
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\x00", 9))
            + chunk(b"IEND", b""))


def with_declared_png(entries: list[Entry], method: int = 8) -> list[Entry]:
    result = clone(entries)
    manifest_entry = named(result, "manifest.json")
    manifest = json.loads(manifest_entry.data)
    manifest["assets"] = [{"path": "assets/boundary.png", "kind": "icon", "license": "MIT"}]
    manifest_entry.data = json.dumps(manifest, separators=(",", ":")).encode("utf-8")
    result.append(Entry("assets/boundary.png", png_with_padding(0), method=method))
    return result


def padded_asset(entries: list[Entry], total_expanded: int) -> list[Entry]:
    result = with_declared_png(entries)
    asset_entry = named(result, "assets/boundary.png")
    padding = total_expanded - sum(len(entry.data) for entry in result)
    if padding < 0:
        raise ValueError("requested archive too small")
    asset_entry.data = png_with_padding(padding)
    return result


def archive_details(data: bytes) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = archive.infolist()
            return {
                "central_entries": len(info),
                "central_declared_expanded_bytes": sum(item.file_size for item in info),
                "central_declared_compressed_bytes": sum(item.compress_size for item in info),
            }
    except (zipfile.BadZipFile, ValueError):
        return {"central_entries": None}


def generate(baseline: Path, output: Path) -> None:
    baseline_bytes = baseline.read_bytes()
    base = read_baseline(baseline)
    output.mkdir(parents=True, exist_ok=True)
    fixtures: list[dict] = []

    def save(name: str, data: bytes, expected: str, reason: str, *, isolated: bool = True) -> None:
        filename = name + ".ouitheme"
        (output / filename).write_bytes(data)
        fixtures.append({
            "file": filename,
            "expected": expected,
            "reason": reason,
            "isolated": isolated,
            "archive_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            **archive_details(data),
        })

    def changed(fixture_name: str, reason: str, **changes: object) -> None:
        entries = clone(base)
        license_entry = named(entries, "LICENSE.txt")
        for key, value in changes.items():
            setattr(license_entry, key, value)
        save(fixture_name, make_zip(entries), "reject", reason)

    save("valid-baseline", baseline_bytes, "accept", "Unmodified existing theme-source example.")
    save("valid-rebuilt", make_zip(base), "accept", "Equivalent deterministic ordinary deflated ZIP.")
    for descriptor in ("signed", "unsigned"):
        entries = clone(base)
        for entry in entries:
            entry.descriptor = descriptor
        save("valid-data-descriptor-" + descriptor, make_zip(entries), "accept",
             "Deflated entries with bit 3 and valid " + descriptor + " data descriptors; signed descriptors match Java ZipOutputStream exports.")

    entries = clone(base)
    entries.append(dataclasses.replace(named(entries, "manifest.json")))
    save("duplicate-manifest", make_zip(entries), "reject", "Duplicate archive path manifest.json.")
    changed("path-traversal", "Parent traversal in both ZIP name views.", name="../LICENSE.txt")
    changed("path-backslash", "Backslash path separator in both ZIP name views.", name="..\\LICENSE.txt")
    changed("path-absolute", "Absolute slash-root path in both ZIP name views.", name="/LICENSE.txt")
    changed("path-drive-absolute", "Windows drive absolute path in both ZIP name views.", name="C:/LICENSE.txt")
    changed("path-nul", "Embedded NUL in filename.", name="LICENSE.txt\x00hidden")
    changed("local-only-traversal", "Local filename traverses while central filename is safe.", local_name="../LICENSE.txt")
    changed("central-only-traversal", "Central filename traverses while local filename is safe.", central_name="../LICENSE.txt")
    changed("local-name-mismatch", "Safe local filename disagrees with central filename.", local_name="LICENXE.txt")
    changed("central-name-mismatch", "Safe central filename disagrees with local filename.", central_name="LICENXE.txt")
    changed("encrypted-both", "Traditional encryption bit set in local and central headers.", flags=1)
    changed("encrypted-local-only", "Encryption bit set only in local header.", local_flags=1)
    changed("encrypted-central-only", "Encryption bit set only in central header.", central_flags=1)
    changed("unix-external-symlink", "Central UNIX external mode identifies a symlink.", external_attr=(stat.S_IFLNK | 0o777) << 16)
    changed("local-asi-symlink", "Local ASi Unix extra mode identifies a symlink; central mode remains regular.",
            local_extra=asi_unix_extra(stat.S_IFLNK | 0o777, b"tokens/dark.json"))
    changed("central-asi-symlink", "Central ASi Unix extra mode identifies a symlink; external mode remains regular.",
            central_extra=asi_unix_extra(stat.S_IFLNK | 0o777, b"tokens/dark.json"))
    changed("local-pkware-symlink", "PKWARE Unix local extra carries a link target after timestamps and UID/GID.",
            local_extra=extra_field(0x000D, struct.pack("<IIHH", 0, 0, 1000, 1000) + b"tokens/dark.json"))

    entries = clone(base)
    named(entries, "LICENSE.txt").local_extra = extra_field(0x5455, b"\x01" + struct.pack("<I", 0))
    save("valid-local-timestamp-extra", make_zip(entries), "accept", "Harmless well-formed extended modification timestamp.")
    entries = clone(base)
    named(entries, "LICENSE.txt").local_extra = asi_unix_extra(stat.S_IFREG | 0o644)
    save("valid-local-asi-regular-extra", make_zip(entries), "reject", "Well-formed ASi Unix regular-file metadata without link data is rejected by the selected strict extra-field whitelist.")
    entries = clone(base)
    entries.extend(Entry(directory, b"", method=0,
                         external_attr=((stat.S_IFDIR | 0o755) << 16) | 0x10)
                   for directory in ("assets/", "tokens/", "overrides/"))
    save("valid-source-directories", make_zip(entries), "accept", "Empty safe source directory records: assets/, tokens/, overrides/.")
    save("valid-declared-padded-png", make_zip(with_declared_png(base)), "accept", "Declared valid 1x1 PNG with empty private ancillary npAd chunk.")

    entries = clone(base)
    entries.append(Entry("unexpected.txt", b"undeclared text\n"))
    save("unknown-file", make_zip(entries), "reject", "Undeclared unrelated file in otherwise valid source.")
    entries = clone(base)
    entries.append(Entry("nested.zip", baseline_bytes))
    save("nested-archive", make_zip(entries), "reject", "Nested archive in theme source.")
    entries = clone(base)
    entries.append(Entry("run.sh", b"#!/bin/sh\nexit 0\n", external_attr=(stat.S_IFREG | 0o755) << 16))
    save("executable-script", make_zip(entries), "reject", "Executable script outside declarative source allowlist.")

    license_bytes = named(base, "LICENSE.txt").data
    license_crc = zlib.crc32(license_bytes) & 0xFFFFFFFF
    changed("central-uncompressed-size-mismatch", "Central expanded size differs from actual data and local size by one.",
            central_uncompressed_size=len(license_bytes) + 1)
    changed("local-uncompressed-size-mismatch", "Local expanded size differs from actual data and central size by one.",
            local_uncompressed_size=len(license_bytes) + 1)
    actual_compressed = len(raw_deflate(license_bytes))
    changed("central-compressed-size-mismatch", "Central compressed size differs from local and actual payload by one.",
            central_compressed_size=actual_compressed + 1)
    changed("local-compressed-size-mismatch", "Local compressed size differs from central and actual payload by one.",
            local_compressed_size=actual_compressed + 1)
    changed("central-crc-mismatch", "Only central CRC differs from actual bytes.", central_crc=license_crc ^ 1)
    changed("local-crc-mismatch", "Only local CRC differs from actual bytes.", local_crc=license_crc ^ 1)
    changed("both-crc-mismatch", "Both recorded CRCs agree but differ from actual bytes.",
            local_crc=license_crc ^ 1, central_crc=license_crc ^ 1)
    corrupted = bytes([license_bytes[0] ^ 1]) + license_bytes[1:]
    changed("stored-data-corruption", "Stored bytes corrupted while both recorded CRCs retain original value.",
            method=0, data=corrupted, local_crc=license_crc, central_crc=license_crc)
    changed("unsupported-compression-method", "Compression method 99 is outside stored/deflated support.", method=99)
    changed("local-entry-not-in-central", "A local LICENSE.txt record has no matching central entry.", central_present=False)

    rebuilt = make_zip(base)
    central_start = rebuilt.find(b"PK\x01\x02")
    save("missing-central-directory", rebuilt[:central_start], "reject", "Local records only: central directory and EOCD removed.")
    save("truncated-eocd", rebuilt[:-5], "reject", "End-of-central-directory record truncated by five bytes.")
    save("truncated-entry-data", rebuilt[:150], "reject", "Archive ends inside first compressed payload.")
    wrong_offset = bytearray(rebuilt)
    struct.pack_into("<I", wrong_offset, central_start + 42, 31)
    save("central-local-offset-mismatch", bytes(wrong_offset), "reject", "Central local-header offset points inside a filename instead of its header.")
    entries = clone(base)
    for entry in entries:
        entry.descriptor = "signed"
    descriptor_archive = make_zip(entries)
    descriptor_offset = descriptor_archive.find(b"PK\x07\x08")
    wrong_descriptor_crc = bytearray(descriptor_archive)
    struct.pack_into("<I", wrong_descriptor_crc, descriptor_offset + 4, license_crc ^ 1)
    save("descriptor-crc-mismatch", bytes(wrong_descriptor_crc), "reject", "Data descriptor CRC disagrees with central CRC and actual data.")
    wrong_descriptor_size = bytearray(descriptor_archive)
    struct.pack_into("<I", wrong_descriptor_size, descriptor_offset + 12, len(license_bytes) + 1)
    save("descriptor-size-mismatch", bytes(wrong_descriptor_size), "reject", "Data descriptor expanded size disagrees with central size and actual data.")
    save("trailing-junk", rebuilt + b"TRAILING-UNDECLARED-DATA\n", "reject",
         "Selected complete-container policy rejects unclaimed trailing bytes after the ZIP.")

    for size, expectation in ((JSON_LIMIT, "accept"), (JSON_LIMIT + 1, "reject")):
        entries = clone(base)
        token = named(entries, "tokens/dark.json")
        token.data += b" " * (size - len(token.data))
        save("json-" + ("at-limit" if size == JSON_LIMIT else "over-limit"), make_zip(entries), expectation,
             "Valid JSON padded with trailing whitespace to exactly " + str(size) + " expanded bytes.")
    for size, expectation in ((EXPANDED_LIMIT, "accept"), (EXPANDED_LIMIT + 1, "reject")):
        entries = padded_asset(base, size)
        save("expanded-" + ("at-limit" if size == EXPANDED_LIMIT else "over-limit"), make_zip(entries), expectation,
             "Total expanded data is exactly " + str(size) + " bytes; a declared valid 1x1 PNG carries ignored private ancillary padding.")

    # Each byte added to a stored PNG chunk adds one physical ZIP byte. Its
    # declared dimensions stay 1x1; no JSON or license-byte cap is involved.
    entries = with_declared_png(base, method=0)
    fixed_overhead = len(make_zip(entries))
    for size, expectation in ((COMPRESSED_LIMIT, "accept"), (COMPRESSED_LIMIT + 1, "reject")):
        entries = with_declared_png(base, method=0)
        named(entries, "assets/boundary.png").data = png_with_padding(size - fixed_overhead)
        data = make_zip(entries)
        assert len(data) == size
        save("archive-" + ("at-limit" if size == COMPRESSED_LIMIT else "over-limit"), data, expectation,
             "Physical ZIP input is exactly " + str(size) + " bytes; a stored declared valid 1x1 PNG isolates the compressed-input cap.")

    # This separates payload compressed-byte totals from physical ZIP byte
    # limits: compressed payloads stay under 20 MiB, while headers put input over.
    entries = with_declared_png(base, method=0)
    asset_entry = named(entries, "assets/boundary.png")
    other_payload = sum(len(raw_deflate(entry.data)) for entry in entries if entry is not asset_entry)
    asset_entry.data = png_with_padding(COMPRESSED_LIMIT - other_payload - len(asset_entry.data))
    save("payload-at-limit-archive-over-limit", make_zip(entries), "reject",
         "Sum of compressed payload bytes is exactly 20 MiB, but physical ZIP bytes exceed 20 MiB.")

    for count in (ENTRY_LIMIT, ENTRY_LIMIT + 1):
        entries = clone(base)
        entries.extend(Entry("unknown-%04d.txt" % index, b"x" * 4096)
                       for index in range(count - len(entries)))
        save("entries-%d-undeclared" % count, make_zip(entries), "reject",
             str(count) + " archive entries; safe but undeclared text files also violate source allowlist.", isolated=False)
        directories = clone(base)
        directories.extend(Entry("empty-%04d/" % index, b"", method=0,
                                 external_attr=((stat.S_IFDIR | 0o755) << 16) | 0x10)
                           for index in range(count - len(directories)))
        save("entries-%d-directories" % count, make_zip(directories),
             "reject",
             str(count) + " central entries use empty directory names outside assets/, tokens/, and overrides/; 501 entries additionally exceeds the entry cap.",
             isolated=False)

    manifest = {
        "baseline": str(baseline),
        "baseline_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
        "limits": {"physical_archive_bytes": COMPRESSED_LIMIT, "expanded_bytes": EXPANDED_LIMIT,
                   "json_bytes": JSON_LIMIT, "entries": ENTRY_LIMIT},
        "expected_values": {"accept": "Must import successfully.",
                            "reject": "Must fail closed without returning a ThemeSource."},
        "fixtures": fixtures,
    }
    (output / "metadata.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    harness_expectations = [{
        "path": "zip/" + fixture["file"],
        "accept": fixture["expected"] == "accept",
        "note": fixture["reason"],
    } for fixture in fixtures]
    (output / "expectations.json").write_text(json.dumps(harness_expectations, indent=2) + "\n", encoding="utf-8")
    lines = ["# Standalone ZIP fixtures", "",
             "Generated by `tests/native/codec/create_zip_fixtures.py`; repository inputs are only read.", "",
             "`accept` means import succeeds; `reject` means fail closed without returning a theme.",
             "All expectations are mandatory under the selected strict ZIP envelope and metadata policies.", "",
             "Input limit means physical ZIP bytes, including headers and any trailing data.",
             "Valid data descriptors include zero local CRC/size fields; compare their actual data and descriptor with central metadata.",
             "Local-only and central-only mutations intentionally test both views of ZIP metadata.",
             "Size-boundary controls preserve valid JSON with whitespace or use a declared 1x1 PNG with an ignored private ancillary npAd chunk.",
             "No accepted fixture is claimed to be device-applicable or an installable overlay.", "",
             "A schema-valid source has at most 100 assets; 500 arbitrary declared files cannot be isolated as a valid source.",
             "The entry-count fixtures document their additional source allowlist conditions.", "",
             "| Fixture | Expected | Semantics |", "|---|---|---|"]
    lines.extend("| `%s` | %s | %s |" % (f["file"], f["expected"], f["reason"]) for f in fixtures)
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "fixtures": len(fixtures),
                      "accept": sum(f["expected"] == "accept" for f in fixtures),
                      "reject": sum(f["expected"] == "reject" for f in fixtures)}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE,
                        help="Baseline source bundle (defaults to repository AMOLED Black example)")
    parser.add_argument("--output", type=Path, required=True,
                        help="External directory for generated ZIPs and expectations, normally RUN_OUTPUT/fixtures/zip")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == REPO_ROOT or REPO_ROOT in output.parents:
        parser.error("--output must be outside the repository")
    generate(args.baseline.resolve(), output)


if __name__ == "__main__":
    main()
