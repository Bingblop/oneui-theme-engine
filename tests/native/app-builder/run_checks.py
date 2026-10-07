#!/usr/bin/env python3
"""Opt-in real Android-tool integration checks; all fixtures live in temp folders."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
import zipfile


BUILDER = None
CONFIG = None


class AppBuilderChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="oneui-studio-builder-check-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        for name in ("src/org/bingblop/oneui/studio", "res/values", "assets/theme-source"):
            (self.source / name).mkdir(parents=True)
        (self.source / "AndroidManifest.xml").write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="org.bingblop.oneui.studio" android:versionCode="1" android:versionName="0.0.0"><uses-sdk android:minSdkVersion="37" android:targetSdkVersion="37"/><application android:label="@string/app_name" android:theme="@android:style/Theme.Material.NoActionBar"><activity android:name=".MainActivity" android:exported="true"><intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter></activity></application></manifest>''', encoding="utf-8")
        (self.source / "src/org/bingblop/oneui/studio/MainActivity.java").write_text('''package org.bingblop.oneui.studio;
import android.app.Activity; import android.os.Bundle; import android.widget.TextView;
public final class MainActivity extends Activity {
 public void onCreate(Bundle saved) { super.onCreate(saved); TextView view=new TextView(this);
  view.setText(R.string.app_name); view.setOnClickListener(v -> view.setText(R.string.app_name)); setContentView(view); }
}''', encoding="utf-8")
        (self.source / "res/values/strings.xml").write_text('<resources><string name="app_name">Compiler fixture</string></resources>', encoding="utf-8")
        (self.source / "assets/theme-source/demo.txt").write_text("compiler fixture asset\n", encoding="utf-8")
        self.args = argparse.Namespace(**{name: getattr(CONFIG, name) for name in ("android_jar", "lambda_stubs", "aapt2", "javac", "java", "d8", "zipalign", "apksigner", "tool_provenance", "keystore", "key_alias", "store_pass")}, source=str(self.source), output=str(self.root / "output"))

    def report(self):
        return json.loads((Path(self.args.output) / "build-report.json").read_text(encoding="utf-8"))

    def assert_no_final_apk(self):
        self.assertFalse((Path(self.args.output) / "oneui-studio.apk").exists())

    def test_signed_reproducible_apk_and_asset_contents(self):
        first = BUILDER.build(self.args)
        apk = (self.root / "output/oneui-studio.apk").read_bytes()
        self.args.output = str(self.root / "second")
        second = BUILDER.build(self.args)
        self.assertEqual(apk, (self.root / "second/oneui-studio.apk").read_bytes(), "Use the pinned RSA development key for signed-byte reproducibility")
        self.assertEqual(first["apk"]["sha256"], second["apk"]["sha256"])
        self.assertTrue(first["signatureVerified"])
        self.assertTrue(first["resourceStorageVerified"])
        self.assertTrue(first["toolProvenance"]["verified"])
        self.assertFalse(first["deviceRuntimeVerified"])
        with zipfile.ZipFile(self.root / "output/oneui-studio.apk") as archive:
            self.assertEqual(archive.getinfo("resources.arsc").compress_type, zipfile.ZIP_STORED)
            self.assertEqual(archive.read("assets/theme-source/demo.txt"), b"compiler fixture asset\n")
            self.assertTrue(archive.read("classes.dex").startswith(b"dex\n"))

    def test_existing_output_is_refused(self):
        output = Path(self.args.output)
        output.mkdir()
        (output / "sentinel").write_text("retain", encoding="utf-8")
        with self.assertRaisesRegex(BUILDER.BuildError, "already exists"):
            BUILDER.build(self.args)
        self.assertEqual((output / "sentinel").read_text(encoding="utf-8"), "retain")

    def test_wrong_manifest_package_or_api_rejected_before_output(self):
        manifest = self.source / "AndroidManifest.xml"
        original = manifest.read_text(encoding="utf-8")
        for bad in (original.replace("org.bingblop.oneui.studio", "org.example.wrong"), original.replace('minSdkVersion="37"', 'minSdkVersion="36"')):
            with self.subTest(manifest=bad):
                manifest.write_text(bad, encoding="utf-8")
                with self.assertRaises(BUILDER.BuildError):
                    BUILDER.build(self.args)
                self.assertFalse(Path(self.args.output).exists())

    def test_changed_tool_provenance_rejected_before_output(self):
        data = json.loads(Path(self.args.tool_provenance).read_text(encoding="utf-8"))
        data["installed_tools"]["android_jar"]["sha256"] = "0" * 64
        path = self.root / "bad-provenance.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.args.tool_provenance = str(path)
        with self.assertRaisesRegex(BUILDER.BuildError, "SHA-256 mismatch"):
            BUILDER.build(self.args)
        self.assertFalse(Path(self.args.output).exists())

    def test_symlinked_asset_rejected_before_output(self):
        (self.source / "assets/link.txt").symlink_to(self.root / "outside")
        with self.assertRaisesRegex(BUILDER.BuildError, "Symlinked"):
            BUILDER.build(self.args)
        self.assertFalse(Path(self.args.output).exists())

    def test_keystore_inside_source_rejected_before_output(self):
        key = self.source / "secret.jks"
        shutil.copyfile(self.args.keystore, key)
        self.args.keystore = str(key)
        with self.assertRaisesRegex(BUILDER.BuildError, "outside"):
            BUILDER.build(self.args)
        self.assertFalse(Path(self.args.output).exists())

    def test_javac_rejects_host_only_java_api_without_publishing_apk(self):
        (self.source / "src/org/bingblop/oneui/studio/MainActivity.java").write_text("package org.bingblop.oneui.studio; public class MainActivity { java.awt.Color value; }", encoding="utf-8")
        with self.assertRaisesRegex(BUILDER.BuildError, "javac failed"):
            BUILDER.build(self.args)
        self.assertEqual(self.report()["status"], "failed")
        self.assert_no_final_apk()

    def test_tool_failure_has_failed_report_without_apk(self):
        wrapper = self.root / "aapt2"
        wrapper.write_text("#!/usr/bin/env python3\nimport os,sys\nif sys.argv[1]=='compile': print('stage rejected',file=sys.stderr);sys.exit(17)\nos.execv(" + repr(str(Path(self.args.aapt2).resolve())) + ",['aapt2']+sys.argv[1:])\n", encoding="utf-8")
        wrapper.chmod(0o755)
        self.args.aapt2 = str(wrapper)
        self.args.tool_provenance = None
        with self.assertRaisesRegex(BUILDER.BuildError, "exit 17"):
            BUILDER.build(self.args)
        self.assertEqual(self.report()["status"], "failed")
        self.assert_no_final_apk()

    def test_new_source_added_during_build_rejected(self):
        original = BUILDER.run

        def execute(argv, env, label):
            result = original(argv, env, label)
            if label == "D8":
                (self.source / "src/org/bingblop/oneui/studio/Added.java").write_text("package org.bingblop.oneui.studio; class Added {}", encoding="utf-8")
            return result

        with mock.patch.object(BUILDER, "run", execute):
            with self.assertRaisesRegex(BUILDER.BuildError, "input changed"):
                BUILDER.build(self.args)
        self.assert_no_final_apk()
        self.assertEqual(self.report()["status"], "failed")

    def test_success_report_write_failure_removes_final_apk(self):
        original = BUILDER.json_write

        def write(path, data):
            if data.get("status") == "succeeded":
                raise OSError("fixture report publication failure")
            return original(path, data)

        with mock.patch.object(BUILDER, "json_write", write):
            with self.assertRaisesRegex(BUILDER.BuildError, "publication failure"):
                BUILDER.build(self.args)
        self.assert_no_final_apk()
        self.assertEqual(self.report()["status"], "failed")

    def test_explicit_jdk_wins_over_inherited_path(self):
        bad = self.root / "badbin"
        bad.mkdir()
        fake = bad / "java"
        fake.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
        fake.chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": str(bad) + os.pathsep + os.environ.get("PATH", "")}):
            result = BUILDER.build(self.args)
        self.assertEqual(result["status"], "succeeded")

    def test_old_d8_api37_warning_rejected_without_final_apk(self):
        if not CONFIG.legacy_d8:
            self.skipTest("Optional --legacy-d8 path not supplied")
        self.args.d8 = CONFIG.legacy_d8
        self.args.tool_provenance = None
        with self.assertRaisesRegex(BUILDER.BuildError, "does not support API 37"):
            BUILDER.build(self.args)
        self.assert_no_final_apk()
        self.assertEqual(self.report()["status"], "failed")


def main():
    global BUILDER, CONFIG
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--builder", default=str(Path(__file__).resolve().parents[3] / "tools/build_oneui9_studio_app.py"))
    for name in ("android-jar", "lambda-stubs", "aapt2", "javac", "java", "d8", "zipalign", "apksigner", "tool-provenance", "keystore"):
        value = os.environ.get("STUDIO_" + name.replace("-", "_").upper())
        parser.add_argument("--" + name, default=value, required=value is None, help="Explicit local path (or STUDIO_" + name.replace("-", "_").upper() + ")")
    parser.add_argument("--key-alias", default=os.environ.get("STUDIO_KEY_ALIAS", "oneui9dev"))
    parser.add_argument("--store-pass", default=os.environ.get("STUDIO_STORE_PASS", "android"))
    parser.add_argument("--legacy-d8", default=os.environ.get("STUDIO_LEGACY_D8"), help="Optional old Build Tools 37 D8 for the API37-warning regression")
    CONFIG = parser.parse_args()
    spec = importlib.util.spec_from_file_location("studio_app_builder_under_test", CONFIG.builder)
    if not spec or not spec.loader:
        parser.error("Cannot load builder")
    BUILDER = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(BUILDER)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AppBuilderChecks))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
