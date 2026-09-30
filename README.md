# Samsung One UI 9.0 Modern Theme Engine & Hex Compatibility Suite

A next-generation theming framework, diagnostic suite, and compatibility layer for **Samsung Galaxy devices running One UI 6, 7, 8, and 9.0 (Android 14, 15, and 16)**.

---

## 🌟 Features

- **Fabricated Runtime Resource Overlays (RRO):** Dynamic, instantaneous color and resource styling via native Android `cmd overlay fabricate`—no slow compilation, no reboot required.
- **Hex Installer One UI 9 Fix Suite:** Fully documented reverse engineering and compatibility layer enabling legacy themers to pass all setup prerequisites.
- **Theme Park Stub Engine:** Zero-overhead compatibility stub APK resolving the `com.samsung.android.themepark` ➔ `com.samsung.android.themedesigner` namespace migration.
- **HexBridge Pro App & Web Dashboard:** Native Android WebView client (`com.hexbridge.pro`) + lightweight local web server with Shizuku integration for full remote theming and diagnostics.
- **Theme Profiles:** Ready-to-use JSON theme templates (AMOLED Pure Black, Neon Violet, Cyberpunk Gold).

---

## 📂 Repository Structure

```
.
├── apps/
│   ├── dummy-themepark/         # Theme Park legacy stub APK builder
│   └── hex-bridge/              # Native Android APK & Web Dashboard
│       ├── app.py               # Flask backend & REST API
│       └── build-apk/           # Java sources, AAPT2, D8, and compile scripts
├── bin/
│   └── oneui-themer             # Command line wrapper
├── docs/
│   ├── ONE_UI_9_THEME_ARCHITECTURE.md
│   ├── HEX_INSTALLER_REVERSE_ENGINEERING.md
│   └── FABRICATED_OVERLAYS_GUIDE.md
├── engine/                      # Core Python theming engine
│   ├── cli.py                   # Unified CLI tool
│   ├── fabricated.py            # Android Fabricated Overlay manager
│   ├── overlay_builder.py       # AAPT2 RRO APK compiler
│   ├── shizuku_bridge.py        # Privileged Shizuku (rish) bridge
│   └── system_properties.py     # One UI system settings manager
└── themes/                      # Theme profiles
    ├── amoled-pure-black/
    ├── cyberpunk-oneui/
    └── modern-monet-neon/
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Samsung Galaxy device running One UI 6.x – 9.0
- [Shizuku](https://shizuku.rikka.app/) running via Wireless Debugging or Root
- [Termux](https://termux.dev/) with `git` and `python` installed

### 2. Inspect Theming Status
```bash
./bin/oneui-themer status
```

### 3. Apply Hex Installer Compatibility Fix
```bash
./bin/oneui-themer fix-hex
```

### 4. Apply a Modern Theme Profile
```bash
./bin/oneui-themer apply themes/amoled-pure-black/theme.json
```

---

## 📱 Building the HexBridge Pro Native APK

To compile and sign the native companion app directly on your Android device:
```bash
cd apps/hex-bridge/build-apk
./compile.sh
```
The compiled APK will be automatically signed and placed into `/storage/emulated/0/Download/HexBridge_Pro.apk`.

---

## 🛠️ Reverse Engineering Summary

Our full reverse engineering breakdown of `project.vivid.hex.bodhi` reveals:
1. **Setup Check (Theme Park):** Evaluates `Settings.System.getString("current_sec_active_themepackage").startsWith("com.samsung.themedesigner")`.
2. **Build Failures:** Legacy Hex Installer attempts to build overlay APKs with deprecated resource IDs against legacy AAPT toolchains.
3. **Modern Alternative:** Using native Fabricated Overlays avoids AAPT fragmentation and provides 100% compatibility across all One UI versions.

For detailed analysis, refer to [docs/HEX_INSTALLER_REVERSE_ENGINEERING.md](docs/HEX_INSTALLER_REVERSE_ENGINEERING.md).

---

## 📄 License
MIT License. See [LICENSE](LICENSE) for details.
# OneUI-Theme-Engine
