#!/usr/bin/env python3
"""Build fresh, measured One UI 9 resource overlays on a desktop.

Compilation and developer signing do not establish overlay policy acceptance.
This program never installs, enables, or downloads anything.
"""

import argparse
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile


ANDROID_URI = "http://schemas.android.com/apk/res/android"
A = "{" + ANDROID_URI + "}"
ET.register_namespace("android", ANDROID_URI)
SOURCE_FORMAT = "oneui-studio.source/1"
TOKEN_API = "oneui-studio.tokens/1"
PACK_FORMAT = "oneui9.resource-pack/1"
TARGETS = {"framework": "android", "systemui": "com.android.systemui", "settings": "com.android.settings"}
OVERRIDE_KEYS = set(TARGETS) | {"phone", "keyboard", "files", "messages", "contacts"}
COLORS = set("background surface accent onAccent textPrimary textSecondary quickTileInactive quickTileActive quickTileIconActive quickTileIconInactive quickPanelBackground notificationBackground notificationText settingsBackground settingsIcon keyboardBackground keyboardKeyBackground keyboardKeyText keyboardAccent statusBarIcons navigationBarBackground navigationBarIcons outline link error".split())
DIMENSIONS = {"cornerRadius": (0, 32, "dp"), "quickTileRadius": (0, 32, "dp"), "keyboardKeyRadius": (0, 24, "dp"), "navigationBarHeight": (16, 96, "dp"), "bodyTextSize": (10, 28, "sp")}
FONTS = {"bodyFont", "headlineFont"}
COMPONENTS = set("device.palette quick-panel.palette settings.palette keyboard.palette wallpaper launcher.icons phone.palette contacts.palette messages.palette files.palette typography systemui.geometry component.drawables".split())
ID = re.compile(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+\Z")
EXTENSION = re.compile(r"extension:[a-z][a-z0-9.-]+/[a-z][a-z0-9.-]+\Z")
RESOURCE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
ASSET = re.compile(r"assets/[A-Za-z0-9_-]+\.(png|jpg|jpeg|webp|ttf|otf)\Z")


class BuildError(Exception):
    """A source, evidence, or tool failure that must prevent success."""


def need(condition, message):
    if not condition:
        raise BuildError(message)


def object_fields(value, allowed, required, label):
    need(isinstance(value, dict), f"{label} must be an object")
    need(not (set(value) - set(allowed)), f"{label} has unknown fields: {sorted(set(value) - set(allowed))}")
    need(set(required) <= set(value), f"{label} is missing fields: {sorted(set(required) - set(value))}")


def text(value, label, maximum=1000):
    need(isinstance(value, str) and 0 < len(value) <= maximum and "\x00" not in value, f"{label} must be a bounded nonempty string")
    return value


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, f"Duplicate JSON key {key!r} in {path.name}")
            result[key] = value
        return result

    try:
        need(path.stat().st_size <= 4 * 1024 * 1024, f"JSON input too large: {path}")
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(BuildError(f"Invalid JSON number {value}")))
    except (OSError, UnicodeError, ValueError) as exc:
        raise BuildError(f"Cannot read JSON {path}: {exc}") from exc


def safe_file(root, relative, label):
    need(isinstance(relative, str) and relative and "\\" not in relative, f"Invalid {label} path")
    parts = relative.split("/")
    need(not PurePosixPath(relative).is_absolute() and all(re.fullmatch(r"[A-Za-z0-9_.-]+", p) and p not in (".", "..") for p in parts), f"Invalid {label} path: {relative!r}")
    path = root
    for part in parts:
        path = path / part
        need(not path.is_symlink(), f"Symlink in {label} path: {relative}")
    need(path.is_file() and path.resolve().is_relative_to(root.resolve()), f"Missing or escaping {label} path: {relative}")
    return path


def validate_tokens(tokens, label, assets):
    need(isinstance(tokens, dict) and tokens, f"{label} must contain explicit tokens")
    for role, token in tokens.items():
        need(role in COLORS | set(DIMENSIONS) | FONTS, f"Unknown token role {label}.{role}")
        fields = {"type", "value", "unit"} if role in DIMENSIONS else {"type", "value"}
        object_fields(token, fields, fields, f"{label}.{role}")
        if role in COLORS:
            need(token["type"] == "color" and isinstance(token["value"], str) and re.fullmatch(r"#[0-9A-Fa-f]{8}", token["value"]), f"{label}.{role} must be a literal #AARRGGBB color")
        elif role in DIMENSIONS:
            lower, upper, unit = DIMENSIONS[role]
            value = token["value"]
            need(token["type"] == "dimension" and type(value) in (int, float) and lower <= value <= upper and math.isfinite(value) and token["unit"] == unit, f"{label}.{role} must be a dimension between {lower} and {upper}{unit}")
        else:
            need(token["type"] == "fontAsset" and isinstance(token["value"], str) and token["value"] in assets and assets[token["value"]]["kind"] == "font", f"{label}.{role} requires a declared licensed font asset")


def read_source(root):
    manifest_path = safe_file(root, "manifest.json", "manifest")
    manifest = read_json(manifest_path)
    fields = set("format id version name author license licenseFile tokenApi targetIntent variants assets components overrides stylePack appearance".split())
    required = fields - {"overrides", "stylePack", "appearance"}
    object_fields(manifest, fields, required, "manifest")
    need(manifest["format"] == SOURCE_FORMAT and manifest["tokenApi"] == TOKEN_API, "Unsupported source format or token API")
    need(isinstance(manifest["id"], str) and len(manifest["id"]) <= 128 and ID.fullmatch(manifest["id"]), "Invalid source id")
    need(isinstance(manifest["version"], str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", manifest["version"]), "Invalid source version")
    for field, maximum in (("name", 80), ("author", 120), ("license", 100)):
        text(manifest[field], "manifest." + field, maximum)
    need(manifest["targetIntent"] == {"manufacturer": "Samsung", "uiFamily": "One UI", "uiMajor": 9}, "Source must declare the Samsung One UI 9 target intent")
    need(manifest["licenseFile"] == "LICENSE.txt", "Invalid source license path")
    files = {"manifest.json": manifest_path, "LICENSE.txt": safe_file(root, "LICENSE.txt", "license")}
    assets = {}
    need(isinstance(manifest["assets"], list) and len(manifest["assets"]) <= 100, "Invalid asset declarations")
    for asset in manifest["assets"]:
        object_fields(asset, {"path", "kind", "license"}, {"path", "kind", "license"}, "asset")
        path = asset["path"]
        need(isinstance(path, str) and len(path) <= 160 and ASSET.fullmatch(path) and path not in assets, "Invalid or duplicate asset path")
        suffix = PurePosixPath(path).suffix
        kinds = {"font": {".ttf", ".otf"}, "icon": {".png", ".webp"}, "wallpaper": {".png", ".jpg", ".jpeg", ".webp"}}
        need(isinstance(asset["kind"], str) and asset["kind"] in kinds and suffix in kinds[asset["kind"]], f"Asset kind and extension disagree: {path}")
        text(asset["license"], "asset license", 100)
        assets[path] = asset
        files[path] = safe_file(root, path, "asset")
    variants = {}
    object_fields(manifest["variants"], {"dark", "light"}, set(), "variant paths")
    need(manifest["variants"], "Source requires at least one variant")
    for variant, relative in manifest["variants"].items():
        need(relative == f"tokens/{variant}.json", f"Invalid {variant} token path")
        files[relative] = safe_file(root, relative, "token")
        variants[variant] = read_json(files[relative])
        validate_tokens(variants[variant], f"tokens.{variant}", assets)
    overrides = {}
    object_fields(manifest.get("overrides", {}), {"dark", "light"}, set(), "override paths")
    for variant, relative in manifest.get("overrides", {}).items():
        need(variant in variants and relative == f"overrides/{variant}.json", f"Invalid {variant} override path or missing variant")
        files[relative] = safe_file(root, relative, "override")
        overrides[variant] = read_json(files[relative])
        need(isinstance(overrides[variant], dict) and overrides[variant], "Overrides must be a nonempty object")
        for target, tokens in overrides[variant].items():
            need(target in OVERRIDE_KEYS or (isinstance(target, str) and len(target) <= 160 and EXTENSION.fullmatch(target)), f"Invalid override target key: {target}")
            validate_tokens(tokens, f"overrides.{variant}.{target}", assets)
    components = manifest["components"]
    need(isinstance(components, list) and 1 <= len(components) <= 128, "Invalid component declarations")
    seen = set()
    for component in components:
        object_fields(component, {"id", "required"}, {"id", "required"}, "component")
        name = component["id"]
        need(isinstance(name, str) and len(name) <= 160 and (name in COMPONENTS or EXTENSION.fullmatch(name)) and name not in seen and type(component["required"]) is bool, "Invalid or duplicate component declaration")
        seen.add(name)
    if "stylePack" in manifest:
        style = manifest["stylePack"]
        object_fields(style, {"id", "version"}, {"id", "version"}, "stylePack")
        need(isinstance(style["id"], str) and ID.fullmatch(style["id"]) and isinstance(style["version"], str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", style["version"]), "Invalid stylePack declaration")
    appearance = manifest.get("appearance", {})
    object_fields(appearance, {"dark", "light"}, set(), "appearance")
    for variant, settings in appearance.items():
        need(variant in variants, "Appearance variant has no token variant")
        object_fields(settings, {"icons", "components"}, set(), "appearance settings")
        need(settings, "Appearance settings must not be empty")
        icons = settings.get("icons", {})
        need(isinstance(icons, dict) and len(icons) <= 128, "Invalid icon slots")
        for slot, asset in icons.items():
            need(re.fullmatch(r"[a-z][A-Za-z0-9]*(?:\.[a-z][A-Za-z0-9]*)+", slot) and isinstance(asset, str) and asset in assets and assets[asset]["kind"] == "icon", f"Invalid or undeclared icon asset for {slot}")
        styles = settings.get("components", {})
        object_fields(styles, {"quickTile", "keyboardKey", "card", "dialog", "button"}, set(), "component appearance")
        for name, style in styles.items():
            object_fields(style, {"shape", "fillRole", "strokeRole", "strokeWidthDp", "radiusRole"}, {"shape", "fillRole"}, name)
            need(all(isinstance(style.get(field, default), str) for field, default in (("shape", ""), ("fillRole", ""), ("strokeRole", "outline"), ("radiusRole", "cornerRadius"))) and style["shape"] in {"rectangle", "roundedRectangle", "circle"} and style["fillRole"] in COLORS and style.get("strokeRole", "outline") in COLORS and style.get("radiusRole", "cornerRadius") in {"cornerRadius", "quickTileRadius", "keyboardKeyRadius"}, f"Invalid component style {name}")
            width = style.get("strokeWidthDp", 0)
            need(type(width) in (int, float) and 0 <= width <= 8 and math.isfinite(width), f"Invalid stroke width for {name}")
    return manifest, variants, overrides, files


def read_pack(path, inputs):
    pack = read_json(path)
    need(isinstance(pack, dict) and pack.get("format") == PACK_FORMAT and pack.get("sourceTokenApi") == TOKEN_API and type(pack.get("androidApiLevel")) is int and pack["androidApiLevel"] == 37, "Unsupported resource pack format, token API, or Android API")
    text(pack.get("buildFingerprint"), "pack buildFingerprint", 1000)
    targets = pack.get("targets")
    need(isinstance(targets, list) and 1 <= len(targets) <= 3, "Pack must contain one to three measured targets")
    seen = set()
    apks = {}
    # Hash every input before invoking resource inspection or creating outputs.
    for target in targets:
        need(isinstance(target, dict) and isinstance(target.get("key"), str) and target["key"] in TARGETS and target["key"] not in seen, "Invalid or duplicate target key")
        key = target["key"]
        seen.add(key)
        need(target.get("package") == TARGETS[key], f"Incorrect package for target {key}")
        relative = target.get("apkPath")
        need(isinstance(relative, str) and relative.startswith("apks/") and relative.endswith(".apk"), f"Invalid APK path for {key}")
        apk = safe_file(inputs, relative, "APK")
        expected = target.get("apkSha256")
        need(isinstance(expected, str) and re.fullmatch(r"[0-9a-fA-F]{64}", expected) and sha256(apk) == expected.lower(), f"APK SHA-256 mismatch for {key}: {relative}")
        apks[key] = apk
        if "targetName" in target:
            need(isinstance(target["targetName"], str) and re.fullmatch(r"[A-Za-z0-9_.-]+", target["targetName"]), f"Invalid targetName for {key}")
        bindings = target.get("bindings")
        need(isinstance(bindings, list) and len(bindings) <= 10000, f"Invalid bindings for {key}")
        for binding in bindings:
            need(isinstance(binding, dict), f"Invalid binding for {key}")
            kind, name, role = binding.get("type"), binding.get("name"), binding.get("role")
            need(isinstance(kind, str) and kind in {"color", "dimen"} and isinstance(name, str) and RESOURCE_NAME.fullmatch(name), f"Invalid resource type/name for {key}")
            need(isinstance(role, str), f"Invalid semantic role for {key}/{name}")
            need((kind == "color" and role in COLORS) or (kind == "dimen" and role in DIMENSIONS), f"Invalid semantic role for {key}/{name}")
            if "originalAlpha" in binding:
                need(kind == "color" and type(binding["originalAlpha"]) is int and 0 <= binding["originalAlpha"] <= 255, f"Invalid originalAlpha for {key}/{name}; color-only integer 0..255 required")
            need(isinstance(binding.get("resourceId"), str) and re.fullmatch(r"0x[0-9A-Fa-f]{8}", binding["resourceId"]), f"Invalid resourceId for {key}/{name}")
            need(isinstance(binding.get("variant"), str) and binding["variant"] in {"dark", "light", "current"}, f"Invalid binding variant for {key}/{name}")
            qualifiers = binding.get("qualifiers")
            need(isinstance(qualifiers, list) and 1 <= len(qualifiers) <= 2 and all(type(q) is str and q in {"", "night"} for q in qualifiers) and len(set(qualifiers)) == len(qualifiers), f"Invalid resource qualifiers for {key}/{name}")
            text(binding.get("evidence"), f"evidence for {key}/{name}", 10000)
    need("framework" in apks, "Pack requires the measured framework APK for linking")
    return pack, apks


def verify_collector_report(inputs, pack, apks):
    """Check available collector evidence without treating partial help as failure."""
    report_path = inputs / "report.json"
    if not report_path.exists():
        return False
    report = read_json(safe_file(inputs, "report.json", "collector report"))
    need(isinstance(report, dict), "Collector report must be an object")
    device = report.get("device", {})
    properties = device.get("properties", {}) if isinstance(device, dict) else {}
    need(isinstance(properties, dict), "Invalid collector device properties")
    need(properties.get("ro.build.fingerprint") == pack["buildFingerprint"], "Collector build fingerprint does not match the resource pack")
    need(str(properties.get("ro.build.version.sdk")) == str(pack["androidApiLevel"]), "Collector Android API does not match the resource pack")
    packages = report.get("packages", {})
    need(isinstance(packages, dict), "Invalid collector package inventory")
    for target in pack["targets"]:
        package = packages.get(target["package"], {})
        records = package.get("apks", []) if isinstance(package, dict) else []
        need(isinstance(records, list), "Invalid collector APK inventory")
        matched = [record for record in records if isinstance(record, dict) and record.get("localPath") == target["apkPath"]]
        need(len(matched) == 1, f"Collector APK record missing or duplicated for {target['key']}")
        record = matched[0]
        need(isinstance(record.get("sha256"), str) and record["sha256"].lower() == target["apkSha256"].lower() and type(record.get("sizeBytes")) is int and record["sizeBytes"] == apks[target["key"]].stat().st_size, f"Collector APK evidence mismatch for {target['key']}")
    return True


def tool_path(value):
    result = shutil.which(value)
    need(result is not None, f"Tool not found: {value}")
    return Path(result).resolve()


def run(argv, *, env=None):
    try:
        result = subprocess.run([str(x) for x in argv], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, errors="replace", timeout=120, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BuildError(f"Tool {Path(argv[0]).name} failed: {exc}") from exc
    need(result.returncode == 0, f"Tool {Path(argv[0]).name} {' '.join(str(x) for x in argv[1:3])} exited {result.returncode}: {result.stderr[-4000:].strip()}")
    return result.stdout


def parse_resources(dump):
    package = None
    resources = {}
    current = None
    for line in dump.splitlines():
        match = re.search(r"Package name=([^\s]+)", line)
        if match:
            package = match.group(1)
        match = re.match(r"\s*resource (0x[0-9a-fA-F]{8}) ([^/\s]+)/([^\s]+)(?:\s|$)", line)
        if match:
            identifier, kind, name = match.groups()
            current = {"id": identifier.lower(), "values": {}}
            resources[(kind, name)] = current
        elif current is not None:
            match = re.match(r"\s+\(([^)]*)\) (.+)$", line)
            if match:
                current["values"][match.group(1)] = match.group(2)
    return package, resources


def package_name(source_id, key):
    parts = source_id.replace("-", "_").split(".")
    parts = [p if not p[0].isdigit() else "_" + p for p in parts]
    return "org.bingblop.oneui9.theme." + ".".join(parts) + "." + key


def token_value(token):
    if token["type"] == "color":
        return token["value"].upper()
    number = format(Decimal(str(token["value"])), "f")
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    return number + token["unit"]


def original_values(resource):
    return [{"qualifier": qualifier, "kind": "reference" if value.startswith("@") else "file" if value.startswith("(file)") else "literal", "value": value} for qualifier, value in sorted(resource["values"].items())]


def plan_target(target, variants, overrides, resources):
    key = target["key"]
    selected = "dark" if "dark" in variants else "light"
    values, omitted, replacements, used = {}, [], [], set()
    for binding in target["bindings"]:
        kind, name = binding["type"], binding["name"]
        resource = resources.get((kind, name))
        need(resource is not None and resource["id"] == binding["resourceId"].lower(), f"Binding {key}/{kind}/{name} {binding['resourceId']} does not match the actual resource table")
        variant = selected if binding["variant"] == "current" else binding["variant"]
        role = binding["role"]
        base = {"type": kind, "name": name, "role": role, "variant": variant}
        if variant not in variants:
            omitted.append({**base, "reason": "source-variant-missing"})
            continue
        own = overrides.get(variant, {}).get(key, {})
        tokens = {**variants[variant], **own}
        if role not in tokens:
            omitted.append({**base, "reason": "explicit-token-missing"})
            continue
        token = tokens[role]
        source_value = token_value(token)
        value = source_value
        original_alpha = binding.get("originalAlpha", 255)
        if kind == "color":
            alpha = round(int(source_value[1:3], 16) * original_alpha / 255)
            value = f"#{alpha:02X}{source_value[3:]}"
        used.add((variant, key if role in own else None, role))
        for qualifier in binding["qualifiers"]:
            slot = (kind, name, qualifier)
            need(slot not in values, f"Duplicate replacement for {key}/{kind}/{name} ({qualifier})")
            values[slot] = value
        replacements.append({**base, "resourceId": binding["resourceId"].lower(), "qualifiers": sorted(binding["qualifiers"]), "replacementKind": "literal", "sourceValue": source_value, "value": value, "tokenOrigin": "per-app-override" if role in own else "global-token", "originalValues": original_values(resource), "evidence": binding["evidence"], **({"originalAlpha": original_alpha} if kind == "color" else {})})
    return values, omitted, replacements, used


def xml_write(root, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def write_project(folder, package, target, values, version):
    manifest = ET.Element("manifest", {"package": package, A + "versionCode": "1", A + "versionName": version})
    ET.SubElement(manifest, "uses-sdk", {A + "minSdkVersion": "37", A + "targetSdkVersion": "37"})
    ET.SubElement(manifest, "application", {A + "hasCode": "false"})
    attributes = {A + "targetPackage": target["package"], A + "isStatic": "false", A + "category": "org.bingblop.oneui9.theme", A + "resourcesMap": "@xml/overlays"}
    if "targetName" in target:
        attributes[A + "targetName"] = target["targetName"]
    ET.SubElement(manifest, "overlay", attributes)
    xml_write(manifest, folder / "AndroidManifest.xml")
    mapping = ET.Element("overlay")
    for kind, name in sorted({(k, n) for k, n, _ in values}):
        ET.SubElement(mapping, "item", {"target": f"{kind}/{name}", "value": f"@{kind}/{name}"})
    xml_write(mapping, folder / "res/xml/overlays.xml")
    for qualifier in sorted({q for _, _, q in values}):
        root = ET.Element("resources")
        for (kind, name, config), value in sorted(values.items()):
            if config == qualifier:
                ET.SubElement(root, kind, {"name": name}).text = value
        xml_write(root, folder / ("res/values" + ("-" + qualifier if qualifier else "")) / "values.xml")


def verify_compiled(aapt2, apk, package, expected):
    found_package, resources = parse_resources(run([aapt2, "dump", "resources", apk]))
    need(found_package == package, "Compiled output package does not match the generated manifest")
    actual = {(kind, name, qualifier): value for (kind, name), resource in resources.items() if kind in {"color", "dimen"} for qualifier, value in resource["values"].items()}
    need(set(actual) == set(expected), "Compiled resource types, names, or qualifiers disagree with generated sources")
    for slot, wanted in expected.items():
        value = actual[slot]
        if slot[0] == "color":
            valid = value.lower() == wanted.lower()
        else:
            parsed = re.fullmatch(r"([+-]?[0-9]+(?:\.[0-9]+)?)(dp|dip|sp)", value)
            planned = re.fullmatch(r"([+-]?[0-9]+(?:\.[0-9]+)?)(dp|sp)", wanted)
            # Bounded dimensions use at least 15 fractional bits in Android's
            # complex encoding; include its half-step and dump's decimal rounding.
            tolerance = 1 / 65536 + 0.000001
            valid = bool(parsed and planned and parsed.group(2).replace("dip", "dp") == planned.group(2) and math.isclose(float(parsed.group(1)), float(planned.group(1)), rel_tol=0, abs_tol=tolerance))
        need(valid, f"Compiled replacement differs for {slot[0]}/{slot[1]} ({slot[2]}): expected {wanted}, got {value}")


def archive(output, filename):
    destination = output / filename
    temporary = output / (filename + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
            for path in sorted(output.rglob("*")):
                if not path.is_file() or path in (destination, temporary) or path.name == "compiled.zip":
                    continue
                info = zipfile.ZipInfo(path.relative_to(output).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, path.read_bytes())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def build(args):
    source, inputs, output = Path(args.source).resolve(), Path(args.inputs).resolve(), Path(args.output).absolute()
    need(not output.exists() and not output.is_symlink(), f"Output already exists: {output}")
    manifest, variants, overrides, source_files = read_source(source)
    pack_path = Path(args.pack).resolve()
    pack, apks = read_pack(pack_path, inputs)
    metadata_verified = verify_collector_report(inputs, pack, apks)
    tools = {"aapt2": tool_path(args.aapt2), "zipalign": tool_path(args.zipalign)}
    if args.keystore:
        need(Path(args.keystore).is_file(), "Signing keystore is missing")
        text(args.key_alias, "key alias", 128)
        tools["apksigner"] = tool_path(args.apksigner)
    versions = {"aapt2": run([tools["aapt2"], "version"]).strip()}
    if "apksigner" in tools:
        versions["apksigner"] = run([tools["apksigner"], "version"]).strip()
    plans, used = [], set()
    for target in pack["targets"]:
        package, resources = parse_resources(run([tools["aapt2"], "dump", "resources", apks[target["key"]]]))
        need(package == target["package"], f"Input resource table package mismatch for {target['key']}")
        values, omitted, replacements, references = plan_target(target, variants, overrides, resources)
        plans.append((target, values, omitted, replacements))
        used.update(references)
    omitted_controls = []
    for variant, tokens in variants.items():
        for role in tokens:
            if (variant, None, role) not in used:
                omitted_controls.append({"variant": variant, "targetKey": None, "role": role, "reason": "font-generation-unsupported" if role in FONTS else "no-used-binding"})
    for variant, targets in overrides.items():
        for target, tokens in targets.items():
            for role in tokens:
                if (variant, target, role) not in used:
                    omitted_controls.append({"variant": variant, "targetKey": target, "role": role, "reason": "target-unmapped" if target not in apks else "no-used-binding"})
    # Required extensions cannot silently become a partial output.
    component_reports = []
    role_groups = {"device.palette": ({"framework"}, COLORS), "quick-panel.palette": ({"systemui"}, {r for r in COLORS if r.startswith("quick")}), "settings.palette": ({"settings"}, {"settingsBackground", "settingsIcon", "background", "surface", "accent", "textPrimary", "textSecondary"}), "typography": (set(TARGETS), {"bodyTextSize"}), "systemui.geometry": ({"systemui"}, set(DIMENSIONS))}
    emitted_roles = {target["key"]: {entry["role"] for entry in replacements} for target, _, _, replacements in plans}
    for component in manifest["components"]:
        keys, roles = role_groups.get(component["id"], (set(), set()))
        supported = any(roles & emitted_roles.get(key, set()) for key in keys)
        need(not component["required"] or supported, f"Required component has no verified emitted bindings: {component['id']}")
        component_reports.append({**component, "status": "partially-mapped" if supported else "omitted"})
    source_digests = {relative: sha256(path) for relative, path in sorted(source_files.items())}
    source_digest = hashlib.sha256(json_bytes(source_digests)).hexdigest()
    report = {"format": "oneui9.theme-build/1", "status": "building", "applied": False, "policyVerified": False, "compatibilityCertification": False, "metadataVerified": metadata_verified, "sourceId": manifest["id"], "sourceVersion": manifest["version"], "sourceSha256": source_digest, "sourceFiles": source_digests, "packSha256": sha256(pack_path), "buildFingerprint": pack["buildFingerprint"], "androidApiLevel": 37, "tools": {name: {"version": versions.get(name), "executableSha256": sha256(path)} for name, path in tools.items()}, "targets": [], "omittedControls": omitted_controls, "components": component_reports, "unsupportedAppearance": manifest.get("appearance", {}), "unsupportedAssets": manifest["assets"], "unresolvedStylePack": manifest.get("stylePack"), "errors": []}
    output.mkdir(parents=True, exist_ok=False)
    try:
        for relative, path in sorted(source_files.items()):
            destination = output / "source" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
        (output / "resource-pack.json").write_bytes(json_bytes(pack))
        for target, values, omitted, replacements in plans:
            key = target["key"]
            package = package_name(manifest["id"], key)
            target_report = {"key": key, "targetPackage": target["package"], "overlayPackage": package, "inputApkPath": target["apkPath"], "inputApkSha256": target["apkSha256"].lower(), "buildFingerprint": pack["buildFingerprint"], "androidApiLevel": 37, "sourceSha256": source_digest, "packSha256": report["packSha256"], "targetName": target.get("targetName"), "bindingCount": len(target["bindings"]), "emittedBindingCount": len(replacements), "resourceCount": len({(k, n) for k, n, _ in values}), "configurationCount": len(values), "omittedBindings": omitted, "replacements": replacements, "applied": False, "policyVerified": False, "compiledValueVerification": False, "status": "omitted" if not values else "building", "artifacts": []}
            report["targets"].append(target_report)
            folder = output / "targets" / key
            folder.mkdir(parents=True)
            if values:
                write_project(folder, package, target, values, manifest["version"])
                compiled, unsigned, aligned = folder / "compiled.zip", folder / "overlay-unsigned.apk", folder / "overlay-aligned.apk"
                run([tools["aapt2"], "compile", "--dir", folder / "res", "-o", compiled])
                argv = [tools["aapt2"], "link", "-I", apks["framework"]]
                if key != "framework":
                    argv += ["-I", apks[key]]
                argv += ["--manifest", folder / "AndroidManifest.xml", "--min-sdk-version", "37", "--target-sdk-version", "37", "--no-auto-version", "--no-resource-deduping", "--no-resource-removal", "--auto-add-overlay", "-o", unsigned, compiled]
                run(argv)
                need(unsigned.is_file(), f"Linker did not produce an APK for {key}")
                run([tools["zipalign"], "-f", "4", unsigned, aligned])
                verify_compiled(tools["aapt2"], aligned, package, values)
                final_apk = aligned
                if args.keystore:
                    final_apk = folder / "overlay-signed.apk"
                    signing_env = {**os.environ, "ONEUI9_BUILDER_STORE_PASS": args.store_pass}
                    run([tools["apksigner"], "sign", "--ks", Path(args.keystore).resolve(), "--ks-key-alias", args.key_alias, "--ks-pass", "env:ONEUI9_BUILDER_STORE_PASS", "--out", final_apk, aligned], env=signing_env)
                    verification = run([tools["apksigner"], "verify", "--verbose", "--print-certs", final_apk])
                    (folder / "signature-verification.txt").write_text(verification, encoding="utf-8")
                    verify_compiled(tools["aapt2"], final_apk, package, values)
                run([tools["zipalign"], "-c", "4", final_apk])
                target_report.update({"status": "signed" if args.keystore else "compiled", "compiledValueVerification": True, "artifacts": [{"path": final_apk.relative_to(output).as_posix(), "sha256": sha256(final_apk), "developerSigned": bool(args.keystore)}]})
            (folder / "build-report.json").write_bytes(json_bytes(target_report))
        need(any(t["compiledValueVerification"] for t in report["targets"]), "No explicitly selected roles have emitted resource bindings")
        report["status"] = "signed" if args.keystore else "compiled"
        report["bundle"] = manifest["id"] + "-theme.zip"
        (output / "build-report.json").write_bytes(json_bytes(report))
        archive(output, report["bundle"])
    except (BuildError, OSError) as exc:
        report["status"] = "failed"
        report["errors"].append(str(exc))
        (output / "build-report.json").write_bytes(json_bytes(report))
        raise BuildError(str(exc)) from exc
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("source", "pack", "inputs", "output"):
        parser.add_argument("--" + option, required=True)
    for tool in ("aapt2", "apksigner", "zipalign"):
        parser.add_argument("--" + tool, default=tool)
    parser.add_argument("--keystore", help="Owner's developer signing key; never a Samsung signing claim")
    parser.add_argument("--key-alias", default="oneui9dev")
    parser.add_argument("--store-pass", default="android", help="Developer keystore password (default: android)")
    args = parser.parse_args(argv)
    try:
        result = build(args)
    except (BuildError, OSError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    print(f"{result['status']}: {Path(args.output) / result['bundle']}; applied=false; policyVerified=false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
