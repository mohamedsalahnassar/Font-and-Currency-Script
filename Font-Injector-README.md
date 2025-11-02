# Font Injector Utility

This tool wraps a FontForge Python script to inject SAR and AED glyphs into existing fonts. It standardizes scaling, spacing, and renaming for batches of font files.

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

### Arguments
- `--fonts-dir` / `--out-dir`: Input folder of source fonts and destination for injected fonts.
- `--sar-svg` / `--aed-svg`: SVG paths for the SAR and AED symbols.
- `--sar-code` / `--aed-code`: Target Unicode code points (defaults: `U+20C1`, `U+20C3`).
- `--scale`, `--lsb`, `--rsb`: Base scaling and side bearings applied to both glyphs.
- `--x`, `--y`: Final horizontal/vertical nudges after spacing is applied.
- `--rename-suffix`: Optional suffix appended to generated font names.

## Vertical Auto-Fit (New)

New flags in `ff_inject.py` (plumbed via `inject_symbols.sh`):

- `--ref-code U+XXXX`  (default `U+0030` = Latin '0'; use `U+0660` for Arabic-Indic digits)
- `--vfit top|center|baseline`  (default `top` = align symbol's top with the reference top)
- `--top-pad N`, `--bottom-pad N`  (font units) to leave tiny buffers
- `--x N`, `--y N`  final nudges after spacing

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
