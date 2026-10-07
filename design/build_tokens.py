#!/usr/bin/env python3
"""Generate platform token files from design/tokens.json.

    python3 design/build_tokens.py          # write the generated files
    python3 design/build_tokens.py --check  # exit 1 if any generated file is stale
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOKENS = json.loads((ROOT / "tokens.json").read_text())
HEADER = "Generated from design/tokens.json by design/build_tokens.py. Do not edit by hand."


def parse_color(value):
    """Return (r, g, b, a) with a in 0..255 for #RRGGBB or rgba(r, g, b, a)."""
    value = value.strip()
    if value.startswith("#") and len(value) == 7:
        return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16), 255
    m = re.fullmatch(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)", value)
    if m:
        r, g, b = (int(m.group(i)) for i in (1, 2, 3))
        return r, g, b, round(float(m.group(4)) * 255)
    raise ValueError(f"Unsupported color: {value}")


def argb_hex(value):
    r, g, b, a = parse_color(value)
    return f"{a:02X}{r:02X}{g:02X}{b:02X}"


def snake(name):
    return name.replace("-", "_")


def camel(name):
    head, *rest = re.split(r"[-_]", name)
    return head + "".join(p[:1].upper() + p[1:] for p in rest)


def resolve_color(ref):
    return TOKENS["color"][ref]["value"] if ref in TOKENS["color"] else ref


# ---------------------------------------------------------------- CSS

def build_css():
    lines = [f"/* {HEADER} */", ":root {"]
    for name, tok in TOKENS["color"].items():
        lines.append(f"    --{name}: {tok['value']};")
    for name, px in TOKENS["radius"].items():
        lines.append(f"    --radius-{name}: {px}px;")
    for name, px in TOKENS["space"].items():
        lines.append(f"    --space-{name}: {px}px;")
    lines.append(f"    --font-sans: {TOKENS['font']['family-sans']};")
    lines.append(f"    --font-mono: {TOKENS['font']['family-mono']};")
    for name, t in TOKENS["type"].items():
        lines.append(f"    --fs-{name}: {t['size']}px;")
        lines.append(f"    --fw-{name}: {t['weight']};")
        lines.append(f"    --ls-{name}: {t['tracking']}px;")
    for name, e in TOKENS["elevation"].items():
        color = f"var(--{e['color']})" if e["color"] in TOKENS["color"] else e["color"]
        lines.append(f"    --shadow-{name}: 0 {e['y']}px {e['blur']}px {color};")
    for name, px in TOKENS["blur"].items():
        lines.append(f"    --blur-{name}: {px}px;")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- Android XML

def build_android():
    lines = ['<?xml version="1.0" encoding="utf-8"?>', f"<!-- {HEADER} -->", "<resources>"]
    for name, tok in TOKENS["color"].items():
        lines.append(f'    <color name="hx_{snake(name)}">#{argb_hex(tok["value"])}</color>')
    lines.append("")
    for name, px in TOKENS["radius"].items():
        lines.append(f'    <dimen name="hx_radius_{name}">{px}dp</dimen>')
    for name, px in TOKENS["space"].items():
        lines.append(f'    <dimen name="hx_space_{name}">{px}dp</dimen>')
    for name, t in TOKENS["type"].items():
        lines.append(f'    <dimen name="hx_text_{name}">{t["size"]}sp</dimen>')
    for name, px in TOKENS["blur"].items():
        lines.append(f'    <dimen name="hx_blur_{name}">{px}dp</dimen>')
    lines.append("</resources>")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- Compose

def build_compose():
    def tracking(t):
        # CSS letter-spacing is in px; Compose takes sp, which matches at 1x font scale.
        return f"{t['tracking']}.sp" if t["tracking"] else "0.sp"

    out = [
        f"// {HEADER}",
        "package com.hexnext.themer.ui.theme",
        "",
        "import androidx.compose.material3.darkColorScheme",
        "import androidx.compose.ui.graphics.Color",
        "import androidx.compose.ui.text.TextStyle",
        "import androidx.compose.ui.text.font.FontWeight",
        "import androidx.compose.ui.unit.dp",
        "import androidx.compose.ui.unit.sp",
        "",
        "object HexColors {",
    ]
    for name, tok in TOKENS["color"].items():
        out.append(f"    val {camel(name)} = Color(0x{argb_hex(tok['value'])})")
    out += ["}", "", "object HexRadius {"]
    for name, px in TOKENS["radius"].items():
        out.append(f"    val {camel(name)} = {px}.dp")
    out += ["}", "", "object HexSpace {"]
    for name, px in TOKENS["space"].items():
        out.append(f"    val s{name} = {px}.dp")
    out += ["}", "", "object HexBlur {"]
    for name, px in TOKENS["blur"].items():
        out.append(f"    val {camel(name)} = {px}.dp")
    out += ["}", "", "object HexElevation {"]
    for name, e in TOKENS["elevation"].items():
        color = resolve_color(e["color"])
        out.append(f"    val {camel(name)}Y = {e['y']}.dp")
        out.append(f"    val {camel(name)}Blur = {e['blur']}.dp")
        out.append(f"    val {camel(name)}Color = Color(0x{argb_hex(color)})")
    out += ["}", "", "/** Sections and captions are uppercase: apply `.uppercase()` to the text. */", "object HexType {"]
    for name, t in TOKENS["type"].items():
        out.append(
            f"    val {camel(name)} = TextStyle(fontSize = {t['size']}.sp, "
            f"fontWeight = FontWeight.W{t['weight']}, letterSpacing = {tracking(t)})"
        )
    out += [
        "}",
        "",
        "val HexNextColorScheme = darkColorScheme(",
        "    primary = HexColors.accent,",
        "    onPrimary = HexColors.onAccent,",
        "    secondary = HexColors.secondary,",
        "    onSecondary = HexColors.textMain,",
        "    background = HexColors.bgBase,",
        "    onBackground = HexColors.textMain,",
        "    surface = HexColors.bgSurface,",
        "    onSurface = HexColors.textMain,",
        "    surfaceVariant = HexColors.bgCard,",
        "    onSurfaceVariant = HexColors.textMuted,",
        "    outline = HexColors.borderGlass,",
        "    error = HexColors.danger,",
        "    onError = HexColors.onAccent,",
        ")",
    ]
    return "\n".join(out) + "\n"


OUTPUTS = {
    ROOT / "css" / "tokens.css": build_css,
    ROOT / "android" / "values" / "hexnext_tokens.xml": build_android,
    ROOT / "compose" / "HexNextTokens.kt": build_compose,
}


def main():
    check = "--check" in sys.argv[1:]
    stale = []
    for path, build in OUTPUTS.items():
        text = build()
        if check:
            if not path.exists() or path.read_text() != text:
                stale.append(path.relative_to(ROOT.parent))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            print(f"wrote {path.relative_to(ROOT.parent)}")
    if stale:
        print("Stale token files, run python3 design/build_tokens.py:")
        for p in stale:
            print(f"  {p}")
        sys.exit(1)


if __name__ == "__main__":
    main()
