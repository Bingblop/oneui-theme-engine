"""Stdlib archive-import tests and real builder CLI checks with fixture tools."""

import dataclasses
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib


REPO = Path(__file__).resolve().parents[1]
BUNDLES = REPO / "docs/design/theme-source/bundles"


def load_module(name, path):
    """Register before exec so dataclass annotations and sibling imports resolve."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class SourceArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = load_module("oneui9_source_archive", REPO / "tools/oneui9_source_archive.py")
        cls.builder = load_module("_source_archive_builder", REPO / "tools/build_oneui9_theme.py")
        cls.zip_helpers = load_module("_source_archive_zip_helpers", REPO / "tests/native/codec/create_zip_fixtures.py")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.zip_helpers.read_baseline(BUNDLES / "amoled-black.ouitheme")

    def save(self, entries=None, *, data=None, name="input.ouitheme"):
        path = self.root / name
        path.write_bytes(data if data is not None else self.zip_helpers.make_zip(entries or self.base))
        return path

    def changed_license(self, **changes):
        entries = [dataclasses.replace(entry) for entry in self.base]
        entry = next(entry for entry in entries if entry.name == "LICENSE.txt")
        for key, value in changes.items():
            setattr(entry, key, value)
        return entries

    def rich_entries(self):
        entries = [dataclasses.replace(entry) for entry in self.base]
        manifest_entry = next(entry for entry in entries if entry.name == "manifest.json")
        dark_entry = next(entry for entry in entries if entry.name == "tokens/dark.json")
        manifest = json.loads(manifest_entry.data)
        dark = json.loads(dark_entry.data)
        dark["quickTileRadius"] = {"type": "dimension", "value": 12.5, "unit": "dp"}
        dark["outline"] = {"type": "color", "value": "#80123456"}
        light = json.loads(json.dumps(dark))
        light["background"]["value"] = "#FFF8F9FB"
        light["surface"]["value"] = "#FFFFFFFF"
        light["cornerRadius"] = {"type": "dimension", "value": 16, "unit": "dp"}
        manifest["variants"]["light"] = "tokens/light.json"
        manifest["assets"] = [{"path": "assets/icon.png", "kind": "icon", "license": "CC0-1.0"}]
        manifest["overrides"] = {"dark": "overrides/dark.json", "light": "overrides/light.json"}
        manifest["appearance"] = {
            "dark": {"icons": {"quickPanel.wifi": "assets/icon.png"},
                     "components": {"quickTile": {"shape": "roundedRectangle", "fillRole": "quickTileInactive",
                                                   "radiusRole": "quickTileRadius", "strokeRole": "outline", "strokeWidthDp": 1.5}}},
            "light": {"icons": {"quickPanel.wifi": "assets/icon.png"},
                      "components": {"card": {"shape": "roundedRectangle", "fillRole": "surface", "radiusRole": "cornerRadius"}}},
        }
        manifest["components"].extend([{"id": "keyboard.palette", "required": False}, {"id": "launcher.icons", "required": False}])
        manifest_entry.data = (json.dumps(manifest, indent=2) + "\n").encode()
        dark_entry.data = (json.dumps(dark, indent=2) + "\n").encode()
        entries.extend([
            self.zip_helpers.Entry("tokens/light.json", (json.dumps(light, indent=2) + "\n").encode()),
            self.zip_helpers.Entry("overrides/dark.json", b'{"keyboard":{"keyboardBackground":{"type":"color","value":"#FF0D0E0F"}}}\n'),
            self.zip_helpers.Entry("overrides/light.json", b'{"settings":{"settingsBackground":{"type":"color","value":"#FFEFF0F1"}}}\n'),
            self.zip_helpers.Entry("assets/icon.png", self.zip_helpers.png_with_padding(0)),
        ])
        return entries

    def reject_before_callback(self, path):
        called = []

        def validate(root):
            called.append(root)
            return self.builder.read_source(root)

        with self.assertRaises(self.archive.SourceArchiveError):
            with self.archive.open_source_archive(path, validate):
                self.fail("Invalid archive returned a source")
        self.assertEqual(called, [], "Unsafe ZIP reached the source callback")

    def test_real_repository_bundles_validate_and_cleanup(self):
        for path in sorted(BUNDLES.glob("*.ouitheme")):
            with self.subTest(bundle=path.name):
                original = path.read_bytes()
                with self.archive.open_source_archive(path, self.builder.read_source) as source:
                    extracted = source.root
                    self.assertIsInstance(extracted, Path)
                    self.assertTrue(extracted.is_dir())
                    self.assertNotEqual(extracted, path.parent)
                    manifest, variants, overrides, files = source.validated
                    self.assertEqual(len(source.validated), 4)
                    self.assertEqual(source.archive_sha256, hashlib.sha256(original).hexdigest())
                    with zipfile.ZipFile(path) as archive:
                        expected = {name for name in archive.namelist() if not name.endswith("/")}
                        self.assertEqual(set(files), expected)
                        for name, file in files.items():
                            self.assertTrue(file.resolve().is_relative_to(extracted.resolve()))
                            self.assertEqual(file.read_bytes(), archive.read(name))
                    self.assertTrue(manifest["id"].startswith("org.bingblop."))
                    self.assertIn("dark", variants)
                    self.assertIsInstance(overrides, dict)
                self.assertFalse(extracted.exists())
                self.assertEqual(path.read_bytes(), original)

    def test_signed_and_unsigned_data_descriptors_are_accepted(self):
        for descriptor in ("signed", "unsigned"):
            with self.subTest(descriptor=descriptor):
                entries = [dataclasses.replace(entry, descriptor=descriptor) for entry in self.base]
                with self.archive.open_source_archive(self.save(entries), self.builder.read_source) as source:
                    self.assertEqual(source.validated[0]["id"], "org.bingblop.amoled-black")

    def test_rich_source_preserves_variants_overrides_appearance_assets_and_license(self):
        entries = self.rich_entries()
        expected = {entry.name: entry.data for entry in entries}
        with self.archive.open_source_archive(self.save(entries), self.builder.read_source) as source:
            extracted = source.root
            manifest, variants, overrides, files = source.validated
            self.assertEqual(set(files), set(expected))
            for name, data in expected.items():
                self.assertEqual(files[name].read_bytes(), data, name)
            self.assertEqual(manifest, json.loads(expected["manifest.json"]))
            self.assertEqual(variants, {variant: json.loads(expected[f"tokens/{variant}.json"]) for variant in ("dark", "light")})
            self.assertEqual(overrides, {variant: json.loads(expected[f"overrides/{variant}.json"]) for variant in ("dark", "light")})
            self.assertEqual(manifest["assets"][0]["license"], "CC0-1.0")
            self.assertEqual(manifest["appearance"]["dark"]["icons"]["quickPanel.wifi"], "assets/icon.png")
            self.assertEqual(manifest["appearance"]["dark"]["components"]["quickTile"]["shape"], "roundedRectangle")
            self.assertEqual(set(overrides["dark"]), {"keyboard"})
            self.assertEqual(set(overrides["light"]), {"settings"})
            self.assertNotIn("bodyTextSize", variants["dark"], "Importer added a preview default")
            self.assertNotIn("navigationBarHeight", variants["light"], "Importer added a preview default")
            self.assertEqual(source.archive_sha256, hashlib.sha256(self.zip_helpers.make_zip(entries)).hexdigest())
        self.assertFalse(extracted.exists())

    def test_supported_local_and_central_extra_fields_are_accepted(self):
        fields = {
            "timestamp": self.zip_helpers.extra_field(0x5455, b"\x01" + struct.pack("<I", 0)),
            "ntfs": self.zip_helpers.extra_field(0x000A, b"\0" * 4 + struct.pack("<HHQQQ", 1, 24, 0, 0, 0)),
            "uid-gid": self.zip_helpers.extra_field(0x7875, b"\x01\x01\x64\x01\x64"),
        }
        for name, extra in fields.items():
            with self.subTest(extra=name):
                path = self.save(self.changed_license(local_extra=extra, central_extra=extra))
                with self.archive.open_source_archive(path, self.builder.read_source) as source:
                    self.assertIn("LICENSE.txt", source.validated[3])

    def test_path_attacks_do_not_reach_callback_or_write_outside(self):
        outside = self.root / "escape.txt"
        names = ("../escape.txt", "..\\escape.txt", str(outside), "C:/escape.txt", "LICENSE.txt\0hidden")
        for name in names:
            with self.subTest(name=name):
                self.reject_before_callback(self.save(self.changed_license(name=name)))
                self.assertFalse(outside.exists())

    def test_duplicate_members_are_rejected_before_callback(self):
        entries = [dataclasses.replace(entry) for entry in self.base]
        entries.append(dataclasses.replace(next(entry for entry in entries if entry.name == "manifest.json")))
        self.reject_before_callback(self.save(entries))

    def test_central_symlink_and_unix_link_extra_fields_are_rejected(self):
        changes = [
            {"external_attr": (stat.S_IFLNK | 0o777) << 16},
            {"local_extra": self.zip_helpers.asi_unix_extra(stat.S_IFLNK | 0o777, b"tokens/dark.json")},
            {"central_extra": self.zip_helpers.asi_unix_extra(stat.S_IFLNK | 0o777, b"tokens/dark.json")},
            {"local_extra": self.zip_helpers.extra_field(0x000D, struct.pack("<IIHH", 0, 0, 1000, 1000) + b"tokens/dark.json")},
            {"local_extra": self.zip_helpers.asi_unix_extra(stat.S_IFREG | 0o644)},
            {"local_extra": self.zip_helpers.extra_field(0xFAFE, b"")},
        ]
        for change in changes:
            with self.subTest(change=change):
                self.reject_before_callback(self.save(self.changed_license(**change)))

    def test_unix_execute_bit_is_rejected_before_callback(self):
        self.reject_before_callback(self.save(self.changed_license(external_attr=(stat.S_IFREG | 0o755) << 16)))

    def test_nested_zip_payload_cannot_masquerade_as_declared_png(self):
        entries = self.rich_entries()
        icon = next(entry for entry in entries if entry.name == "assets/icon.png")
        icon.data = self.zip_helpers.make_zip(self.base)
        self.reject_before_callback(self.save(entries))

    def test_encryption_flags_in_either_header_are_rejected(self):
        for change in ({"flags": 1}, {"local_flags": 1}, {"central_flags": 1}):
            with self.subTest(change=change):
                self.reject_before_callback(self.save(self.changed_license(**change)))

    def test_prefix_trailer_and_truncated_envelopes_are_rejected(self):
        data = self.zip_helpers.make_zip(self.base)
        for changed in (b"SFX\n" + data, data + b"JUNK\n", data[:-5], data[:150]):
            with self.subTest(length=len(changed)):
                self.reject_before_callback(self.save(data=changed))

    def test_local_central_names_sizes_flags_and_crc_must_agree(self):
        license_entry = next(entry for entry in self.base if entry.name == "LICENSE.txt")
        changes = [
            {"local_name": "LICENXE.txt"}, {"central_name": "LICENXE.txt"},
            {"local_name": "../LICENSE.txt"}, {"central_name": "../LICENSE.txt"},
            {"central_uncompressed_size": len(license_entry.data) + 1},
            {"local_uncompressed_size": len(license_entry.data) + 1},
            {"local_compressed_size": len(self.zip_helpers.raw_deflate(license_entry.data)) + 1},
            {"central_compressed_size": len(self.zip_helpers.raw_deflate(license_entry.data)) + 1},
            {"local_crc": 1}, {"central_crc": 1},
            {"local_flags": 0x0800}, {"central_present": False},
            {"method": 99},
        ]
        for change in changes:
            with self.subTest(change=change):
                self.reject_before_callback(self.save(self.changed_license(**change)))

    def test_corrupted_payload_is_rejected_before_callback(self):
        entry = next(entry for entry in self.base if entry.name == "LICENSE.txt")
        original_crc = zlib.crc32(entry.data) & 0xFFFFFFFF
        changed = bytes([entry.data[0] ^ 1]) + entry.data[1:]
        self.reject_before_callback(self.save(self.changed_license(
            method=0, data=changed, local_crc=original_crc, central_crc=original_crc)))

    def test_deflate_cannot_hide_extra_output_or_incomplete_stream(self):
        entry = next(entry for entry in self.base if entry.name == "LICENSE.txt")
        original_crc = zlib.crc32(entry.data) & 0xFFFFFFFF
        payloads = {
            "falsified-expanded-size": self.zip_helpers.raw_deflate(entry.data + b"hidden expanded content"),
            "trailing-compressed-data": self.zip_helpers.raw_deflate(entry.data) + b"hidden compressed content",
            "truncated-deflate-end": self.zip_helpers.raw_deflate(entry.data)[:-1],
        }
        for label, payload in payloads.items():
            with self.subTest(payload=label):
                # Both headers consistently describe only the original license.
                entries = self.changed_license(
                    compressed_payload=payload, local_crc=original_crc, central_crc=original_crc,
                    local_uncompressed_size=len(entry.data), central_uncompressed_size=len(entry.data))
                self.reject_before_callback(self.save(entries))

    def test_data_descriptor_crc_and_size_must_agree(self):
        entries = [dataclasses.replace(entry, descriptor="signed") for entry in self.base]
        data = self.zip_helpers.make_zip(entries)
        descriptor = data.index(b"PK\x07\x08")
        for field in (descriptor + 4, descriptor + 12):
            with self.subTest(field=field):
                changed = bytearray(data)
                struct.pack_into("<I", changed, field, struct.unpack_from("<I", changed, field)[0] ^ 1)
                self.reject_before_callback(self.save(data=bytes(changed)))

    def test_undeclared_allowed_asset_and_unlisted_files_are_rejected(self):
        for name in ("assets/undeclared.png", "unexpected.txt", "nested.zip", "run.sh"):
            with self.subTest(name=name):
                entries = [dataclasses.replace(entry) for entry in self.base]
                payload = self.zip_helpers.png_with_padding(0) if name.endswith(".png") else b"undeclared payload"
                entries.append(self.zip_helpers.Entry(name, payload))
                with self.assertRaises(self.archive.SourceArchiveError) as failure:
                    with self.archive.open_source_archive(self.save(entries), self.builder.read_source):
                        self.fail("Undeclared member returned a source")
                if name.endswith(".png"):
                    self.assertIn("Undeclared", str(failure.exception))

    def test_archive_native_color_and_exact_number_constraints(self):
        for field in ("lowercase-color", "precise-radius", "precise-ui-major"):
            with self.subTest(field=field):
                entries = [dataclasses.replace(entry) for entry in self.base]
                tokens = next(entry for entry in entries if entry.name == "tokens/dark.json")
                manifest = next(entry for entry in entries if entry.name == "manifest.json")
                if field == "lowercase-color":
                    tokens.data = tokens.data.replace(b"#FF00E5FF", b"#ff00e5ff")
                elif field == "precise-radius":
                    tokens.data = tokens.data.rstrip().removesuffix(b"}") + b',"cornerRadius":{"type":"dimension","value":32.000000000000000001,"unit":"dp"}}'
                else:
                    manifest.data = manifest.data.replace(b'"uiMajor": 9', b'"uiMajor": 9.000000000000000001')
                with self.assertRaises(self.archive.SourceArchiveError):
                    with self.archive.open_source_archive(self.save(entries), self.builder.read_source):
                        self.fail("Invalid native source constraint was accepted")

    def test_expanded_size_bomb_metadata_is_rejected_before_callback(self):
        size = 80 * 1024 * 1024 + 1
        self.reject_before_callback(self.save(self.changed_license(
            local_uncompressed_size=size, central_uncompressed_size=size)))

    def test_json_byte_limit_is_enforced_before_callback(self):
        entries = [dataclasses.replace(entry) for entry in self.base]
        manifest = next(entry for entry in entries if entry.name == "manifest.json")
        manifest.data += b" " * (1024 * 1024 + 1 - len(manifest.data))
        self.reject_before_callback(self.save(entries))

    def test_physical_archive_limit_rejects_sparse_oversized_input(self):
        path = self.root / "oversized.ouitheme"
        with path.open("wb") as handle:
            handle.truncate(20 * 1024 * 1024 + 1)
        self.reject_before_callback(path)

    def test_entry_limit_is_enforced_before_callback(self):
        entries = [dataclasses.replace(entry) for entry in self.base]
        entries.extend(self.zip_helpers.Entry(f"assets/file{index}.png", b"", method=0)
                       for index in range(501 - len(entries)))
        self.reject_before_callback(self.save(entries))

    def test_archive_requires_all_seven_baseline_roles(self):
        for role in ("background", "surface", "accent", "onAccent", "textPrimary", "textSecondary", "quickTileInactive"):
            with self.subTest(role=role):
                entries = [dataclasses.replace(entry) for entry in self.base]
                tokens_entry = next(entry for entry in entries if entry.name == "tokens/dark.json")
                tokens = json.loads(tokens_entry.data)
                del tokens[role]
                tokens_entry.data = json.dumps(tokens).encode()
                with self.assertRaises(self.archive.SourceArchiveError):
                    with self.archive.open_source_archive(self.save(entries), self.builder.read_source):
                        self.fail("Archive without a baseline role returned a source")

    def test_callback_failure_removes_private_extraction(self):
        roots = []

        def fail(root):
            roots.append(root)
            self.assertTrue(root.is_dir())
            raise RuntimeError("fixture callback failure")

        with self.assertRaisesRegex(RuntimeError, "fixture callback failure"):
            with self.archive.open_source_archive(self.save(), fail):
                self.fail("Failing callback returned a source")
        self.assertEqual(len(roots), 1)
        self.assertFalse(roots[0].exists())

    def test_consumer_failure_removes_private_extraction(self):
        extracted = None
        with self.assertRaisesRegex(RuntimeError, "fixture consumer failure"):
            with self.archive.open_source_archive(self.save(), self.builder.read_source) as source:
                extracted = source.root
                raise RuntimeError("fixture consumer failure")
        self.assertFalse(extracted.exists())

    def test_open_archive_is_a_snapshot_of_input_bytes(self):
        path = self.save()
        original = path.read_bytes()
        with self.archive.open_source_archive(path, self.builder.read_source) as source:
            path.write_bytes(b"changed original input")
            self.assertEqual(source.archive_sha256, hashlib.sha256(original).hexdigest())
            self.assertEqual(source.validated[3]["LICENSE.txt"].read_bytes(),
                             next(entry.data for entry in self.base if entry.name == "LICENSE.txt"))

    @unittest.skipUnless(os.environ.get("ONEUI9_NATIVE_EXPORT"), "Optional native export path not supplied")
    def test_optional_native_export_import(self):
        path = Path(os.environ["ONEUI9_NATIVE_EXPORT"])
        with self.archive.open_source_archive(path, self.builder.read_source) as source:
            self.assertEqual(source.archive_sha256, hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertIn("manifest.json", source.validated[3])
            self.assertTrue(source.validated[1])


class SourceArchiveBuilderCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Keep the imported TestCase inside its module; unittest must not discover it twice.
        cls.fixtures = load_module("_source_archive_cli_fixtures", REPO / "tests/test_oneui9_theme_builder.py")
        cls.zip_helpers = load_module("_source_archive_cli_zip_helpers", REPO / "tests/native/codec/create_zip_fixtures.py")

    def setUp(self):
        self.fixture = self.fixtures.ThemeBuilderTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def make_archive(self):
        fixture = self.fixture
        for role, value in {"surface": "#FF101112", "onAccent": "#FF000000",
                            "textPrimary": "#FFFFFFFF", "textSecondary": "#FFB0B0B0",
                            "quickTileInactive": "#FF202122"}.items():
            fixture.tokens[role] = {"type": "color", "value": value}
        fixture.save()
        path = fixture.root / "source.ouitheme"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(fixture.source.rglob("*")):
                if file.is_file():
                    archive.write(file, file.relative_to(fixture.source).as_posix())
        return path

    def test_actual_builder_cli_compiles_archive_input_and_bundles_source(self):
        archive_path = self.make_archive()
        original = archive_path.read_bytes()
        self.fixture.source = archive_path
        result = self.fixture.run_builder()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.fixture.report()
        self.assertFalse(report["applied"])
        self.assertFalse(report["policyVerified"])
        self.assertEqual(archive_path.read_bytes(), original)
        with zipfile.ZipFile(self.fixture.output / "org.example.safe-theme-theme.zip") as bundle:
            self.assertEqual(bundle.read("source/LICENSE.txt"), b"fixture license\n")
            tokens = json.loads(bundle.read("source/tokens/dark.json"))
            self.assertEqual(tokens["background"]["value"], "#FF07080B")
            self.assertIn("resource-pack.json", bundle.namelist())

    def test_actual_builder_cli_rejects_unsafe_archive_before_output(self):
        archive_path = self.make_archive()
        baseline = self.zip_helpers.read_baseline(archive_path)
        for name in ("../LICENSE.txt", "unexpected.txt", "assets/undeclared.png"):
            with self.subTest(name=name):
                entries = [dataclasses.replace(entry) for entry in baseline]
                payload = self.zip_helpers.png_with_padding(0) if name.endswith(".png") else b"unsafe"
                entries.append(self.zip_helpers.Entry(name, payload))
                archive_path.write_bytes(self.zip_helpers.make_zip(entries))
                self.fixture.source = archive_path
                result = self.fixture.run_builder()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(self.fixture.output.exists())
                if name.endswith(".png"):
                    self.assertIn("Undeclared", result.stderr)

    def test_directory_and_archive_cli_source_digests_match(self):
        archive_path = self.make_archive()
        result = self.fixture.run_builder()
        self.assertEqual(result.returncode, 0, result.stderr)
        directory_report = self.fixture.report()
        self.assertNotIn("sourceArchiveSha256", directory_report)
        self.fixture.source = archive_path
        self.fixture.output = self.fixture.root / "archive-output"
        result = self.fixture.run_builder()
        self.assertEqual(result.returncode, 0, result.stderr)
        archive_report = self.fixture.report()
        self.assertEqual(archive_report["sourceFiles"], directory_report["sourceFiles"])
        self.assertEqual(archive_report["sourceSha256"], directory_report["sourceSha256"])
        self.assertEqual(archive_report["sourceArchiveSha256"], hashlib.sha256(archive_path.read_bytes()).hexdigest())

    def test_existing_sparse_directory_input_behavior_is_preserved(self):
        self.assertNotIn("surface", self.fixture.tokens)
        (self.fixture.source / "ignored.txt").write_text("Existing directory inputs ignore unlisted files\n")
        result = self.fixture.run_builder()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.fixture.report()["applied"])


if __name__ == "__main__":
    unittest.main()
