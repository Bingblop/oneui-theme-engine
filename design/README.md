# HexNext design tokens

One source of truth for the HexNext look: a near-black ground, translucent glass cards, a cyan `#00E5FF` accent with a violet `#7C4DFF` secondary, and One UI-style rounded corners.

Edit `tokens.json`, then regenerate:

```bash
python3 design/build_tokens.py          # rewrite the generated files
python3 design/build_tokens.py --check  # fail if a generated file is out of date
```

| Output | For | How to use it |
| --- | --- | --- |
| `android/values/hexnext_tokens.xml` | XML layouts and themes | Copy into `res/values/`. Colors are `@color/hx_*`, sizes are `@dimen/hx_*`. |
| `compose/HexNextTokens.kt` | Jetpack Compose | Copy into `ui/theme/`. Use `MaterialTheme(colorScheme = HexNextColorScheme)` and the `HexColors`, `HexType`, `HexRadius`, `HexSpace` objects. |
| `css/tokens.css` | WebView or web dashboards | Link it, or paste its `:root` block. Variable names match the existing HexNext web UI. |

## Rules

- Text and icons on an accent fill use `on-accent` (black), never white.
- `text-dim` is decorative only; it fails contrast for body text.
- The accent is the swappable theme color: anything that marks "active" reads it, so a theme preset only has to change `accent` and `secondary`.
- Cards and tiles use `radius.lg` (20). Pills are fully rounded. No sharp corners.
- Section labels and captions are uppercase with positive tracking; display and brand text have negative tracking.

The canvas these tokens came from is the "HexNext design system" Design artifact in the project.
