# Font Currency Symbol Injector (FontForge CLI)

Inject the **Saudi Riyal sign (SAR, U+20C1)** and an **AED (Dirham) symbol** into one or more TTF/OTF fonts from **SVG** source files — with precise, repeatable control over **scale**, **left/right side bearings**, and **x/y nudges**.  
Works cross‑platform via **FontForge** (Python API). Outputs new `*-injected.ttf|otf` files; originals remain untouched.

> **Note:** This README assumes AED is mapped to **U+20C3** (per your configuration). If you prefer a PUA (e.g., U+E000), pass it via `--aed-code U+E000`.

---

## What you get

- Batch‑inject SAR (`U+20C1`) and AED (`U+20C3` by default) glyphs into every `.ttf`/`.otf` under a folder (recursive).
- Deterministic metrics per glyph:
  - **Scale** the contours (e.g., `--scale 67` = 67%).
  - Set **LSB/RSB** (left/right side bearings) exactly (in font units).
  - Optional **x/y nudges** applied after spacing for visual fine‑tuning.
- Auto‑hint / auto‑instr the new glyphs to clear “blue” indicators in FontForge.
- Optional **family rename suffix** (license‑friendly when modifying Roboto/OFL fonts).
- No third‑party Python deps; just calls `fontforge` (CLI).

---

## Requirements

- **FontForge** with Python support
  - macOS: `brew install fontforge`
- The two files in the same directory:
  - `inject_symbols.sh` (bash wrapper)
  - `ff_inject.py` (FontForge Python script)
- Your SVGs: `SAR.svg` (U+20C1), `AED.svg` (mapped to `U+20C3` by default).

Optional (to silence FontForge plugin warnings): the wrapper already sets `FONTFORGE_NO_PLUGINS=1` when invoking FontForge.

---

## Files

```
.
├─ inject_symbols.sh      # Wrapper: scans fonts folder and calls FontForge (Python)
├─ ff_inject.py           # Does the actual glyph import/cleanup/metrics/hinting
└─ assets/
   ├─ SAR.svg             # Your Saudi Riyal sign vector (filled outlines)
   └─ AED.svg             # Your Dirham symbol vector (filled outlines)
```

---

## Usage

```bash
./inject_symbols.sh \
  --fonts-dir ./fonts_in \
  --sar-svg ./assets/SAR.svg \
  --aed-svg ./assets/AED.svg \
  --out-dir ./fonts_out \
  --sar-code U+20C1 --aed-code U+20C3 \
  --scale 80 --lsb 50 --rsb 100 \
  --x 15 --y 20
```

The script will recurse under `--fonts-dir`, process any `.ttf/.otf`, and write results to `--out-dir` (originals untouched). Each output is named `<original>-injected.ttf|otf`.

### Arguments (wrapper)

| Flag | Description | Default |
|---|---|---|
| `--fonts-dir PATH` | Root folder containing input fonts (recursive). | **required** |
| `--out-dir PATH` | Output folder for injected fonts. | **required** |
| `--sar-svg FILE.svg` | SVG for **SAR** glyph shape. | **required** |
| `--aed-svg FILE.svg` | SVG for **AED** glyph shape. | **required** |
| `--sar-code U+XXXX` | Code point for SAR (Saudi Riyal). | `U+20C1` |
| `--aed-code U+XXXX` | Code point for AED (Dirham). | `U+20C3` |
| `--rename-suffix STR` | Appended to family/full/PS names (license‑safe rename). | *empty* |
| `--scale N` | Scale percentage for contours (e.g., `67`, `80`). | `67` |
| `--lsb N` | Target **left** side bearing (font units). | `53` |
| `--rsb N` | Target **right** side bearing (font units). | `106` |
| `--x N` | Final **x nudge** after spacing (units). | `0` |
| `--y N` | Final **y nudge** after spacing (units). | `0` |
| `--ref-code U+XXXX` | Glyph used as the vertical reference for auto-fit (e.g., `U+0030` = digit "0"). | `U+0030` |
| `--vfit top|center|baseline` | How to align SAR/AED vertically relative to the reference glyph. | `top` |
| `--top-pad N` / `--bottom-pad N` | Extra vertical breathing room when auto-fitting (font units). | `0` / `0` |

> **Units:** `--lsb`, `--rsb`, `--x`, `--y` use the font’s units-per-em (UPM). If your font is UPM 2048 (not 1000), the same numeric values appear proportionally smaller on screen — adjust accordingly. The Python injector automatically rescales spacing/nudge numbers for each font based on its ascent, descent, UPM and underline metrics so that tweaks dialled in for the reference font carry over to other families. The `--scale` percentage stays exactly as you specify it.

### What the Python script does (per glyph)

1. Imports the SVG into the target code point.
2. Robust cleanup: `addExtrema → canonicalContours → canonicalStart → correctDirection → removeOverlap (fallback simplify) → round`.
3. **Deterministic spacing:**
   - Normalize outline so `xmin = 0`.
   - Set advance width = `LSB + (bbox width) + RSB`.
   - Translate contours by `+LSB` so the *visible* left margin equals `LSB`.
   - Correction pass ensures LSB/RSB land on the requested values.
4. Apply final **x/y** nudge (post‑spacing).
5. `autoHint()` and `autoInstr()` the injected glyphs.
6. Generate the new font at the output path you specified.

It prints BEFORE/AFTER metrics so you can verify that your `LSB/RSB` actually took effect.

---

## Vertical Auto-Fit (why & how)

Currency marks rarely share the same cap-height or alignment across families. Without intervention, they land at different tops or
sink below the baseline depending on the font. The injector now auto-fits both SAR and AED against a reference glyph so they look
native wherever you drop them.

- `--ref-code U+XXXX` picks the glyph whose vertical metrics you trust. The default `U+0030` targets the Latin digit “0”, but you
  can swap to `U+0660` (Arabic-Indic zero) or a custom placeholder to match another script.
- `--vfit top|center|baseline` tells the script how to align the symbol after scaling:
  - `top` (default) keeps the top of the symbol flush with the reference’s top (minus optional padding).
  - `center` vertically centers the symbol within the reference glyph’s box.
  - `baseline` locks the bottom of the symbol to the reference baseline (plus optional padding).
- `--top-pad` / `--bottom-pad` let you reserve breathing room when `top`/`baseline` would otherwise touch.
- Final `--x` / `--y` nudges still run after auto-fit so you can micro-adjust optical balance without re-exporting SVGs.

### Updated example

```bash
./inject_symbols.sh \
  --fonts-dir ./fonts_in \
  --sar-svg ./assets/SAR.svg \
  --aed-svg ./assets/AED.svg \
  --out-dir ./fonts_out \
  --sar-code U+20C1 --aed-code U+20C3 \
  --scale 80 --lsb 50 --rsb 100 \
  --x 15 --y 20 \
  --ref-code U+0030 --vfit top --top-pad 0 --bottom-pad 0
```

---

## SVG Prep Checklist (important)

To avoid “Internal Error (overlap)…” from FontForge and ensure clean contours:

- Convert **strokes to outlines** (Illustrator: *Object → Path → Outline Stroke*; Figma: *Flatten*).
- **Unite** shapes (Pathfinder **Unite/Union**) so there are no overlapping subpaths.
- Ensure **closed paths**, no masks/filters/gradients.
- Export **Plain SVG** (no transforms).
- Make the glyph roughly at visual cap‑height vs digits; fine‑tune with `--scale` and `--x/--y` later.

The script will still try to repair tricky paths, but clean SVGs yield best results.

---

## Examples

### 1) Default SAR/AED with rename and gentle scaling
```bash
./inject_symbols.sh \
  --fonts-dir ./fonts_in \
  --sar-svg ./assets/SAR.svg \
  --aed-svg ./assets/AED.svg \
  --out-dir ./fonts_out \
  --rename-suffix "-ENBD" \
  --scale 67 --lsb 53 --rsb 106
```

### 2) AED on a PUA instead (if you prefer)
```bash
./inject_symbols.sh \
  --fonts-dir ./fonts_in \
  --sar-svg ./assets/SAR.svg \
  --aed-svg ./assets/AED.svg \
  --out-dir ./fonts_out \
  --sar-code U+20C1 \
  --aed-code U+E000 \
  --scale 80 --lsb 40 --rsb 100 --x -15
```

### 3) Tighten left margin; small baseline lift
```bash
./inject_symbols.sh \
  --fonts-dir ./fonts_in \
  --sar-svg ./assets/SAR.svg \
  --aed-svg ./assets/AED.svg \
  --out-dir ./fonts_out \
  --sar-code U+20C1 --aed-code U+20C3 \
  --scale 78 --lsb 35 --rsb 110 --x -8 --y 12
```

---

## Platform Notes

### iOS
- Use **UIFontDescriptor cascade** to add your tiny symbols font as a fallback (no need to replace SF).  
- If you injected directly into your app’s base fonts, just load those; fallback still works.

### Android
- When you set a custom `Typeface`, **system fallback stops**. Ensure the Typeface (or its **FontFamily** chain) contains the glyphs:
  - Put your micro **symbols font first** in a `res/font` **family XML**, then Roboto/Noto weights you use.
  - Or **span** just the currency mark with `TypefaceSpan` using your symbols TTF.
- Verify quickly with:
  ```kotlin
  val p = Paint().apply { typeface = ResourcesCompat.getFont(ctx, R.font.your_money_font) }
  Log.d("GLYPH", "has SAR: " + p.hasGlyph("\u20C1"))
  Log.d("GLYPH", "has AED: " + p.hasGlyph("\u20C3")) // or \uE000 if you used PUA
  ```

---

## Troubleshooting

- **“Undefined variable: import”** → FontForge ran the script as **PE** not Python. The wrapper calls `fontforge -lang=py -script ...`. Use the provided `.sh` and keep `ff_inject.py` separate.
- **`pkg_resources not found` / plugin warnings** → harmless; the wrapper sets `FONTFORGE_NO_PLUGINS=1` to silence it.
- **Internal Error (overlap)** → your SVG has overlaps/open paths. The script attempts cleanup; if it persists, unify paths and re‑export SVG as “plain”.
- **`--lsb/--rsb` seem to do nothing** → this README’s version moves **contours**, not just bearings. Check the printed AFTER metrics; if unchanged, you may be opening the wrong output file or a different weight.
- **Symbols not showing on Android** → the view’s Typeface (family) doesn’t include your glyphs. Use a `@font` family with your symbols font first, or span the mark.
- **Still tofu after rebuild** → uninstall the app (font cache), bump font filenames, and make sure output is **.ttf** (not CFF `.otf`) if targeting older Android.

---

## Licensing

- Roboto (Apache 2.0) and most OFL fonts allow modification **if you rename** the family/PostScript names. Use `--rename-suffix "-YourOrg"`.
- Proprietary fonts may **forbid** modification — check their EULA before injecting.

---

## Notes & Tips

- LSB/RSB are in **font units** (UPM). If your font uses 2048 UPM, values like `53/106` are relatively small; scale up if needed.
- `--x/--y` are applied **after** spacing. Effective left margin becomes `LSB + x`.
- To force TTF quadratic curves before generate (for older Android), you can add this near the end of `ff_inject.py`:
  ```python
  try:
      f.selection.all()
      f.removeOverlap()
      f.layers['Fore'].isQuadratic = True
  except: pass
  ```

---

## Credits

- Powered by **FontForge** (CLI, Python mode). No third‑party Python libraries are required.
- Script design focuses on **deterministic spacing** and **minimal APK/IPA size** (use a micro symbols font or inject into your app’s existing fonts).
