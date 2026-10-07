"""Read-only collector regressions with isolated ADB command fixtures."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


COLLECTOR = Path(__file__).resolve().parents[1] / "tools/collect_oneui9_inputs.py"
MAX_CAPTURE_BYTES = 256 * 1024

# Captured Android 17 help structure, including its terminal command block.
OVERLAY_HELP = r"""Overlay manager (overlay) commands:
  help
    Print this help text.
  dump [--verbose] [--user USER_ID] [[FIELD] PACKAGE[:NAME]]
    Print debugging information about the overlay manager.
    With optional parameters PACKAGE and NAME, limit output to the specified
    overlay or target. With optional parameter FIELD, limit output to
    the corresponding SettingsItem field. Field names are all lower case
    and omit the m prefix, i.e. 'userid' for SettingsItem.mUserId.
  list [--user USER_ID] [PACKAGE[:NAME]]
    Print information about target and overlay packages.
    Overlay packages are printed in priority order. With optional
    parameters PACKAGE and NAME, limit output to the specified overlay or
    target.
  enable [--user USER_ID] PACKAGE[:NAME]
    Enable overlay within or owned by PACKAGE with optional unique NAME.
  disable [--user USER_ID] PACKAGE[:NAME]
    Disable overlay within or owned by PACKAGE with optional unique NAME.
  enable-exclusive [--user USER_ID] [--category] PACKAGE
    Enable overlay within or owned by PACKAGE and disable all other overlays
    for its target package. If the --category option is given, only disables
    other overlays in the same category.
  set-priority [--user USER_ID] PACKAGE PARENT|lowest|highest
    Change the priority of the overlay to be just higher than
    the priority of PARENT If PARENT is the special keyword
    'lowest', change priority of PACKAGE to the lowest priority.
    If PARENT is the special keyword 'highest', change priority of
    PACKAGE to the highest priority.
  lookup [--user USER_ID] [--verbose] PACKAGE-TO-LOAD PACKAGE:TYPE/NAME
    Load a package and print the value of a given resource
    applying the current configuration and enabled overlays.
    For a more fine-grained alternative, use 'idmap2 lookup'.
  fabricate [--target-name OVERLAYABLE] --target PACKAGE
            --name NAME [--file FILE] 
            PACKAGE:TYPE/NAME ENCODED-TYPE-ID|TYPE-NAME ENCODED-VALUE
    Create an overlay from a single resource. Caller must be root. Example:
      fabricate --target android --name LighterGray \
                android:color/lighter_gray 0x1c 0xffeeeeee
  partition-order
    Print the partition order from overlay config and how this order
    got established, by default or by /product/overlay/partition_order.xml
"""

FAKE_ADB = r'''#!/usr/bin/env python3
import json, os, sys, time
a = sys.argv[1:]
mode = os.environ.get("COLLECTOR_FIXTURE_MODE", "normal")
help_text = os.environ["COLLECTOR_FIXTURE_HELP"]
with open(os.environ["COLLECTOR_FIXTURE_LOG"], "a") as log:
    log.write(json.dumps(a) + "\n")
if a == ["devices"]:
    print("List of devices attached\nfixture-phone\tdevice")
    sys.exit()
assert a[:2] == ["-s", "fixture-phone"], a
a = a[2:]
if a == ["shell", "id"]:
    print("uid=2000(shell) gid=2000(shell)")
elif a[:2] == ["shell", "getprop"] and len(a) == 3:
    values = {
        "ro.product.model": "SM-S948U1", "ro.product.manufacturer": "samsung",
        "ro.build.version.release": "17", "ro.build.version.sdk": "37",
        "ro.build.display.id": "CP2A.260605.016.S948U1UEU4BZID",
        "ro.build.version.oneui": "90000",
    }
    print(values.get(a[2], "fixture"))
elif a == ["shell", "cmd", "overlay", "help"]:
    if mode == "help-prefix":
        print(help_text.split("  partition-order")[0], end="")
    else:
        print(help_text, end="")
    if mode == "help-error":
        print("Permission denied: overlay help unavailable", file=sys.stderr)
    if mode == "help-stdout-error":
        print("java.lang.SecurityException: Permission denied")
    if mode == "help-timeout":
        sys.stdout.flush()
        time.sleep(1)
    if mode == "help-exit1": sys.exit(1)
    if mode == "help-exit7": sys.exit(7)
    if mode.startswith("help-"): sys.exit(255)
elif a == ["shell", "cmd", "overlay", "list"]:
    if mode == "list-help":
        print(help_text, end="")
        sys.exit(255)
    print("android\n[x] fixture.overlay")
elif a[:3] == ["shell", "pm", "path"] and len(a) == 4:
    print("package:/system/priv-app/Fixture/base.apk")
elif a[:3] == ["shell", "dumpsys", "package"] and len(a) == 4:
    if mode in ("late-metadata", "metadata-timeout"):
        # One huge unrelated line and many ordinary lines both precede fields.
        sys.stdout.write("DO_NOT_RETAIN_PRIVATE_STATE" * 30000 + "\n")
        sys.stdout.write("resolver DO_NOT_RETAIN_PRIVATE_STATE\n" * 12000)
    if mode == "long-version":
        sys.stdout.write("  versionName=" + "v" * 1000000 + "\n")
        sys.stdout.write("  versionCode=37 minSdk=37 targetSdk=37\n")
    else:
        # CRLF, a line crossing read-block boundaries, and no final newline.
        sys.stdout.write("  versionCode=37 minSdk=37 targetSdk=37\r\n")
        sys.stdout.write("  versionName=17 fixture build")
    if mode == "metadata-timeout":
        sys.stdout.flush()
        sys.stderr.write("stderr-noise" * 50000)
        sys.stderr.flush()
        time.sleep(1)
else:
    raise AssertionError("Unexpected or mutating command: " + repr(a))
'''


class OneUi9InputCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.adb = self.root / "adb-fixture"
        self.adb.write_text(FAKE_ADB)
        self.adb.chmod(0o755)
        self.output = self.root / "output"
        self.log = self.root / "commands.jsonl"

    def collect(self, mode="normal", extra=()):
        env = {
            **os.environ,
            "COLLECTOR_FIXTURE_MODE": mode,
            "COLLECTOR_FIXTURE_HELP": OVERLAY_HELP,
            "COLLECTOR_FIXTURE_LOG": str(self.log),
        }
        result = subprocess.run(
            [sys.executable, str(COLLECTOR), "--adb", str(self.adb),
             "--output", str(self.output), *extra],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, timeout=15,
        )
        report = json.loads((self.output / "report.json").read_text())
        return result, report

    @staticmethod
    def help_record(report):
        return next(x for x in report["commands"] if x["argv"][-4:] == ["shell", "cmd", "overlay", "help"])

    def test_recovers_all_version_fields_after_oversized_unrelated_dump(self):
        result, report = self.collect("late-metadata")
        self.assertEqual(result.returncode, 0, result.stderr)
        for entry in report["packages"].values():
            self.assertEqual(entry["version"], {
                "versionCode": "37", "minSdk": "37", "targetSdk": "37",
                "versionName": "17 fixture build",
            })
        self.assertNotIn("DO_NOT_RETAIN_PRIVATE_STATE", json.dumps(report))
        for record in report["commands"]:
            if "stdoutHandling" in record:
                self.assertLess(len(record["stdout"].encode()), 1024)
                self.assertNotIn("stdoutTruncated", record)

    def test_bounds_a_large_version_field_without_losing_later_fields(self):
        result, report = self.collect("long-version")
        self.assertEqual(result.returncode, 0, result.stderr)
        for entry in report["packages"].values():
            self.assertEqual(entry["version"].get("versionCode"), "37")
            self.assertEqual(entry["version"].get("targetSdk"), "37")
            self.assertLessEqual(len(entry["version"].get("versionName", "").encode()), 4096)
        records = [x for x in report["commands"] if "stdoutHandling" in x]
        self.assertTrue(all(x.get("versionFieldsTruncated") for x in records))
        self.assertTrue(any("version" in x.lower() and "truncated" in x.lower() for x in report["warnings"]))

    def test_complete_help_exit_255_is_informational_and_keeps_real_exit_code(self):
        result, report = self.collect("help-valid")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["errors"], [])
        record = self.help_record(report)
        self.assertEqual(record["exitCode"], 255)
        self.assertEqual(record["stdout"], OVERLAY_HELP)
        self.assertEqual(record["classification"], "informational-help")

    def test_help_with_stderr_or_stdout_error_remains_a_failure(self):
        for mode in ("help-error", "help-stdout-error", "help-prefix", "help-exit1", "help-exit7"):
            with self.subTest(mode=mode):
                self.output = self.root / mode
                result, report = self.collect(mode)
                self.assertEqual(result.returncode, 1)
                self.assertTrue(report["errors"])
                self.assertNotIn("classification", self.help_record(report))

    def test_valid_help_from_another_command_does_not_hide_nonzero_exit(self):
        result, report = self.collect("list-help")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(any("overlay list" in error for error in report["errors"]))

    def test_valid_help_cannot_hide_a_timeout(self):
        result, report = self.collect("help-timeout", ("--timeout", "0.2"))
        self.assertEqual(result.returncode, 1)
        record = self.help_record(report)
        self.assertTrue(record["timedOut"])
        self.assertNotIn("classification", record)

    def test_metadata_timeout_still_records_failure_and_bounds_noisy_stderr(self):
        result, report = self.collect("metadata-timeout", ("--timeout", "0.2"))
        records = [x for x in report["commands"] if "stdoutHandling" in x]
        self.assertEqual(len(records), 3)
        self.assertTrue(all(x.get("timedOut") and x.get("error") for x in records))
        self.assertTrue(all(len(x["stderr"].encode()) <= MAX_CAPTURE_BYTES for x in records))
        self.assertNotIn("DO_NOT_RETAIN_PRIVATE_STATE", json.dumps(report))
        self.assertTrue(all(entry["version"].get("versionCode") == "37" for entry in report["packages"].values()))


if __name__ == "__main__":
    unittest.main()
