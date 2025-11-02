#!/usr/bin/env bash
set -euo pipefail

die(){ echo "ERR: $*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
Usage:
  ./inject_symbols.sh --fonts-dir <dir> --sar-svg <file.svg> --aed-svg <file.svg> --out-dir <dir>
                      [--sar-code U+20C1] [--aed-code U+20C3]
                      [--rename-suffix "-ENBD"]
                      [--scale 67] [--lsb 53] [--rsb 106]
                      [--x 0] [--y 0]
                      [--ref-code U+0030] [--vfit top|center|baseline] [--top-pad 0] [--bottom-pad 0]
USAGE
}

FONTS_DIR=""; OUT_DIR=""
SAR_SVG=""; AED_SVG=""
SAR_CODE="U+20C1"; AED_CODE="U+20C3"
RENAME_SUFFIX=""
SCALE="67"; LSB="53"; RSB="106"
XNUDGE="0"; YNUDGE="0"
REF_CODE="U+0030"; VFIT="top"; TOP_PAD="0"; BOTTOM_PAD="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fonts-dir)     FONTS_DIR="${2:-}"; shift 2;;
    --out-dir)       OUT_DIR="${2:-}"; shift 2;;
    --sar-svg)       SAR_SVG="${2:-}"; shift 2;;
    --aed-svg)       AED_SVG="${2:-}"; shift 2;;
    --sar-code)      SAR_CODE="${2:-}"; shift 2;;
    --aed-code)      AED_CODE="${2:-}"; shift 2;;
    --rename-suffix) RENAME_SUFFIX="${2:-}"; shift 2;;
    --scale)         SCALE="${2:-67}"; shift 2;;
    --lsb)           LSB="${2:-53}"; shift 2;;
    --rsb)           RSB="${2:-106}"; shift 2;;
    --x)             XNUDGE="${2:-0}"; shift 2;;
    --y)             YNUDGE="${2:-0}"; shift 2;;
    --ref-code)      REF_CODE="${2:-U+0030}"; shift 2;;
    --vfit)          VFIT="${2:-top}"; shift 2;;
    --top-pad)       TOP_PAD="${2:-0}"; shift 2;;
    --bottom-pad)    BOTTOM_PAD="${2:-0}"; shift 2;;
    -h|--help)       usage; exit 0;;
    *) die "Unknown arg: $1 (use --help)";;
  esac
done

[[ -n "$FONTS_DIR" && -d "$FONTS_DIR" ]] || { usage; die "--fonts-dir not found"; }
[[ -n "$OUT_DIR" ]] || { usage; die "--out-dir is required"; }
[[ -f "$SAR_SVG" ]] || { usage; die "--sar-svg not found"; }
[[ -f "$AED_SVG" ]] || { usage; die "--aed-svg not found"; }
command -v fontforge >/dev/null 2>&1 || die "fontforge not found"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
PY_SCRIPT="$SCRIPT_DIR/ff_inject.py"
[[ -f "$PY_SCRIPT" ]] || die "ff_inject.py not found in $SCRIPT_DIR"

hex_to_dec(){ u="$1"; u="$(printf '%s' "$u" | tr '[:lower:]' '[:upper:]')"; u="${u#U+}"; u="${u#0X}"; case "$u" in (*[!0-9A-F]*) die "Invalid codepoint: $1";; esac; printf '%d' "$((16#$u))"; }
SAR_DEC="$(hex_to_dec "$SAR_CODE")"; AED_DEC="$(hex_to_dec "$AED_CODE")"

abspath(){ local p="$1"; if [ -d "$p" ]; then (cd "$p" && pwd -P); else (cd "$(dirname "$p")" && printf "%s/%s\n" "$(pwd -P)" "$(basename "$p")"); fi; }
FONTS_DIR="$(abspath "$FONTS_DIR")"; OUT_DIR="$(abspath "$OUT_DIR")"; SAR_SVG="$(abspath "$SAR_SVG")"; AED_SVG="$(abspath "$AED_SVG")"
mkdir -p "$OUT_DIR"

# FontForge Python availability (suppress plugin discovery noise)
env FONTFORGE_NO_PLUGINS=1 fontforge -lang=py -c 'import fontforge' >/dev/null 2>&1 \
  || die "FontForge lacks Python support; reinstall (brew install fontforge)"

found=0
while IFS= read -r -d '' font; do
  found=1
  base="$(basename "$font")"; name="${base%.*}"; ext="${base##*.}"
  out="$OUT_DIR/${name}-injected.${ext}"
  echo "[*] Inject: $base → $(basename "$out")"
  if env FONTFORGE_NO_PLUGINS=1 fontforge -lang=py -script "$PY_SCRIPT" \
      "$font" "$SAR_DEC" "$SAR_SVG" "$AED_DEC" "$AED_SVG" "$out" "$RENAME_SUFFIX" \
      "$SCALE" "$LSB" "$RSB" "$XNUDGE" "$YNUDGE" "$REF_CODE" "$VFIT" "$TOP_PAD" "$BOTTOM_PAD"; then
    [[ -f "$out" ]] && echo "[+] OK: $(basename "$out")" || echo "[-] No output for $base"
  else
    echo "[-] Failed for $base"
  fi

done < <(find "$FONTS_DIR" -type f \( -iname "*.ttf" -o -iname "*.otf" \) -print0)

[[ $found -eq 1 ]] || echo "[!] No .ttf/.otf files found under $FONTS_DIR"
echo "Done."
