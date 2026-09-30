#!/usr/bin/env python3
import sys
import os
import json
import argparse
from .shizuku_bridge import ShizukuBridge
from .system_properties import SamsungSystemProperties
from .fabricated import FabricatedOverlayBuilder
from .overlay_builder import RROApkBuilder

def print_header():
    print("\033[1;36m======================================================\033[0m")
    print("\033[1;32m      ✨ Samsung One UI 9.0 Modern Theme Engine ✨     \033[0m")
    print("\033[1;36m======================================================\033[0m\n")

def cmd_status(args):
    print_header()
    bridge = ShizukuBridge()
    props = SamsungSystemProperties(bridge)

    print(f"Shell Bridge Mode   : \033[1;33m{bridge.mode}\033[0m")
    active_theme = props.get_active_theme_package()
    print(f"Active Theme Package: \033[1;32m{active_theme or 'Default / None'}\033[0m")

    # Check stub
    code, out, _ = bridge.run("pm path com.samsung.android.themepark")
    has_themepark = "package:" in out
    code2, out2, _ = bridge.run("pm path com.samsung.android.themedesigner")
    has_designer = "package:" in out2

    print(f"Theme Designer (OneUI 9): \033[1;{'32mInstalled' if has_designer else '31mNot Installed'}\033[0m")
    print(f"Theme Park Legacy Stub  : \033[1;{'32mInstalled' if has_themepark else '31mMissing'}\033[0m")

def cmd_fix_hex(args):
    print_header()
    print("[*] Applying One UI 9.0 Compatibility Fixes for Hex Installer...")
    bridge = ShizukuBridge()
    props = SamsungSystemProperties(bridge)

    # 1. Enable Monet overlays
    monet_overlays = [
        "android:SemWT_android",
        "android:SemWT_com.android.systemui",
        "android:SemWT_MonetPalette",
        "android:SemWT_G_MonetPalette"
    ]
    for o in monet_overlays:
        print(f"  -> Enabling overlay: {o}")
        props.enable_overlay(o)

    # 2. Set active theme setting
    print("  -> Setting system current_sec_active_themepackage to 'com.samsung.themedesigner.Hex'...")
    props.set_active_theme_package("com.samsung.themedesigner.Hex")

    print("\n\033[1;32m[✓] Hex Installer compatibility configuration applied successfully!\033[0m")

def cmd_apply_theme(args):
    print_header()
    theme_file = args.file
    if not os.path.exists(theme_file):
        print(f"\033[1;31mError: Theme file {theme_file} not found.\033[0m")
        sys.exit(1)

    with open(theme_file, "r") as f:
        data = json.load(f)

    name = data.get("name", "CustomTheme")
    print(f"[*] Applying Theme: \033[1;32m{name}\033[0m")

    bridge = ShizukuBridge()
    props = SamsungSystemProperties(bridge)

    overlays = data.get("overlays", {})
    for target_pkg, values in overlays.items():
        overlay_name = f"theme_{name.lower()}_{target_pkg.replace('.', '_')}"
        print(f"  -> Fabricating dynamic overlay for {target_pkg}...")
        builder = FabricatedOverlayBuilder(target_pkg, overlay_name, bridge)
        for k, v in values.get("colors", {}).items():
            builder.add_color(k, v)
        for k, v in values.get("booleans", {}).items():
            builder.add_bool(k, v)
        for k, v in values.get("integers", {}).items():
            builder.add_integer(k, v)
        builder.build_and_apply()

    print("\n\033[1;32m[✓] Theme applied instantly without reboot!\033[0m")

def main():
    parser = argparse.ArgumentParser(description="One UI Modern Theming Engine")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Inspect device theming status")
    subparsers.add_parser("fix-hex", help="Apply One UI 9 fix for Hex Installer")
    
    apply_p = subparsers.add_parser("apply", help="Apply a theme json profile")
    apply_p.add_argument("file", help="Path to theme.json")

    args = parser.parse_args()
    if args.command == "status":
        cmd_status(args)
    elif args.command == "fix-hex":
        cmd_fix_hex(args)
    elif args.command == "apply":
        cmd_apply_theme(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
