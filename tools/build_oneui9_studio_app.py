#!/usr/bin/env python3
"""Compile and developer-sign the native Studio app using explicit offline tools.

No SDK downloads, package installation, or device operations occur here.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile


PACKAGE = "org.bingblop.oneui.studio"
API = 37
ANDROID = "{http://schemas.android.com/apk/res/android}"


class BuildError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise BuildError(message)


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def json_write(path, value):
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def local_file(value, label, executable=False):
    path = Path(value).expanduser().resolve()
    require(path.is_file(), f"Missing local {label}: {path}")
    require(not executable or os.access(path, os.X_OK), f"{label} is not executable: {path}")
    return path


def tree_files(root):
    require(root.is_dir() and not root.is_symlink(), f"Missing or symlinked input folder: {root}")
    files = []
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), f"Symlinked source input: {path}")
        require(path.is_dir() or path.is_file(), f"Unsupported source input: {path}")
        if path.is_file():
            require(all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) and part not in {".", ".."} for part in path.relative_to(root).parts), f"Unsupported input filename: {path}")
            files.append(path)
    return files


def source_inputs(source):
    manifest = source / "AndroidManifest.xml"
    require(manifest.is_file() and not manifest.is_symlink(), "Missing or symlinked AndroidManifest.xml")
    try:
        tree = ET.parse(manifest).getroot()
    except (OSError, ET.ParseError) as exc:
        raise BuildError(f"Cannot parse AndroidManifest.xml: {exc}") from exc
    require(tree.tag == "manifest" and tree.get("package") == PACKAGE, f"Manifest package must be {PACKAGE}")
    sdk = tree.find("uses-sdk")
    require(sdk is not None and sdk.get(ANDROID + "minSdkVersion") == str(API) and sdk.get(ANDROID + "targetSdkVersion") == str(API), "Manifest must explicitly declare minSdkVersion=37 and targetSdkVersion=37")
    application = tree.find("application")
    require(application is not None and application.get(ANDROID + "hasCode", "true") != "false", "Native app must declare an application with code")
    java = tree_files(source / "src")
    require(java and all(path.suffix == ".java" for path in java), "src must contain Java source files only")
    resources = tree_files(source / "res")
    require(resources, "res must contain Android resources")
    assets = tree_files(source / "assets") if (source / "assets").exists() else []
    files = [manifest] + java + resources + assets
    return java, files


def run(argv, env, label):
    try:
        result = subprocess.run([str(arg) for arg in argv], env=env, text=True, capture_output=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BuildError(f"{label} could not run: {exc}") from exc
    require(result.returncode == 0, f"{label} failed (exit {result.returncode}):\n{(result.stderr or result.stdout)[-12000:]}")
    return (result.stdout + result.stderr).strip()


def zip_entries(path):
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            require(len(names) == len(set(names)), f"Duplicate archive entries: {path.name}")
            require(archive.testzip() is None, f"Corrupt archive entries: {path.name}")
            return {name: archive.read(name) for name in names if not name.endswith("/")}
    except (OSError, zipfile.BadZipFile) as exc:
        raise BuildError(f"Cannot read archive {path.name}: {exc}") from exc


def deterministic_zip(path, entries):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            require(not name.startswith("/") and ".." not in name.split("/"), f"Escaping archive entry: {name}")
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED if name == "resources.arsc" else zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compress_type=info.compress_type, compresslevel=9)


def verify_resource_storage(apk):
    # Android 11+ rejects compressed or misaligned resource tables.
    with zipfile.ZipFile(apk) as archive:
        require("resources.arsc" in archive.namelist(), "Signed APK is missing resources.arsc")
        resource = archive.getinfo("resources.arsc")
        require(resource.compress_type == zipfile.ZIP_STORED, "resources.arsc must be uncompressed")
    with apk.open("rb") as handle:
        handle.seek(resource.header_offset)
        header = handle.read(30)
    require(header[:4] == b"PK\x03\x04" and len(header) == 30, "Invalid resources.arsc ZIP header")
    name_length, extra_length = struct.unpack("<HH", header[26:30])
    require((resource.header_offset + 30 + name_length + extra_length) % 4 == 0, "resources.arsc must be aligned to four bytes")


def tool_records(tools, provenance):
    records = {name: {"path": str(path), "sha256": digest(path)} for name, path in tools.items()}
    for name, path in (("d8_jar", tools["d8"].parent / "lib/d8.jar"), ("apksigner_jar", tools["apksigner"].parent / "lib/apksigner.jar"), ("java_modules", tools["java"].parent.parent / "lib/modules")):
        require(path.is_file(), f"Missing tool companion: {path}")
        records[name] = {"path": str(path), "sha256": digest(path)}
    if provenance:
        try:
            evidence = json.loads(provenance.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise BuildError(f"Cannot read tool provenance: {exc}") from exc
        require(isinstance(evidence, dict) and isinstance(evidence.get("installed_tools"), dict), "Tool provenance must contain installed_tools")
        aliases = {"d8": "d8_script", "apksigner": "apksigner_script"}
        for name, record in records.items():
            key = aliases.get(name, name)
            expected = evidence["installed_tools"].get(key)
            require(isinstance(expected, dict) and expected.get("sha256") == record["sha256"], f"Tool provenance SHA-256 mismatch or missing evidence: {key}")
        return records, {"sha256": digest(provenance), "verified": True, "archives": {name: evidence[name] for name in ("build_tools", "maven_aapt2", "maven_r8", "sdk_platform", "jdk_packages") if name in evidence}}
    return records, {"verified": False, "reason": "No local provenance file supplied; actual tool hashes are recorded."}


def build(args):
    source = Path(args.source).expanduser()
    require(not source.is_symlink(), "Source folder must not be a symlink")
    source = source.resolve()
    output = Path(args.output).expanduser()
    require(not output.exists() and not output.is_symlink(), f"Output already exists: {output}")
    output = output.resolve()
    require(not output.is_relative_to(source), "Output must be outside the app source folder")
    java_sources, inputs = source_inputs(source)
    tools = {name: local_file(getattr(args, name), name, name not in {"android_jar", "lambda_stubs"}) for name in ("aapt2", "javac", "java", "d8", "zipalign", "apksigner", "android_jar", "lambda_stubs")}
    require(tools["javac"].parent == tools["java"].parent, "javac and java must come from the same local JDK")
    keystore = local_file(args.keystore, "developer keystore")
    require(not keystore.is_relative_to(source) and not keystore.is_relative_to(output), "Keep the developer keystore outside app sources and output")
    require(re.fullmatch(r"[A-Za-z0-9_.-]+", args.key_alias), "Invalid developer key alias")
    provenance_path = local_file(args.tool_provenance, "tool provenance") if args.tool_provenance else None
    tool_info, provenance = tool_records(tools, provenance_path)
    # A full platform stub jar includes Java core classes as well as Android APIs.
    stub_entries = zip_entries(tools["android_jar"])
    require({"android/app/Activity.class", "java/lang/Object.class"} <= set(stub_entries), "android.jar must contain official Android and Java API stubs")
    env = dict(os.environ)
    for name in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
        env.pop(name, None)
    env["JAVA_HOME"] = str(tools["java"].parent.parent)
    env["PATH"] = str(tools["java"].parent) + os.pathsep + env.get("PATH", "")
    env["ONEUI9_STUDIO_STORE_PASS"] = args.store_pass
    report = {"format": "oneui-studio.app-build/1", "status": "building", "package": PACKAGE, "androidApiLevel": API, "minSdkVersion": API, "targetSdkVersion": API, "javaSourceLevel": 8, "javaBytecodeLevel": 8, "installed": False, "deviceRuntimeVerified": False, "toolProvenance": provenance, "tools": tool_info, "inputs": {str(path.relative_to(source)): digest(path) for path in sorted(inputs)}}
    for name, version_args in (("aapt2", ["version"]), ("javac", ["-version"]), ("java", ["-version"]), ("d8", ["--version"]), ("apksigner", ["version"])):
        report["tools"][name]["version"] = run([tools[name]] + version_args, env, f"{name} version")
    output.mkdir(parents=True)
    json_write(output / "build-report.json", report)
    work = output / "intermediates"
    work.mkdir()
    try:
        generated, classes, dex = (work / name for name in ("generated", "classes", "dex"))
        for folder in (generated, classes, dex):
            folder.mkdir()
        compiled, resources_apk = work / "compiled-resources.zip", work / "resources.apk"
        run([tools["aapt2"], "compile", "--dir", source / "res", "-o", compiled], env, "aapt2 compile")
        link = [tools["aapt2"], "link", "-o", resources_apk, "--manifest", source / "AndroidManifest.xml", "-I", tools["android_jar"], "--java", generated, "--min-sdk-version", str(API), "--target-sdk-version", str(API), "--no-auto-version"]
        if (source / "assets").is_dir():
            link += ["-A", source / "assets"]
        run(link + [compiled], env, "aapt2 link")
        generated_java = sorted(generated.rglob("*.java"))
        require(generated_java, "aapt2 did not generate R.java")
        bootclasspath = os.pathsep.join(str(tools[name]) for name in ("android_jar", "lambda_stubs"))
        report["javacDiagnostics"] = run([tools["javac"], "-encoding", "UTF-8", "-source", "8", "-target", "8", "-bootclasspath", bootclasspath, "-classpath", tools["android_jar"], "-g:none", "-d", classes] + java_sources + generated_java, env, "javac")
        class_files = sorted(classes.rglob("*.class"))
        require(class_files, "javac produced no class files")
        classes_jar = work / "classes.jar"
        deterministic_zip(classes_jar, {str(path.relative_to(classes)): path.read_bytes() for path in class_files})
        report["d8Diagnostics"] = run([tools["d8"], "--release", "--min-api", str(API), "--lib", tools["android_jar"], "--output", dex, classes_jar], env, "D8")
        require(not re.search(r"API level(?: of)?\s+37\s+is\s+not supported", report["d8Diagnostics"], re.I), "Selected D8 does not support API 37; use a newer official R8/D8 artifact")
        dex_files = sorted(dex.glob("classes*.dex"))
        require(dex_files and dex_files[0].name == "classes.dex" and all(re.fullmatch(r"classes(?:[2-9]|[1-9][0-9]+)?\.dex", path.name) for path in dex_files), "D8 produced no valid classes.dex files")
        for path in dex_files:
            require(path.read_bytes()[:8].startswith(b"dex\n") and path.stat().st_size > 112, f"D8 produced an invalid dex file: {path.name}")
        entries = zip_entries(resources_apk)
        require({"AndroidManifest.xml", "resources.arsc"} <= set(entries), "aapt2 APK is missing manifest or resources")
        require(not any(name.startswith("META-INF/") or re.fullmatch(r"classes.*\.dex", name) for name in entries), "Unexpected signatures or dex files in resource APK")
        entries.update({path.name: path.read_bytes() for path in dex_files})
        unsigned, aligned, signed = (work / name for name in ("app-unsigned.apk", "app-aligned.apk", "app-signed.apk"))
        deterministic_zip(unsigned, entries)
        run([tools["zipalign"], "-f", "4", unsigned, aligned], env, "zipalign")
        run([tools["apksigner"], "sign", "--ks", keystore, "--ks-key-alias", args.key_alias, "--ks-pass", "env:ONEUI9_STUDIO_STORE_PASS", "--key-pass", "env:ONEUI9_STUDIO_STORE_PASS", "--min-sdk-version", str(API), "--v1-signing-enabled", "false", "--v2-signing-enabled", "true", "--v3-signing-enabled", "true", "--v4-signing-enabled", "false", "--out", signed, aligned], env, "developer APK signing")
        verification = run([tools["apksigner"], "verify", "--verbose", "--print-certs", signed], env, "APK signature verification")
        run([tools["zipalign"], "-c", "4", signed], env, "signed APK alignment check")
        verify_resource_storage(signed)
        badging = run([tools["aapt2"], "dump", "badging", signed], env, "APK manifest verification")
        require(re.search(r"^package: name='" + re.escape(PACKAGE) + "'.*compileSdkVersion='37'", badging, re.M) and re.search(r"^(?:minSdkVersion|sdkVersion):'37'$", badging, re.M) and re.search(r"^targetSdkVersion:'37'$", badging, re.M), "Compiled APK package/compileSdk/minSdk/targetSdk mismatch")
        signed_entries = zip_entries(signed)
        require(all(signed_entries.get(path.name) == path.read_bytes() for path in dex_files), "Signed APK dex payload mismatch")
        require(all(signed_entries.get("assets/" + str(path.relative_to(source / "assets"))) == path.read_bytes() for path in inputs if path.is_relative_to(source / "assets")), "Signed APK asset payload mismatch")
        _, current_inputs = source_inputs(source)
        require({str(path.relative_to(source)): digest(path) for path in current_inputs} == report["inputs"], "App input changed during build; retry with a stable source snapshot")
        report.update({"status": "succeeded", "developerSigned": True, "signatureVerified": True, "manifestVerified": True, "resourceStorageVerified": True, "dexFiles": {path.name: digest(path) for path in dex_files}, "signingKeyAlias": args.key_alias, "apk": {"path": "oneui-studio.apk", "sha256": digest(signed), "sizeBytes": signed.stat().st_size}})
        (output / "signature-verification.txt").write_text(verification + "\n", encoding="utf-8")
        (output / "manifest-badging.txt").write_text(badging + "\n", encoding="utf-8")
        signed.replace(output / "oneui-studio.apk")
        json_write(output / "build-report.json", report)
    except (BuildError, OSError, ValueError) as exc:
        (output / "oneui-studio.apk").unlink(missing_ok=True)
        report.update({"status": "failed", "error": str(exc)})
        json_write(output / "build-report.json", report)
        raise BuildError(str(exc)) from exc
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="App folder containing AndroidManifest.xml, src/, res/, and optional assets/")
    parser.add_argument("--output", required=True, help="New folder outside the app sources; existing folders are refused")
    for name in ("android-jar", "lambda-stubs", "aapt2", "javac", "java", "d8", "zipalign", "apksigner"):
        parser.add_argument("--" + name, required=True, help="Explicit local tool or SDK file path")
    parser.add_argument("--tool-provenance", help="Local provenance JSON with installed_tools SHA-256 records")
    parser.add_argument("--keystore", required=True, help="Existing developer key kept outside sources and output")
    parser.add_argument("--key-alias", default="oneui9dev")
    parser.add_argument("--store-pass", default="android", help="Developer key password; omitted from reports (default: android)")
    args = parser.parse_args()
    try:
        report = build(args)
    except (BuildError, OSError, ValueError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "apk": str(Path(args.output) / report["apk"]["path"]), "sha256": report["apk"]["sha256"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
