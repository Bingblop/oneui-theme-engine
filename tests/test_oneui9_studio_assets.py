"""Deterministic asset sync tests; no Android tools or repository mutations."""

import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "tools/sync_oneui9_studio_assets.py"


class StudioAssetSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.themes = self.root / "themes"
        self.assets = self.root / "assets"
        for name in ("amoled-black", "neon-violet", "cyberpunk-gold"):
            source = self.themes / name
            (source / "tokens").mkdir(parents=True)
            manifest = {"format": "oneui-studio.source/1", "id": "org.example." + name, "version": "1.0.0", "name": name, "author": "Test", "license": "MIT", "licenseFile": "LICENSE.txt", "tokenApi": "oneui-studio.tokens/1", "targetIntent": {"manufacturer": "Samsung", "uiFamily": "One UI", "uiMajor": 9}, "variants": {"dark": "tokens/dark.json"}, "assets": [], "components": [{"id": "device.palette", "required": False}]}
            (source / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
            tokens = {role: {"type": "color", "value": "#FF010203"} for role in ("background", "surface", "accent", "onAccent", "textPrimary", "textSecondary", "quickTileInactive")}
            (source / "tokens/dark.json").write_text(json.dumps(tokens, indent=2) + "\n", encoding="utf-8")
            (source / "LICENSE.txt").write_text("license bytes\n", encoding="utf-8")
            (source / "unrelated.txt").write_text("must not be bundled", encoding="utf-8")
        self.pack = self.root / "resource-pack.json"
        self.pack.write_text(json.dumps({"format": "oneui9.resource-pack/1", "sourceTokenApi": "oneui-studio.tokens/1", "androidApiLevel": 37, "buildFingerprint": "test/device/build", "targets": [{"key": "framework", "package": "android", "apkSha256": "1" * 64, "bindings": []}]}) + "\n", encoding="utf-8")

    def command(self, *extra):
        return subprocess.run([sys.executable, str(SCRIPT), "--themes", str(self.themes), "--pack", str(self.pack), "--assets", str(self.assets)] + list(extra), capture_output=True, text=True, timeout=20)

    def write_assets(self):
        result = self.command("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def snapshot(self):
        if not self.assets.exists():
            return {}
        return {str(path.relative_to(self.assets)): (path.read_bytes(), path.stat().st_mtime_ns) for path in self.assets.rglob("*") if path.is_file()}

    def module(self):
        spec = importlib.util.spec_from_file_location("tools.studio_sync_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_default_check_reports_missing_without_creating_outputs(self):
        result = self.command()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(self.assets.exists())
        report = json.loads(result.stdout)
        self.assertEqual(len(report["differences"]), 4)
        self.assertTrue(all(item["reason"] == "missing" for item in report["differences"]))

    def test_write_exact_inventory_bytes_and_fixed_regular_file_metadata(self):
        self.write_assets()
        self.assertEqual((self.assets / "resource-pack.json").read_bytes(), self.pack.read_bytes())
        for name in ("amoled-black", "neon-violet", "cyberpunk-gold"):
            with zipfile.ZipFile(self.assets / "sources" / (name + ".ouitheme")) as archive:
                self.assertEqual(archive.namelist(), ["LICENSE.txt", "manifest.json", "tokens/dark.json"])
                for info in archive.infolist():
                    self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                    self.assertEqual(info.create_system, 3)
                    self.assertEqual(info.external_attr, 0o100644 << 16)
                    self.assertEqual(info.compress_type, zipfile.ZIP_DEFLATED)
                    self.assertEqual(info.extra, b"")
                    self.assertEqual(archive.read(info.filename), (self.themes / name / info.filename).read_bytes())

    def test_successful_check_and_repeat_write_preserve_bytes_and_mtimes(self):
        self.write_assets()
        before = self.snapshot()
        result = self.command("--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "in-sync")
        self.assertEqual(self.snapshot(), before)
        self.write_assets()
        self.assertEqual(self.snapshot(), before)

    def test_payload_drift_names_changed_entry_without_writing(self):
        self.write_assets()
        before = self.snapshot()
        token = self.themes / "neon-violet/tokens/dark.json"
        token.write_text(token.read_text().replace("#FF010203", "#FF998877"), encoding="utf-8")
        result = self.command()
        self.assertEqual(result.returncode, 1, result.stderr)
        difference = json.loads(result.stdout)["differences"][0]
        self.assertEqual(difference["path"], "sources/neon-violet.ouitheme")
        self.assertEqual(difference["changedEntries"], ["tokens/dark.json"])
        self.assertEqual(self.snapshot(), before)

    def test_bad_source_rejected_before_any_write(self):
        self.write_assets()
        before = self.snapshot()
        token = self.themes / "cyberpunk-gold/tokens/dark.json"
        token.write_text('{"background":{"type":"color","value":"#wrong"}}', encoding="utf-8")
        result = self.command("--write")
        self.assertEqual(result.returncode, 2)
        self.assertIn("#AARRGGBB", result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_declared_file_symlink_rejected(self):
        original = self.themes / "amoled-black/LICENSE.txt"
        outside = self.root / "outside.txt"
        outside.write_bytes(original.read_bytes())
        original.unlink()
        original.symlink_to(outside)
        result = self.command("--write")
        self.assertEqual(result.returncode, 2)
        self.assertIn("symlink", result.stderr.lower())
        self.assertFalse(self.assets.exists())

    def test_destination_symlinks_and_source_overlap_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        self.assets.symlink_to(outside, target_is_directory=True)
        result = self.command("--write")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(list(outside.iterdir()), [])
        self.assets.unlink()
        self.assets = self.themes / "amoled-black/output"
        result = self.command("--write")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.assets.exists())

    def test_unknown_destination_files_are_preserved(self):
        self.write_assets()
        sentinel = self.assets / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        self.write_assets()
        self.assertEqual(sentinel.read_text(), "keep")

    def test_invalid_pack_rejected(self):
        self.pack.write_text('{"format":"unsupported"}', encoding="utf-8")
        result = self.command("--write")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.assets.exists())

    def test_input_pack_at_any_known_output_rejected_without_overwrite(self):
        original = self.pack.read_bytes()
        self.pack = self.assets / "sources/amoled-black.ouitheme"
        self.pack.parent.mkdir(parents=True)
        self.pack.write_bytes(original)
        result = self.command("--write")
        self.assertEqual(result.returncode, 2)
        self.assertIn("input pack", result.stderr)
        self.assertEqual(self.pack.read_bytes(), original)
        self.assertFalse((self.assets / "resource-pack.json").exists())

    def test_missing_duplicate_or_incorrect_pack_targets_rejected(self):
        metadata = json.loads(self.pack.read_text())
        framework = metadata["targets"][0]
        for targets in ([], [framework, framework], [{**framework, "package": "not.android"}], [{**framework, "apkSha256": "not-a-hash"}]):
            with self.subTest(targets=targets):
                self.pack.write_text(json.dumps({**metadata, "targets": targets}), encoding="utf-8")
                result = self.command("--write")
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertFalse(self.assets.exists())

    def test_source_root_symlink_and_escaping_cli_path_rejected(self):
        link = self.root / "linked-themes"
        link.symlink_to(self.themes, target_is_directory=True)
        original = self.themes
        self.themes = link
        result = self.command("--write")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Symlink", result.stderr)
        self.themes = original / ".." / "themes"
        result = self.command("--write")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Escaping", result.stderr)
        self.assertFalse(self.assets.exists())

    def test_sparse_or_lowercase_native_source_rejected_before_outputs(self):
        token = self.themes / "amoled-black/tokens/dark.json"
        original = token.read_text()
        for invalid in ('{"background":{"type":"color","value":"#FF010203"}}', original.replace("#FF010203", "#ff010203")):
            with self.subTest(source=invalid):
                token.write_text(invalid, encoding="utf-8")
                result = self.command("--write")
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertFalse(self.assets.exists())

    def test_empty_license_or_invalid_asset_rejected_before_outputs(self):
        source = self.themes / "amoled-black"
        license_path = source / "LICENSE.txt"
        original = license_path.read_bytes()
        license_path.write_text("\n  \n", encoding="utf-8")
        result = self.command("--write")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertFalse(self.assets.exists())
        license_path.write_bytes(original)
        manifest_path = source / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["assets"] = [{"path": "assets/icon.png", "kind": "icon", "license": "MIT"}]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        (source / "assets").mkdir()
        (source / "assets/icon.png").write_bytes(b"not a PNG")
        result = self.command("--write")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertFalse(self.assets.exists())

    def test_staging_failure_preserves_existing_outputs(self):
        self.write_assets()
        before = self.snapshot()
        for source in self.themes.iterdir():
            path = source / "tokens/dark.json"
            path.write_text(path.read_text().replace("#FF010203", "#FF445566"), encoding="utf-8")
        module = self.module()
        original = Path.open

        def fail(path, mode="r", *args, **kwargs):
            if mode == "wb" and path.name == "neon-violet.ouitheme" and any(part.startswith(".studio-asset-sync-") for part in path.parts):
                raise OSError("fixture staging failure")
            return original(path, mode, *args, **kwargs)

        with mock.patch.object(Path, "open", fail):
            with self.assertRaisesRegex(OSError, "staging failure"):
                module.synchronize(self.themes, self.pack, self.assets, write=True)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any(path.name.startswith(".studio-asset-sync-") for path in self.assets.iterdir()))

    def test_size_preflight_and_growing_read_reject_before_unbounded_capture(self):
        license_path = self.themes / "amoled-black/LICENSE.txt"
        with license_path.open("wb") as handle:
            handle.truncate(1024 * 1024 + 1)
        result = self.command("--write")
        self.assertEqual(result.returncode, 2)
        self.assertIn("byte limit", result.stderr)
        self.assertFalse(self.assets.exists())
        module = self.module()
        tiny = self.root / "tiny.bin"
        tiny.write_bytes(b"ok")
        with mock.patch.object(Path, "open", return_value=io.BytesIO(b"0123456789")):
            with self.assertRaisesRegex(module.SyncError, "grew beyond byte limit"):
                module.bounded_bytes(tiny, 4, "Test input")

    def test_captured_json_schema_change_rejected_without_outputs(self):
        module = self.module()
        original = module.compiler.read_source

        def mutate_after_validation(source):
            validated = original(source)
            token_path = source / "tokens/dark.json"
            tokens = json.loads(token_path.read_text())
            tokens["unknownRole"] = {"type": "color", "value": "#FF445566"}
            token_path.write_text(json.dumps(tokens), encoding="utf-8")
            return validated

        with mock.patch.object(module.compiler, "read_source", mutate_after_validation):
            with self.assertRaises(ValueError):
                module.synchronize(self.themes, self.pack, self.assets, write=True)
        self.assertFalse(self.assets.exists())


if __name__ == "__main__":
    unittest.main()
