"""Bounded .ouitheme snapshots for the desktop compiler, using only stdlib.

ZIP policy and size limits match the native ThemeSource codec. Asset inspection
checks container metadata, not Android decoding, rendering, or overlay eligibility.
The caller supplies its existing source-schema validator.
"""

from contextlib import contextmanager
from collections.abc import Mapping
from decimal import Decimal, DecimalException
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import tempfile
from typing import NamedTuple
import zlib


MAX_COMPRESSED_BYTES = 20 * 1024 * 1024
MAX_EXPANDED_BYTES = 80 * 1024 * 1024
MAX_ENTRIES = 500
MAX_JSON_BYTES = 1024 * 1024
MAX_RASTER_DIMENSION = 8192
BASE_COLORS = {"background", "surface", "accent", "onAccent", "textPrimary", "textSecondary", "quickTileInactive"}
DIMENSIONS = {"cornerRadius": (0, 32), "quickTileRadius": (0, 32), "keyboardKeyRadius": (0, 24), "navigationBarHeight": (16, 96), "bodyTextSize": (10, 28)}
ALLOWED_FILES = {"manifest.json", "LICENSE.txt", "tokens/dark.json", "tokens/light.json", "overrides/dark.json", "overrides/light.json"}
ALLOWED_DIRECTORIES = {"tokens/", "overrides/", "assets/"}
ASSET = re.compile(r"assets/[A-Za-z0-9_-]+\.(png|jpg|jpeg|webp|ttf|otf)\Z")


class SourceArchiveError(ValueError):
    """Malformed or unsupported source archive; nothing may be compiled."""


class SourceArchive(NamedTuple):
    root: Path
    validated: tuple
    archive_sha256: str


def _need(condition, message):
    if not condition:
        raise SourceArchiveError(message)


def _u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def _path(raw):
    name = raw.decode("utf-8", errors="strict")
    _need(0 < len(name) <= 160 and re.fullmatch(r"[A-Za-z0-9._/-]+", name) and not name.startswith("/"), "Unsafe archive path")
    parts = name.split("/")
    _need(all(part not in {".", ".."} and (part or i == len(parts) - 1) for i, part in enumerate(parts)), "Unsafe archive path")
    _need(name in ALLOWED_FILES | ALLOWED_DIRECTORIES or ASSET.fullmatch(name), f"Unknown or executable source path: {name}")
    return name


def _extras(data):
    at = 0
    while at < len(data):
        _need(at + 4 <= len(data), "Truncated ZIP extra field")
        tag, size = struct.unpack_from("<HH", data, at); at += 4
        _need(at + size <= len(data), "Truncated ZIP extra field")
        body = data[at:at + size]
        if tag == 0x5455:
            _need(1 <= size <= 13 and not body[0] & ~7, "Invalid ZIP timestamp metadata")
        elif tag == 0x000A:
            _need(size == 32 and _u16(body, 4) == 1 and _u16(body, 6) == 24, "Unsupported NTFS ZIP metadata")
        elif tag == 0x7875:
            _need(size >= 5 and body[0] == 1, "Invalid ZIP uid/gid metadata")
            uid = body[1]
            _need(1 <= uid <= 8 and uid + 3 <= size, "Invalid ZIP uid metadata")
            gid = body[2 + uid]
            _need(1 <= gid <= 8 and uid + gid + 3 == size, "Invalid ZIP gid metadata")
        else:
            raise SourceArchiveError("Unsupported ZIP link/extra metadata")
        at += size


def _inspect(data):
    end = next((i for i in range(len(data) - 22, max(-1, len(data) - 65558), -1)
                if _u32(data, i) == 0x06054B50 and i + 22 + _u16(data, i + 20) == len(data)), None)
    _need(end is not None, "Missing ZIP central directory or trailing archive data")
    count = _u16(data, end + 10)
    _need(_u16(data, end + 4) == _u16(data, end + 6) == 0 and _u16(data, end + 8) == count and 0 < count <= MAX_ENTRIES, "Unsupported ZIP disk/count")
    directory_size, directory = _u32(data, end + 12), _u32(data, end + 16)
    _need(directory + directory_size == end, "Invalid ZIP directory bounds")
    entries, expanded, at = {}, 0, directory
    for _ in range(count):
        _need(at + 46 <= end and _u32(data, at) == 0x02014B50, "Invalid ZIP directory record")
        flags, method = _u16(data, at + 8), _u16(data, at + 10)
        crc, compressed, size = struct.unpack_from("<III", data, at + 16)
        names, extra, comment = struct.unpack_from("<HHH", data, at + 28)
        offset, attrs = _u32(data, at + 42), _u32(data, at + 38)
        next_at = at + 46 + names + extra + comment
        _need(next_at <= end and _u16(data, at + 34) == 0 and _u16(data, at + 6) <= 20
              and not flags & ~0x080E and method in {0, 8}
              and 0xFFFFFFFF not in {compressed, size, offset}, "Unsupported encrypted/ZIP64 ZIP entry")
        name = _path(data[at + 46:at + 46 + names])
        mode = attrs >> 16; kind = mode & 0xF000
        _need(kind in {0, 0x8000, 0x4000} and not (kind == 0x8000 and mode & 0o111), "ZIP symlink/special/executable entry rejected")
        _need(kind != 0x4000 or name.endswith("/"), "ZIP directory name mismatch")
        limit = MAX_JSON_BYTES if name.endswith(".json") or name == "LICENSE.txt" else MAX_EXPANDED_BYTES
        _need(offset < directory and compressed <= MAX_COMPRESSED_BYTES and size <= limit, "ZIP entry exceeds source limits")
        expanded += size
        _need(expanded <= MAX_EXPANDED_BYTES, "Expanded source exceeds 80 MiB")
        _need(name not in entries, f"Duplicate ZIP path: {name}")
        _extras(data[at + 46 + names:at + 46 + names + extra])
        entries[name] = {"offset": offset, "flags": flags, "method": method, "crc": crc, "compressed": compressed, "size": size}
        at = next_at
    _need(at == end, "Unclaimed ZIP directory bytes")
    expected = 0
    for name, entry in sorted(entries.items(), key=lambda item: item[1]["offset"]):
        at = entry["offset"]
        _need(at == expected and at + 30 <= directory and _u32(data, at) == 0x04034B50, "Overlapping/hidden ZIP local entry")
        names, extra = _u16(data, at + 26), _u16(data, at + 28)
        payload = at + 30 + names + extra; finish = payload + entry["compressed"]
        _need(finish <= directory and _u16(data, at + 4) <= 20 and _u16(data, at + 6) == entry["flags"] and _u16(data, at + 8) == entry["method"], "ZIP local metadata mismatch")
        _need(_path(data[at + 30:at + 30 + names]) == name, "ZIP local/central path mismatch")
        _extras(data[at + 30 + names:payload])
        local = struct.unpack_from("<III", data, at + 14)
        central = (entry["crc"], entry["compressed"], entry["size"])
        if entry["flags"] & 8:
            _need(all(actual in {0, wanted} for actual, wanted in zip(local, central)), "ZIP descriptor metadata mismatch")
            _need(finish + 12 <= directory, "Truncated ZIP descriptor")
            if _u32(data, finish) == 0x08074B50:
                finish += 4
            _need(finish + 12 <= directory and struct.unpack_from("<III", data, finish) == central, "ZIP descriptor disagreement")
            finish += 12
        else:
            _need(local == central, "ZIP local size/CRC mismatch")
        entry["payload"] = payload
        expected = finish
    _need(expected == directory, "Hidden ZIP data before central directory")
    return entries


def _inflate(data, entry):
    payload = memoryview(data)[entry["payload"]:entry["payload"] + entry["compressed"]]
    if entry["method"] == 0:
        value = bytes(payload)
    else:
        decoder = zlib.decompressobj(-15)
        value = decoder.decompress(payload, entry["size"] + 1)
        _need(decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data, "Truncated, oversized, or trailing deflate payload")
    _need(len(value) == entry["size"] and zlib.crc32(value) & 0xFFFFFFFF == entry["crc"], "ZIP size or CRC disagreement")
    return value


def _json(value):
    def pairs(items):
        result = {}
        for key, item in items:
            _need(key not in result, "Duplicate JSON key")
            result[key] = item
        return result
    def invalid_number(value):
        raise SourceArchiveError(f"Invalid JSON number: {value}")
    def number(value, integer=False):
        _need(len(value) <= 128, "JSON number exceeds 128 characters")
        try:
            decimal = Decimal(value)
            _need(decimal.is_finite() and abs(decimal.as_tuple().exponent) <= 2147483647
                  and math.isfinite(float(decimal)), "JSON number is outside native finite bounds")
            return int(value) if integer else decimal
        except (DecimalException, OverflowError, ValueError) as exc:
            raise SourceArchiveError("Invalid JSON number") from exc
    result = json.loads(value.decode("utf-8"), object_pairs_hook=pairs, parse_float=number,
                        parse_int=lambda value: number(value, True), parse_constant=invalid_number)
    _need(isinstance(result, dict), "Source JSON must be an object")
    def walk(value, depth=0):
        _need(depth <= 64, "JSON nesting exceeds 64")
        if isinstance(value, str):
            value.encode("utf-8", errors="strict")
        elif isinstance(value, dict):
            for key, item in value.items():
                key.encode("utf-8", errors="strict"); walk(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                walk(item, depth + 1)
    walk(result)
    return result


def _dimensions(width, height):
    _need(1 <= width <= MAX_RASTER_DIMENSION and 1 <= height <= MAX_RASTER_DIMENSION, "Invalid raster dimensions or dimensions exceed 8192")


def _asset(path, data):
    """Validate bounded container metadata without an image/font decoder."""
    suffix = Path(path).suffix
    if suffix == ".png":
        _need(data.startswith(b"\x89PNG\r\n\x1a\n"), "Invalid PNG signature")
        at, header, image, ended = 8, False, False, False
        while at < len(data):
            _need(at + 12 <= len(data), "Truncated PNG chunk")
            size = struct.unpack_from(">I", data, at)[0]; kind = data[at + 4:at + 8]
            _need(at + size + 12 <= len(data), "PNG chunk outside asset")
            _need(zlib.crc32(memoryview(data)[at + 4:at + size + 8]) & 0xFFFFFFFF == struct.unpack_from(">I", data, at + size + 8)[0], "PNG CRC mismatch")
            if not header:
                _need(kind == b"IHDR" and size == 13, "Missing PNG header")
                _dimensions(*struct.unpack_from(">II", data, at + 8)); header = True
            image |= kind == b"IDAT"; at += size + 12
            if kind == b"IEND":
                _need(size == 0 and at == len(data), "Trailing PNG content"); ended = True; break
        _need(header and image and ended, "Incomplete PNG")
    elif suffix in {".jpg", ".jpeg"}:
        _need(data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"), "Invalid JPEG container")
        at, dimensions = 2, False
        while at < len(data) - 2:
            _need(data[at] == 255, "Invalid JPEG marker")
            while at < len(data) and data[at] == 255:
                at += 1
            _need(at < len(data), "Truncated JPEG marker")
            marker = data[at]; at += 1
            if marker == 0xDA:
                break
            if marker in {0x01, 0xD8} or 0xD0 <= marker <= 0xD9:
                continue
            _need(at + 2 <= len(data), "Truncated JPEG segment")
            size = struct.unpack_from(">H", data, at)[0]
            _need(size >= 2 and at + size <= len(data), "JPEG segment outside asset")
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                _need(size >= 8, "Truncated JPEG dimensions")
                height, width = struct.unpack_from(">HH", data, at + 3); _dimensions(width, height); dimensions = True
            at += size
        _need(dimensions, "Missing JPEG dimensions")
    elif suffix == ".webp":
        _need(len(data) >= 20 and data[:4] == b"RIFF" and data[8:12] == b"WEBP" and _u32(data, 4) + 8 == len(data), "Invalid WebP container")
        at, dimensions, image = 12, False, False
        while at < len(data):
            _need(at + 8 <= len(data), "Truncated WebP chunk")
            kind, size = data[at:at + 4], _u32(data, at + 4); body = at + 8
            _need(body + size + (size & 1) <= len(data), "WebP chunk outside asset")
            if kind == b"VP8X":
                _need(size >= 10, "Truncated WebP dimensions")
                _dimensions(int.from_bytes(data[body + 4:body + 7], "little") + 1, int.from_bytes(data[body + 7:body + 10], "little") + 1); dimensions = True
            elif kind == b"VP8 ":
                _need(size >= 10 and data[body + 3:body + 6] == b"\x9d\x01\x2a", "Invalid VP8 header")
                _dimensions(_u16(data, body + 6) & 0x3FFF, _u16(data, body + 8) & 0x3FFF); dimensions = image = True
            elif kind == b"VP8L":
                _need(size >= 5 and data[body] == 0x2F, "Invalid VP8L header")
                bits = _u32(data, body + 1); _dimensions((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1); dimensions = image = True
            elif kind == b"ANMF":
                _need(size >= 16, "Truncated animated WebP frame"); image = True
            at = body + size + (size & 1)
        _need(dimensions and image, "Missing WebP dimensions/image")
    else:
        signature = b"OTTO" if suffix == ".otf" else b"\x00\x01\x00\x00"
        _need(len(data) >= 12 and (data[:4] == signature or suffix == ".ttf" and data[:4] == b"true"), "Font signature/extension mismatch")
        count = struct.unpack_from(">H", data, 4)[0]
        _need(0 < count <= 256 and 12 + 16 * count <= len(data), "Invalid font table directory")
        tables = {}
        for i in range(count):
            at = 12 + 16 * i; tag = data[at:at + 4]; offset, size = struct.unpack_from(">II", data, at + 8)
            _need(offset >= 12 + 16 * count and size > 0 and offset + size <= len(data) and tag not in tables, "Invalid font table bounds")
            tables[tag] = (offset, size)
        _need(all(tag in tables and tables[tag][1] >= minimum for tag, minimum in ((b"head", 54), (b"cmap", 4), (b"name", 6))), "Missing font metadata")
        head = tables[b"head"][0]; _need(struct.unpack_from(">I", data, head + 12)[0] == 0x5F0F3CF5 and 16 <= struct.unpack_from(">H", data, head + 18)[0] <= 16384, "Invalid font metadata")
        at, size = tables[b"name"]; count, strings = struct.unpack_from(">HH", data, at + 2)
        _need(0 < count <= 2048 and 6 + count * 12 <= size and strings <= size, "Invalid font names")
        for i in range(count):
            length, offset = struct.unpack_from(">HH", data, at + 6 + i * 12 + 8)
            _need(strings + offset + length <= size, "Font name outside table")


def _native_constraints(documents, manifest, variants, overrides):
    # Retain directory-source compatibility while archive input enforces the
    # native container's additional constraints using exact JSON decimals.
    _need(documents["manifest.json"]["targetIntent"]["uiMajor"] == 9, "Unsupported UI intention")
    if "stylePack" in manifest:
        _need(len(manifest["stylePack"]["id"]) <= 128, "Style pack id exceeds 128 characters")
    for field in ("overrides", "appearance"):
        _need(field not in manifest or manifest[field], f"Empty {field} declaration")
    for variant in variants:
        tokens = documents[f"tokens/{variant}.json"]
        _need(BASE_COLORS <= set(tokens), f"Missing baseline colors in {variant}")
    collections = [documents[f"tokens/{variant}.json"] for variant in variants]
    collections += [tokens for variant in overrides for tokens in documents[f"overrides/{variant}.json"].values()]
    for tokens in collections:
        for role, token in tokens.items():
            if token["type"] == "color":
                _need(re.fullmatch(r"#[0-9A-F]{8}", token["value"]), "Colors must use uppercase #AARRGGBB")
            elif role in DIMENSIONS:
                lower, upper = DIMENSIONS[role]
                _need(lower <= token["value"] <= upper, f"Dimension outside exact bounds: {role}")
    for settings in documents["manifest.json"].get("appearance", {}).values():
        for field in ("icons", "components"):
            _need(field not in settings or settings[field], f"Empty appearance {field}")
        for style in settings.get("components", {}).values():
            _need(0 <= style.get("strokeWidthDp", 0) <= 8, "Stroke width outside exact bounds")


def _payload(name, value):
    _need(isinstance(name, str) and isinstance(value, bytes), "Payloads require relative file names and bytes")
    _path(name.encode("utf-8", errors="strict"))
    _need(not name.endswith("/"), "Payload inventory must contain files only")
    limit = MAX_JSON_BYTES if name.endswith(".json") or name == "LICENSE.txt" else MAX_EXPANDED_BYTES
    _need(len(value) <= limit, f"Source payload exceeds byte limit: {name}")
    if name.endswith(".json"):
        return _json(value)
    if name == "LICENSE.txt":
        license_text = value.decode("utf-8", errors="strict")
        _need(license_text.strip() and "\x00" not in license_text, "Invalid source license")
    else:
        _asset(name, value)
    return None


def _validated_payloads(documents, files, validated):
    manifest, variants, overrides, declared = validated
    _need(files == set(declared), f"Undeclared or missing source files: {sorted(files ^ set(declared))}")
    expected = {"manifest.json": manifest}
    expected.update({f"tokens/{variant}.json": tokens for variant, tokens in variants.items()})
    expected.update({f"overrides/{variant}.json": targets for variant, targets in overrides.items()})
    for name, parsed in expected.items():
        # read_source uses ordinary floats; preserve those semantics for this
        # equality check, then enforce the original exact decimals below.
        encoded = lambda value: json.dumps(value, sort_keys=True, allow_nan=False, default=float)
        _need(encoded(documents[name]) == encoded(parsed), f"Payload changed since schema validation: {name}")
    _native_constraints(documents, manifest, variants, overrides)


def validate_source_payloads(payloads, validated):
    """Check source payload bytes against read_source's schema-validated tuple.

    Pure memory: no extraction, output, file reads, or payload mutations. ZIP
    envelope/compressed-size checks remain the archive reader's responsibility.
    """
    try:
        _need(isinstance(payloads, Mapping) and 0 < len(payloads) <= MAX_ENTRIES, "Invalid source payload count")
        _need(all(isinstance(value, bytes) for value in payloads.values()), "Source payloads must be bytes")
        _need(sum(map(len, payloads.values())) <= MAX_EXPANDED_BYTES, "Expanded source exceeds 80 MiB")
        documents = {}
        for name, value in payloads.items():
            document = _payload(name, value)
            if document is not None:
                documents[name] = document
        _validated_payloads(documents, set(payloads), validated)
    except SourceArchiveError:
        raise
    except (UnicodeError, ValueError, KeyError, TypeError, RecursionError, struct.error, DecimalException) as exc:
        raise SourceArchiveError(f"Invalid source payload: {exc}") from exc


@contextmanager
def open_source_archive(path, validate_source):
    """Yield a private validated snapshot; remove it after success or failure.

    validate_source(root) must return (manifest, variants, overrides, files), where
    files maps every declared relative path to its regular snapshot file.
    """
    try:
        with Path(path).open("rb") as handle:
            data = handle.read(MAX_COMPRESSED_BYTES + 1)
        _need(len(data) <= MAX_COMPRESSED_BYTES, "Compressed source exceeds 20 MiB")
        entries = _inspect(data)
        with tempfile.TemporaryDirectory(prefix="oneui9-source-") as temporary:
            root = Path(temporary); documents, files = {}, set()
            for name, entry in entries.items():
                value = _inflate(data, entry)
                if name.endswith("/"):
                    _need(not value, "Source directory contains data"); continue
                document = _payload(name, value)
                if document is not None:
                    documents[name] = document
                destination = root / name; destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("xb") as handle:
                    handle.write(value)
                files.add(name)
            validated = validate_source(root)
            _validated_payloads(documents, files, validated)
            yield SourceArchive(root, validated, hashlib.sha256(data).hexdigest())
    except SourceArchiveError:
        raise
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, RecursionError, struct.error, zlib.error, DecimalException) as exc:
        raise SourceArchiveError(f"Invalid source archive: {exc}") from exc
