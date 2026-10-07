#!/usr/bin/env python3
"""Collect read-only design inputs from an already authorized Android device.

This is evidence collection, not an overlay builder or an apply bridge. No
resource, overlayability, or theming compatibility claim follows from a report.
"""

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import threading
import time


DEFAULT_PACKAGES = ("android", "com.android.systemui", "com.android.settings")
CANDIDATE_PACKAGES = DEFAULT_PACKAGES + (
    "com.samsung.android.dialer",
    "com.samsung.android.honeyboard",
    "com.sec.android.app.myfiles",
    "com.samsung.android.messaging",
    "com.samsung.android.app.contacts",
    "com.sec.android.app.launcher",
    "com.samsung.android.themedesigner",
    "com.samsung.android.themepark",
)
PROPERTIES = (
    "ro.build.fingerprint",
    "ro.build.version.sdk",
    "ro.build.version.release",
    "ro.build.version.security_patch",
    "ro.product.manufacturer",
    "ro.product.model",
    "ro.build.display.id",
    "ro.build.PDA",
    "ro.build.version.oneui",
)
MAX_TEXT_BYTES = 256 * 1024
APK_ROOTS = ("/system", "/system_ext", "/product", "/vendor", "/odm")
SAFE_PATH = re.compile(r"/[A-Za-z0-9_./+=@~-]+\Z")


def timestamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def bounded_text(value):
    """Keep individual command records bounded, including malformed output."""
    if value is None:
        return "", False
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= MAX_TEXT_BYTES:
        return value, False
    return encoded[:MAX_TEXT_BYTES].decode("utf-8", errors="replace"), True


def drain_pipe(pipe, captured):
    """Drain child output without retaining more than the per-stream limit."""
    try:
        while True:
            block = pipe.read(8192)
            if not block:
                break
            remaining = MAX_TEXT_BYTES - len(captured["data"])
            captured["data"].extend(block[:remaining])
            if len(block) > remaining:
                captured["truncated"] = True
    except OSError as exc:
        captured["error"] = str(exc)
    finally:
        pipe.close()


def stop_process(process):
    """Terminate only the ADB client we launched, with a bounded reap."""
    try:
        process.kill()
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=1)
        return True
    except subprocess.TimeoutExpired:
        return False


def package_version_fields(raw):
    """Discard permissions, user state, and other unrelated package dump data."""
    fields = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("versionName="):
            fields["versionName"] = stripped.partition("=")[2]
        elif stripped.startswith("versionCode="):
            for key, value in re.findall(
                r"(?:^|\s)(versionCode|minSdk|targetSdk)=([^\s]+)", stripped
            ):
                fields[key] = value
        elif stripped.startswith(("minSdk=", "targetSdk=")):
            key, _, value = stripped.partition("=")
            fields[key] = value.split()[0] if value else ""
    return fields


def validate_apk_path(raw):
    """Accept APKs in resource/app locations, never private application data."""
    if not SAFE_PATH.fullmatch(raw):
        return "Path contains unexpected characters or is not absolute."
    parts = raw.split("/")
    if any(part in ("", ".", "..") for part in parts[1:]):
        return "Path contains empty, dot, or traversal components."
    path = PurePosixPath(raw)
    if path.suffix != ".apk":
        return "Path does not end in .apk."
    # Framework resources and APKs on read-only Android partitions.
    if any(
        raw.startswith(root + "/" + area + "/")
        for root in APK_ROOTS
        for area in ("app", "priv-app", "framework", "overlay")
    ):
        return None
    # Updated system apps can live in /data/app. /data/data and /data/user
    # are deliberately excluded; package manager must supply every path.
    if raw.startswith("/data/app/") and len(path.parts) >= 4:
        return None
    # APEX may supply framework resources or APKs in app/priv-app trees.
    if (
        len(path.parts) >= 5
        and path.parts[1] == "apex"
        and path.parts[3] in ("app", "priv-app", "framework")
    ):
        return None
    return "Path is outside permitted Android APK/resource directories."


class Collector:
    def __init__(self, args, output):
        self.args = args
        self.output = output
        self.serial = None
        self.report = {
            "schemaVersion": 1,
            "generatedAt": timestamp(),
            "purpose": "Read-only One UI 9 theme design inputs",
            "compatibilityCertification": False,
            "referenceTarget": {
                "model": "SM-S948U1",
                "androidRelease": "17",
                "oneUi": "9",
                "build": "CP2A.260605.016.S948U1UEU4BZID",
                "source": "User-supplied reference; compare with collected values",
            },
            "options": {
                "packages": args.packages,
                "pullApks": args.pull_apks,
                "includeOverlayDump": args.include_overlay_dump,
                "timeoutSeconds": args.timeout,
            },
            "device": {},
            "packages": {},
            "commands": [],
            "warnings": [
                "Diagnostics and readable APKs do not prove overlay acceptance, "
                "resource coverage, or a visual match."
            ],
            "errors": [],
        }

    def warn(self, message):
        self.report["warnings"].append(message)

    def error(self, message):
        self.report["errors"].append(message)

    def run(self, command, *, device=True, version_only=False):
        argv = [self.args.adb]
        if device:
            if self.serial is None:
                raise RuntimeError("A verified device is required.")
            argv.extend(("-s", self.serial))
        argv.extend(command)
        record = {"argv": argv, "exitCode": None, "stdout": "", "stderr": ""}
        started = time.monotonic()
        stdout = ""
        process = None
        streams = {}
        readers = []
        interrupted = False
        try:
            process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for name, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
                captured = {"data": bytearray(), "truncated": False}
                streams[name] = captured
                reader = threading.Thread(target=drain_pipe, args=(pipe, captured), daemon=True)
                reader.start()
                readers.append(reader)
            try:
                record["exitCode"] = process.wait(timeout=self.args.timeout)
            except subprocess.TimeoutExpired:
                record["timedOut"] = True
                record["error"] = "Command exceeded its timeout."
                if not stop_process(process):
                    record["error"] += " ADB client did not exit after termination."
        except KeyboardInterrupt:
            interrupted = True
            record["interrupted"] = True
            record["error"] = "Command interrupted."
            if process is not None and not stop_process(process):
                record["error"] += " ADB client did not exit after termination."
        except OSError as exc:
            record["error"] = str(exc)
            if process is not None:
                stop_process(process)
        finally:
            # A descendant that keeps a pipe open must not make collection
            # wait indefinitely after the ADB client has exited.
            for reader in readers:
                reader.join(timeout=1)
            if any(reader.is_alive() for reader in readers):
                record["captureIncomplete"] = True
                record.setdefault("error", "Command output pipes remained open after exit.")
        for name, captured in streams.items():
            record[name], decoded_cut = bounded_text(bytes(captured["data"]))
            if captured["truncated"] or decoded_cut:
                record[name + "Truncated"] = True
            if captured.get("error"):
                record.setdefault("error", "Could not read command output: " + captured["error"])
        stdout = record["stdout"]
        record["durationSeconds"] = round(time.monotonic() - started, 3)
        if version_only:
            fields = package_version_fields(stdout)
            stdout = "".join(key + "=" + value + "\n" for key, value in fields.items())
            record["stdoutHandling"] = "Selected version fields only; raw package dump discarded"
        record["stdout"], selected_cut = bounded_text(stdout)
        if selected_cut:
            record["stdoutTruncated"] = True
        if record.get("stdoutTruncated") or record.get("stderrTruncated"):
            self.warn("Command output was truncated: " + " ".join(command))
        self.report["commands"].append(record)
        if interrupted:
            raise KeyboardInterrupt
        return record

    @staticmethod
    def ok(record):
        return record["exitCode"] == 0 and not record.get("error")

    def required(self, command):
        record = self.run(command)
        if not self.ok(record):
            self.error("Read-only command failed: " + " ".join(command))
        return record

    def select_device(self):
        record = self.run(["devices"], device=False)
        if not self.ok(record) or record.get("stdoutTruncated"):
            self.error("Could not obtain a complete ADB device list.")
            return False
        devices = {}
        for line in record["stdout"].splitlines():
            if not line.strip() or line.startswith("List of devices attached"):
                continue
            fields = line.split()
            if len(fields) >= 2:
                devices[fields[0]] = fields[1]
        if self.args.serial:
            if devices.get(self.args.serial) != "device":
                self.error("Requested serial is absent or is not in ADB's authorized 'device' state.")
                return False
            self.serial = self.args.serial
        else:
            authorized = [serial for serial, state in devices.items() if state == "device"]
            if len(authorized) != 1:
                self.error(
                    "Exactly one authorized device is required without --serial; found "
                    + str(len(authorized)) + ". Select one explicitly if needed."
                )
                return False
            self.serial = authorized[0]
        if any(state != "device" for state in devices.values()):
            self.warn("Other ADB entries are unauthorized, offline, or unavailable; none were accessed.")
        self.report["device"]["serial"] = self.serial
        return True

    def collect_package(self, package):
        entry = {"candidatePackage": package, "discovered": False, "apkPaths": [], "apks": []}
        self.report["packages"][package] = entry
        record = self.run(["shell", "pm", "path", package])
        if not self.ok(record):
            entry["pathQueryFailed"] = True
            self.warn("Package path unavailable (absent package or denied query): " + package)
            if record.get("error"):
                self.error("Package path command failed: " + package)
            return
        if record.get("stdoutTruncated"):
            self.error("Incomplete package paths were rejected: " + package)
            return
        paths = []
        for line in record["stdout"].splitlines():
            if not line.strip():
                continue
            if not line.startswith("package:"):
                self.warn("Unexpected pm path output was rejected for " + package)
                continue
            path = line[len("package:"):]
            problem = validate_apk_path(path)
            if problem:
                self.warn("Rejected APK path for " + package + ": " + problem)
                continue
            if path not in paths:
                paths.append(path)
        if not paths:
            self.warn("No permitted APK paths were discovered for candidate " + package)
            return
        entry["discovered"] = True
        entry["apkPaths"] = paths
        version = self.run(["shell", "dumpsys", "package", package], version_only=True)
        entry["version"] = package_version_fields(version["stdout"])
        if not self.ok(version):
            self.warn("Package version metadata unavailable: " + package)
        if self.args.pull_apks:
            for index, path in enumerate(paths):
                self.pull_apk(package, index, path, entry)

    def pull_apk(self, package, index, remote, entry):
        package_dir = self.output / "apks" / package
        package_dir.mkdir(parents=True, exist_ok=True)
        local = package_dir / (str(index).zfill(2) + "-" + PurePosixPath(remote).name)
        item = {"remotePath": remote, "localPath": str(local.relative_to(self.output))}
        entry["apks"].append(item)
        if os.path.lexists(local):
            item["error"] = "Refusing to overwrite an existing local file."
            self.error(item["error"])
            return
        try:
            record = self.run(["pull", remote, str(local)])
        except KeyboardInterrupt:
            item["error"] = "APK copy interrupted; partial bytes were discarded."
            if local.is_file() and not local.is_symlink():
                local.unlink()
            raise
        if not self.ok(record):
            item["error"] = "APK copy failed; no elevated-access retry was attempted."
            self.error("APK copy failed: " + package + " " + remote)
            # An interrupted adb pull can leave incomplete bytes; never label
            # those bytes a captured APK or include a misleading hash.
            if local.is_file() and not local.is_symlink():
                local.unlink()
            return
        if local.is_symlink() or not local.is_file():
            item["error"] = "ADB did not produce a regular local APK file."
            self.error(item["error"])
            return
        digest = hashlib.sha256()
        with local.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        item["sizeBytes"] = local.stat().st_size
        item["sha256"] = digest.hexdigest()

    def collect(self):
        if not self.select_device():
            return
        self.required(["shell", "id"])
        properties = self.report["device"]["properties"] = {}
        for name in PROPERTIES:
            record = self.required(["shell", "getprop", name])
            properties[name] = record["stdout"].strip() if self.ok(record) else None
            if self.ok(record) and not properties[name]:
                self.warn("Device property is empty or unsupported: " + name)
        if properties.get("ro.product.model") != "SM-S948U1":
            self.warn("Collected model differs from the user-supplied SM-S948U1 reference.")
        if properties.get("ro.build.version.release") != "17":
            self.warn("Collected Android release differs from the user-supplied Android 17 reference.")
        if properties.get("ro.build.display.id") != "CP2A.260605.016.S948U1UEU4BZID":
            self.warn("Collected display build differs from the user-supplied reference; map this actual build.")
        self.required(["shell", "cmd", "overlay", "help"])
        self.required(["shell", "cmd", "overlay", "list"])
        if self.args.include_overlay_dump:
            self.required(["shell", "dumpsys", "overlay"])
        for package in self.args.packages:
            self.collect_package(package)

    def save(self):
        self.report["completedAt"] = timestamp()
        self.report["status"] = "partial" if self.report["errors"] else "collected_with_warnings"
        report_file = self.output / "report.json"
        with report_file.open("x", encoding="utf-8") as stream:
            json.dump(self.report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        return report_file


def timeout_seconds(value):
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("timeout must be a number") from None
    if not math.isfinite(number) or not 0 < number <= 300:
        raise argparse.ArgumentTypeError("timeout must be greater than 0 and at most 300 seconds")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Collect read-only One UI 9 design evidence using laptop Android Platform Tools. "
        "This does not install, enable, authorize, pair, or certify any overlay.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--adb", default="adb", help="ADB executable path (one executable, not a shell command)")
    parser.add_argument("--serial", help="Explicit already-authorized ADB serial; otherwise require one authorized device")
    parser.add_argument("--output", type=Path, help="New output folder; existing paths are refused")
    parser.add_argument("--timeout", type=timeout_seconds, default=20.0, help="Timeout per ADB command, in seconds")
    parser.add_argument(
        "--packages", nargs="+", choices=CANDIDATE_PACKAGES, default=list(DEFAULT_PACKAGES),
        metavar="PACKAGE", help="Candidate packages to query; replaces the default list",
    )
    parser.add_argument("--pull-apks", action="store_true", help="Copy only pm-discovered APKs already readable by ADB")
    parser.add_argument("--include-overlay-dump", action="store_true", help="Also capture read-only dumpsys overlay details")
    args = parser.parse_args(argv)
    args.packages = list(dict.fromkeys(args.packages))
    if args.output is None:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        args.output = Path("oneui9-inputs-" + stamp)
    return args


def main(argv=None):
    args = parse_args(argv)
    output = args.output.absolute()
    if os.path.lexists(output):
        print("Error: output path already exists; choose a new folder: " + str(output), file=sys.stderr)
        return 2
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print("Error: cannot create output folder: " + str(exc), file=sys.stderr)
        return 2
    collector = Collector(args, output)
    try:
        collector.collect()
    except (OSError, RuntimeError, KeyboardInterrupt) as exc:
        collector.error("Collection interrupted: " + (str(exc) or type(exc).__name__))
    try:
        report_file = collector.save()
    except OSError as exc:
        print("Error: cannot write report: " + str(exc), file=sys.stderr)
        return 2
    print("Report: " + str(report_file))
    print("Warnings: " + str(len(collector.report["warnings"])) + "; errors: " + str(len(collector.report["errors"])))
    print("Design evidence only; overlay compatibility is unverified.")
    return 1 if collector.report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
