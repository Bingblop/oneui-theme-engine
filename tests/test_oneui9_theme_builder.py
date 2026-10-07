"""Desktop compiler contract tests, using isolated command-line tool fixtures."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
import zipfile


BUILDER = Path(__file__).resolve().parents[1] / "tools/build_oneui9_theme.py"
ANDROID = "{http://schemas.android.com/apk/res/android}"


FAKE_AAPT2 = r'''#!/usr/bin/env python3
import json, os, pathlib, sys, xml.etree.ElementTree as ET
a = sys.argv[1:]
if a[0] == os.environ.get("FAKE_FAIL_STAGE"):
    print("fixture tool rejected stage", file=sys.stderr); sys.exit(17)
if a == ["version"]:
    print("Android Asset Packaging Tool (aapt) fixture-37"); sys.exit()
if a[:2] == ["dump", "resources"]:
    data=json.loads(pathlib.Path(a[-1]).read_text())
    print("Binary APK\nPackage name="+data["package"]+" id=7f")
    for i, item in enumerate(data["resources"]):
        print("    resource "+item.get("id", "0x7f010000")+" "+item["type"]+"/"+item["name"])
        for qualifier, value in item["values"].items():
            print("      ("+qualifier+") "+value)
    sys.exit()
if a[0] == "compile":
    pathlib.Path(a[a.index("-o")+1]).write_text(json.dumps({"res":a[a.index("--dir")+1]})); sys.exit()
if a[0] == "link":
    manifest=ET.parse(a[a.index("--manifest")+1]).getroot()
    source=pathlib.Path(json.loads(pathlib.Path(a[-1]).read_text())["res"])
    resources={}
    for folder in sorted(source.glob("values*")):
        qualifier=folder.name.removeprefix("values").removeprefix("-")
        for file in sorted(folder.glob("*.xml")):
            for value in ET.parse(file).getroot():
                key=(value.tag, value.get("name"))
                item=resources.setdefault(key, {"type":value.tag,"name":value.get("name"),"values":{}})
                text=value.text
                if value.tag=="color" and os.environ.get("FAKE_CORRUPT_OUTPUT"):
                    text="#ff000001"
                item["values"][qualifier]=text
    result={"package":manifest.get("package"),"resources":list(resources.values())}
    pathlib.Path(a[a.index("-o")+1]).write_text(json.dumps(result)); sys.exit()
print("unexpected arguments",file=sys.stderr);sys.exit(18)
'''

FAKE_ZIPALIGN = r'''#!/usr/bin/env python3
import pathlib, shutil, sys
a=sys.argv[1:]
if "-c" in a:
    sys.exit(0 if pathlib.Path(a[-1]).is_file() else 1)
shutil.copyfile(a[-2],a[-1])
'''

FAKE_APKSIGNER = r'''#!/usr/bin/env python3
import shutil,sys
a=sys.argv[1:]
if a==["version"]: print("fixture signer");sys.exit()
if a[0]=="sign": shutil.copyfile(a[-1],a[a.index("--out")+1]);sys.exit()
if a[0]=="verify": print("Verifies");sys.exit()
sys.exit(18)
'''


class ThemeBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        (self.source / "tokens").mkdir(parents=True)
        self.manifest = {
            "format": "oneui-studio.source/1", "id": "org.example.safe-theme",
            "version": "1.0.0", "name": "Name $(must not run)", "author": "Test",
            "license": "MIT", "licenseFile": "LICENSE.txt",
            "tokenApi": "oneui-studio.tokens/1",
            "targetIntent": {"manufacturer": "Samsung", "uiFamily": "One UI", "uiMajor": 9},
            "variants": {"dark": "tokens/dark.json"}, "assets": [],
            "components": [{"id": "device.palette", "required": False}],
        }
        self.tokens = {
            "background": {"type": "color", "value": "#FF07080B"},
            "accent": {"type": "color", "value": "#FF8A2BE2"},
            "quickTileRadius": {"type": "dimension", "value": 12.5, "unit": "dp"},
            "keyboardKeyRadius": {"type": "dimension", "value": 8, "unit": "dp"},
        }
        (self.source / "LICENSE.txt").write_text("fixture license\n")
        self.inputs = self.root / "inputs"
        self.targets = []
        for key, package, prefix in [("framework", "android", "01"), ("systemui", "com.android.systemui", "7e")]:
            relative = f"apks/{package}/base.apk"
            apk = self.inputs / relative
            apk.parent.mkdir(parents=True)
            resources = [
                {"type": "color", "name": "real_background", "id": f"0x{prefix}060001", "values": {"": "@color/original_background"}},
                {"type": "color", "name": "real_accent", "id": f"0x{prefix}060002", "values": {"": "#ff000000"}},
                {"type": "dimen", "name": "real_radius", "id": f"0x{prefix}070001", "values": {"": "32.000000dp"}},
            ]
            apk.write_text(json.dumps({"package": package, "resources": resources}))
            bindings = [self.binding("color", "real_background", f"0x{prefix}060001", "background", "dark", ["", "night"])]
            if key == "systemui":
                bindings.extend([
                    self.binding("dimen", "real_radius", f"0x{prefix}070001", "quickTileRadius", "current", [""]),
                    self.binding("color", "real_accent", f"0x{prefix}060002", "accent", "light", [""]),
                ])
            self.targets.append({"key": key, "package": package, "apkPath": relative, "apkSha256": hashlib.sha256(apk.read_bytes()).hexdigest(), "bindings": bindings})
        self.pack = {
            "format": "oneui9.resource-pack/1", "buildFingerprint": "Samsung/device/build:17/release",
            "androidApiLevel": 37, "sourceTokenApi": "oneui-studio.tokens/1", "targets": self.targets,
        }
        self.packfile = self.root / "pack.json"
        self.output = self.root / "output"
        self.toolpaths = {}
        for name, script in [("aapt2", FAKE_AAPT2), ("zipalign", FAKE_ZIPALIGN), ("apksigner", FAKE_APKSIGNER)]:
            path = self.root / name
            path.write_text(script)
            path.chmod(0o755)
            self.toolpaths[name] = path
        self.save()

    @staticmethod
    def binding(kind, name, resource_id, role, variant, qualifiers):
        return {"type": kind, "name": name, "resourceId": resource_id, "role": role, "variant": variant, "qualifiers": qualifiers, "evidence": "measured fixture resource"}

    def save(self):
        (self.source / "manifest.json").write_text(json.dumps(self.manifest))
        (self.source / "tokens/dark.json").write_text(json.dumps(self.tokens))
        self.packfile.write_text(json.dumps(self.pack))

    def run_builder(self, *, env=None, extra=()):
        args = [sys.executable, str(BUILDER), "--source", str(self.source), "--pack", str(self.packfile), "--inputs", str(self.inputs), "--output", str(self.output)]
        for name, path in self.toolpaths.items():
            args.extend([f"--{name}", str(path)])
        return subprocess.run(args + list(extra), capture_output=True, text=True, env={**os.environ, **(env or {})}, timeout=20)

    def report(self):
        return json.loads((self.output / "build-report.json").read_text())

    def save_collector_report(self, fingerprint=None, sdk="37"):
        report = {"device": {"properties": {"ro.build.fingerprint": fingerprint or self.pack["buildFingerprint"], "ro.build.version.sdk": sdk}}, "packages": {}}
        for target in self.targets:
            report["packages"][target["package"]] = {"apks": [{"localPath": target["apkPath"], "sha256": target["apkSha256"], "sizeBytes": (self.inputs / target["apkPath"]).stat().st_size}]}
        (self.inputs / "report.json").write_text(json.dumps(report))

    def test_verifies_matching_collector_metadata(self):
        self.save_collector_report()
        result = self.run_builder()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.report()["metadataVerified"])

    def test_rejects_wrong_collector_fingerprint_or_api_before_output(self):
        for fingerprint, sdk in (("different/build", "37"), (self.pack["buildFingerprint"], "36")):
            with self.subTest(fingerprint=fingerprint, sdk=sdk):
                self.save_collector_report(fingerprint, sdk)
                result = self.run_builder()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("does not match", result.stderr)
                self.assertFalse(self.output.exists())

    def test_rejects_mismatched_collector_apk_evidence(self):
        self.save_collector_report()
        path = self.inputs / "report.json"
        report = json.loads(path.read_text())
        report["packages"]["android"]["apks"][0]["sizeBytes"] += 1
        path.write_text(json.dumps(report))
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("evidence mismatch", result.stderr)
        self.assertFalse(self.output.exists())

    def test_generates_only_explicit_tokens_and_verifies_compiled_color_dimension_configs(self):
        result = self.run_builder()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.report()
        self.assertFalse(report["applied"])
        self.assertFalse(report["policyVerified"])
        self.assertTrue(all(t["compiledValueVerification"] for t in report["targets"]))
        values = ET.parse(self.output / "targets/systemui/res/values/values.xml").getroot()
        self.assertEqual({x.get("name"): x.text for x in values}, {"real_background": "#FF07080B", "real_radius": "12.5dp"})
        night = ET.parse(self.output / "targets/systemui/res/values-night/values.xml").getroot()
        self.assertEqual([(x.tag, x.get("name"), x.text) for x in night], [("color", "real_background", "#FF07080B")])
        manifest = ET.parse(self.output / "targets/systemui/AndroidManifest.xml").getroot()
        self.assertEqual(manifest.find("application").get(ANDROID + "hasCode"), "false")
        self.assertIsNone(manifest.find("overlay").get(ANDROID + "targetName"))
        self.assertEqual(manifest.find("overlay").get(ANDROID + "targetPackage"), "com.android.systemui")
        self.assertTrue(any(x["role"] == "accent" and x["reason"] == "source-variant-missing" for x in report["targets"][1]["omittedBindings"]))
        self.assertTrue(any(x["role"] == "keyboardKeyRadius" for x in report["omittedControls"]))
        self.assertEqual(report["targets"][0]["replacements"][0]["originalValues"][0]["kind"], "reference")

    def test_applies_per_app_override_and_reports_valid_unmatched_keyboard_controls(self):
        (self.source / "overrides").mkdir()
        self.manifest["overrides"] = {"dark": "overrides/dark.json"}
        overrides = {"systemui": {"background": {"type": "color", "value": "#FF102030"}}, "keyboard": {"accent": {"type": "color", "value": "#FF998877"}}}
        (self.source / "overrides/dark.json").write_text(json.dumps(overrides))
        self.save()
        result = self.run_builder()
        self.assertEqual(result.returncode, 0, result.stderr)
        values = ET.parse(self.output / "targets/systemui/res/values/values.xml").getroot()
        self.assertEqual(values.find("color").text, "#FF102030")
        self.assertTrue(any(x["targetKey"] == "keyboard" for x in self.report()["omittedControls"]))

    def test_rejects_malformed_color_and_out_of_bounds_dimension(self):
        for role, bad in [("background", {"type": "color", "value": "#bad;touch /tmp/injected"}), ("quickTileRadius", {"type": "dimension", "value": 33, "unit": "dp"})]:
            with self.subTest(role=role):
                original = self.tokens[role]
                self.tokens[role] = bad
                self.save()
                result = self.run_builder()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(role, result.stderr)
                self.assertFalse(self.output.exists())
                self.tokens[role] = original

    def test_rejects_source_and_pack_path_traversal(self):
        self.manifest["variants"]["dark"] = "../outside.json"
        self.save()
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("path", result.stderr.lower())
        self.manifest["variants"]["dark"] = "tokens/dark.json"
        self.targets[0]["apkPath"] = "../outside.apk"
        self.save()
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("path", result.stderr.lower())
        self.assertFalse(self.output.exists())

    def test_rejects_changed_apk_before_generation(self):
        apk = self.inputs / self.targets[0]["apkPath"]
        apk.write_bytes(apk.read_bytes() + b"changed")
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SHA-256", result.stderr)
        self.assertFalse(self.output.exists())

    def test_rejects_binding_missing_from_actual_resource_table_even_when_omitted_variant(self):
        self.targets[1]["bindings"][-1]["name"] = "invented_resource"
        self.save()
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invented_resource", result.stderr)
        self.assertFalse(self.output.exists())

    def test_rejects_binding_with_real_name_but_wrong_resource_id(self):
        self.targets[0]["bindings"][0]["resourceId"] = "0x0106ffff"
        self.save()
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("actual resource table", result.stderr)
        self.assertFalse(self.output.exists())

    def test_required_settings_component_cannot_be_satisfied_by_framework_colors(self):
        self.manifest["components"] = [{"id": "settings.palette", "required": True}]
        self.save()
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Required component", result.stderr)
        self.assertFalse(self.output.exists())

    def test_rejects_unmatched_required_extension(self):
        self.manifest["components"] = [{"id": "extension:org.example/app.palette", "required": True}]
        self.save()
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Required component", result.stderr)
        self.assertFalse(self.output.exists())

    def test_rejects_symlink_token_input(self):
        token = self.source / "tokens/dark.json"
        outside = self.root / "outside.json"
        token.rename(outside)
        token.symlink_to(outside)
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Symlink", result.stderr)
        self.assertFalse(self.output.exists())

    def test_malformed_pack_field_is_reported_without_traceback(self):
        self.targets[0]["key"] = ["framework"]
        self.save()
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Build failed:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_huge_dimension_is_rejected_without_traceback(self):
        self.tokens["quickTileRadius"]["value"] = 10 ** 400
        self.save()
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("quickTileRadius", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_color_alpha_retains_binding_opacity_and_source_opacity(self):
        for source, expected in [("#FF07080B", "#4D07080B"), ("#8007080B", "#2707080B")]:
            with self.subTest(source=source):
                self.tokens["background"]["value"] = source
                self.targets[0]["bindings"][0]["originalAlpha"] = 77
                self.output = self.root / ("alpha-" + source[1:3])
                self.save()
                result = self.run_builder()
                self.assertEqual(result.returncode, 0, result.stderr)
                values = ET.parse(self.output / "targets/framework/res/values/values.xml").getroot()
                self.assertEqual(values.find("color").text, expected)
                replacement = self.report()["targets"][0]["replacements"][0]
                self.assertEqual(replacement["sourceValue"], source)
                self.assertEqual(replacement["originalAlpha"], 77)
                self.assertEqual(replacement["value"], expected)

    def test_invalid_original_alpha_and_alpha_on_dimension_are_rejected(self):
        for binding, alpha in [(self.targets[0]["bindings"][0], 256), (self.targets[1]["bindings"][1], 77)]:
            with self.subTest(alpha=alpha, kind=binding["type"]):
                binding["originalAlpha"] = alpha
                self.save()
                result = self.run_builder()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("originalAlpha", result.stderr)
                self.assertFalse(self.output.exists())
                del binding["originalAlpha"]

    def test_duplicate_generated_resource_qualifiers_are_rejected(self):
        self.targets[0]["bindings"].append(dict(self.targets[0]["bindings"][0]))
        self.save()
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Duplicate", result.stderr)
        self.assertFalse(self.output.exists())

    def test_archive_read_failure_does_not_publish_partial_bundle(self):
        spec = importlib.util.spec_from_file_location("theme_builder_archive_test", BUILDER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.output.mkdir()
        (self.output / "build-report.json").write_text('{"status":"compiled"}')
        broken = self.output / "values.xml"
        broken.write_text("resource source")
        original_read = Path.read_bytes

        def fail_selected_read(path):
            if path == broken:
                raise OSError("fixture packaging read failure")
            return original_read(path)

        with mock.patch.object(Path, "read_bytes", fail_selected_read):
            with self.assertRaises(OSError):
                module.archive(self.output, "theme.zip")
        self.assertFalse((self.output / "theme.zip").exists())
        self.assertFalse(any(self.output.glob("*.tmp")))

    def test_target_name_is_preserved_only_when_declared_by_measured_pack(self):
        self.targets[0]["targetName"] = "MeasuredThemeResources"
        self.save()
        result = self.run_builder()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = ET.parse(self.output / "targets/framework/AndroidManifest.xml").getroot()
        self.assertEqual(manifest.find("overlay").get(ANDROID + "targetName"), "MeasuredThemeResources")

    def test_light_tokens_are_used_only_for_light_bindings(self):
        self.manifest["variants"]["light"] = "tokens/light.json"
        (self.source / "tokens/light.json").write_text(json.dumps({"accent": {"type": "color", "value": "#FF112233"}}))
        self.save()
        result = self.run_builder()
        self.assertEqual(result.returncode, 0, result.stderr)
        values = ET.parse(self.output / "targets/systemui/res/values/values.xml").getroot()
        self.assertEqual({x.get("name"): x.text for x in values}["real_accent"], "#FF112233")

    def test_same_sources_pack_and_tools_produce_repeatable_bundle(self):
        first = self.run_builder()
        self.assertEqual(first.returncode, 0, first.stderr)
        original = (self.output / "org.example.safe-theme-theme.zip").read_bytes()
        self.output = self.root / "another-output"
        second = self.run_builder()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(original, (self.output / "org.example.safe-theme-theme.zip").read_bytes())

    def test_tool_exit_failure_never_produces_success_report(self):
        result = self.run_builder(env={"FAKE_FAIL_STAGE": "compile"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("17", result.stderr)
        self.assertEqual(self.report()["status"], "failed")
        self.assertFalse(self.report()["applied"])
        self.assertFalse((self.output / "org.example.safe-theme-theme.zip").exists())

    def test_rejects_compiled_values_that_disagree_with_generated_sources(self):
        result = self.run_builder(env={"FAKE_CORRUPT_OUTPUT": "1"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("compiled", result.stderr.lower())
        self.assertEqual(self.report()["status"], "failed")

    def test_refuses_existing_output_without_altering_it(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep")
        result = self.run_builder()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exists", result.stderr)
        self.assertEqual(sentinel.read_text(), "keep")

    def test_signed_bundle_contains_sources_pack_reports_apks_but_no_input_apks_or_key(self):
        key = self.root / "owner.p12"
        key.write_bytes(b"private owner key fixture")
        result = self.run_builder(extra=("--keystore", str(key), "--store-pass", "fixture-password"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.report()["status"], "signed")
        with zipfile.ZipFile(self.output / "org.example.safe-theme-theme.zip") as bundle:
            names = bundle.namelist()
            self.assertIn("source/manifest.json", names)
            self.assertIn("source/tokens/dark.json", names)
            self.assertIn("resource-pack.json", names)
            self.assertIn("build-report.json", names)
            self.assertTrue(any(x.endswith("overlay-signed.apk") for x in names))
            self.assertFalse(any("base.apk" in x or "owner.p12" in x or "private" in x for x in names))
            self.assertNotIn("fixture-password", bundle.read("build-report.json").decode())


if __name__ == "__main__":
    unittest.main()
