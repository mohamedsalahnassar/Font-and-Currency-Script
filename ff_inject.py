# ff_inject.py
# Run via:
#   fontforge -lang=py -script ff_inject.py \
#     inFont sarDec sarSvg aedDec aedSvg outFont renameSuffix scalePct lsb rsb xNudge yNudge
import sys, traceback
import fontforge
import psMat

# Metrics that the default CLI parameters were tuned against.  These values
# correspond to the "reference" font where the manual --scale/--lsb/--rsb/--x/--y
# settings were determined to look correct.  When we process a different font we
# normalise the caller supplied numbers against this baseline so that we can
# derive per-font values that respect the target font's ascent/descent/em size,
# underline position and underline thickness.
BASELINE_METRICS = dict(
    upm=2048.0,
    ascent=1536.0,
    descent=512.0,
    underline_pos=-200.0,
    underline_thickness=100.0,
    line_gap=0.0,  # reference font had no extra line gap
)

def log(*a): sys.stderr.write(" ".join(str(x) for x in a) + "\n")


def safe_ratio(numerator, denominator, fallback=1.0):
    try:
        denominator = float(denominator)
        if abs(denominator) < 1e-9:
            return float(fallback)
        return float(numerator) / denominator
    except Exception:
        return float(fallback)


def collect_font_metrics(fnt):
    """Return the subset of font metrics we care about for normalising values."""
    metrics = {}
    metrics["upm"] = float(getattr(fnt, "em", getattr(fnt, "upm", BASELINE_METRICS["upm"])))
    metrics["ascent"] = float(getattr(fnt, "ascent", BASELINE_METRICS["ascent"]))
    metrics["descent"] = float(getattr(fnt, "descent", BASELINE_METRICS["descent"]))
    metrics["underline_pos"] = float(getattr(fnt, "upos", BASELINE_METRICS["underline_pos"]))
    metrics["underline_thickness"] = float(getattr(fnt, "uwidth", BASELINE_METRICS["underline_thickness"]))

    line_gap = None
    for attr in ("hhea_linegap", "os2_typolinegap", "os2_winascentadd"):
        if hasattr(fnt, attr):
            try:
                line_gap = float(getattr(fnt, attr))
                break
            except Exception:
                continue
    if line_gap is None:
        line_gap = BASELINE_METRICS["line_gap"]
    metrics["line_gap"] = line_gap

    return metrics


def derive_adjusted_metrics(user_values, font_metrics, baseline=BASELINE_METRICS):
    """Map CLI supplied values (tuned for baseline metrics) to this font."""

    # Horizontal measurements (scale%, LSB/RSB, x nudge) primarily track the
    # font's units-per-em.  We also fold in the total vertical height so that a
    # font with a non-standard ascent/descent split still preserves overall
    # proportions.
    upm_ratio = safe_ratio(font_metrics["upm"], baseline["upm"])
    total_height_ratio = safe_ratio(
        font_metrics["ascent"] + font_metrics["descent"],
        baseline["ascent"] + baseline["descent"],
    )
    horiz_ratio = (upm_ratio + total_height_ratio) / 2.0

    adjusted = {}
    adjusted["scale_pct"] = float(user_values["scale_pct"]) * total_height_ratio
    adjusted["lsb"] = round(float(user_values["lsb"]) * horiz_ratio)
    adjusted["rsb"] = round(float(user_values["rsb"]) * horiz_ratio)
    adjusted["x_nudge"] = round(float(user_values["x_nudge"]) * horiz_ratio)

    # Vertical nudges need to respect how the font allocates ascent/descent, and
    # also the underline metrics (position + thickness).  We derive a blended
    # ratio that weights these contributions so that small manual tweaks made for
    # the baseline font stay visually consistent across different metric
    # configurations.
    y_val = float(user_values["y_nudge"])
    if abs(y_val) < 1e-6:
        adjusted["y_nudge"] = 0
    else:
        ascent_ratio = safe_ratio(font_metrics["ascent"], baseline["ascent"])
        descent_ratio = safe_ratio(font_metrics["descent"], baseline["descent"])
        underline_ratio = safe_ratio(
            abs(font_metrics["underline_pos"]),
            abs(baseline["underline_pos"]),
        )
        thickness_ratio = safe_ratio(
            font_metrics["underline_thickness"],
            baseline["underline_thickness"],
        )
        line_gap_ratio = safe_ratio(
            font_metrics["ascent"] + font_metrics["descent"] + font_metrics["line_gap"],
            baseline["ascent"] + baseline["descent"] + baseline["line_gap"],
        )

        if y_val > 0:
            dominant_ratio = ascent_ratio
        else:
            dominant_ratio = descent_ratio

        blended_ratio = (dominant_ratio + underline_ratio + thickness_ratio + line_gap_ratio) / 4.0
        adjusted["y_nudge"] = round(y_val * blended_ratio)

    return adjusted

def bbox(g):
    try:    return g.boundingBox()  # (xmin, ymin, xmax, ymax)
    except: return (0, 0, g.width, 0)

def measure(g):
    xmin, ymin, xmax, ymax = bbox(g)
    width = g.width
    lsb = xmin
    rsb = width - xmax
    return dict(xmin=xmin, xmax=xmax, width=width, lsb=lsb, rsb=rsb, ymin=ymin, ymax=ymax)

def safe_cleanup(g):
    for fn in (
        lambda: g.addExtrema(),
        lambda: g.canonicalContours(),
        lambda: g.canonicalStart(),
        lambda: g.correctDirection(),
        lambda: g.removeOverlap(),
        lambda: g.round(1),
    ):
        try: fn()
        except: pass

def apply_metrics_exact(g, scale_pct, target_lsb, target_rsb):
    """
    Deterministic spacing:
      1) Scale outline
      2) Translate outline so xmin = 0
      3) width = target_lsb + bbox_w + target_rsb
      4) Translate outline by +target_lsb
      5) Correction pass to hit exact LSB/RSB
    """
    m0 = measure(g); log(f"[FF] BEFORE  lsb={m0['lsb']:.2f} rsb={m0['rsb']:.2f} width={m0['width']:.2f}")

    # 1) Scale
    s = float(scale_pct) / 100.0
    if abs(s - 1.0) > 1e-6:
        g.transform(psMat.scale(s, s))

    # 2) Normalize xmin -> 0
    xmin, _, xmax, _ = bbox(g)
    if abs(xmin) > 0.001:
        g.transform(psMat.translate(-xmin, 0))

    # 3) width to enforce rsb
    xmin2, _, xmax2, _ = bbox(g)  # xmin2 ~ 0
    box_w = xmax2 - xmin2
    g.width = int(round(float(target_lsb) + box_w + float(target_rsb)))

    # 4) enforce lsb by moving outline (not bearings)
    if int(target_lsb) != 0:
        g.transform(psMat.translate(int(target_lsb), 0))

    # 5) correction pass
    m1 = measure(g)
    dx_l = int(round(float(target_lsb) - m1["lsb"]))
    if dx_l:
        g.transform(psMat.translate(dx_l, 0))
    m2 = measure(g)
    if abs(float(target_rsb) - m2["rsb"]) > 0.5:
        g.width = int(round(m2["xmax"] + float(target_rsb)))

def import_svg_at(fnt, codepoint, svg_path, scale_pct, lsb, rsb, x_nudge, y_nudge):
    cp = int(codepoint)
    g = fnt.createChar(cp)
    try: g.clear()
    except: pass

    g.importOutlines(svg_path)
    safe_cleanup(g)

    # spacing first
    apply_metrics_exact(g, scale_pct=scale_pct, target_lsb=lsb, target_rsb=rsb)

    # final nudges (post-spacing)
    dx = int(float(x_nudge)); dy = int(float(y_nudge))
    if dx or dy:
        g.transform(psMat.translate(dx, dy))

    mF = measure(g); log(f"[FF] AFTER   lsb={mF['lsb']:.2f} rsb={mF['rsb']:.2f} width={mF['width']:.2f} nudged(x={dx},y={dy})")

def main():
    # Expect 12 args after script name
    if len(sys.argv) < 13:
        sys.stderr.write("Usage: ff_inject.py inFont sarDec sarSvg aedDec aedSvg outFont renameSuffix scalePct lsb rsb xNudge yNudge\n")
        sys.exit(1)

    (in_font, sar_dec, sar_svg, aed_dec, aed_svg,
     out_font, rename_suffix, scale_pct, lsb, rsb, x_nudge, y_nudge) = sys.argv[1:13]

    log(f"[FF] Open: {in_font}")
    f = fontforge.open(in_font)

    base_metrics = BASELINE_METRICS
    font_metrics = collect_font_metrics(f)
    log("[FF] Metrics baseline→target:")
    log(
        f"      upm {base_metrics['upm']:.1f} → {font_metrics['upm']:.1f}",
        f"ascent {base_metrics['ascent']:.1f} → {font_metrics['ascent']:.1f}",
        f"descent {base_metrics['descent']:.1f} → {font_metrics['descent']:.1f}",
    )
    log(
        f"      underline-pos {base_metrics['underline_pos']:.1f} → {font_metrics['underline_pos']:.1f}",
        f"underline-thickness {base_metrics['underline_thickness']:.1f} → {font_metrics['underline_thickness']:.1f}",
        f"line-gap {base_metrics['line_gap']:.1f} → {font_metrics['line_gap']:.1f}",
    )

    user_values = dict(
        scale_pct=float(scale_pct),
        lsb=float(lsb),
        rsb=float(rsb),
        x_nudge=float(x_nudge),
        y_nudge=float(y_nudge),
    )
    adjusted_values = derive_adjusted_metrics(user_values, font_metrics)
    log(
        f"[FF] Adjusted metrics → scale {adjusted_values['scale_pct']:.2f}%",
        f"lsb {adjusted_values['lsb']}",
        f"rsb {adjusted_values['rsb']}",
        f"x {adjusted_values['x_nudge']}",
        f"y {adjusted_values['y_nudge']}",
    )

    if rename_suffix:
        try:
            fam = (f.familyname or "UnknownFamily") + rename_suffix
            fn  = (f.fullname   or "UnknownFull")   + rename_suffix
            ps  = ((f.fontname  or "UnknownPS")     + rename_suffix).replace(" ", "")
            f.familyname, f.fullname, f.fontname = fam, fn, ps
            try: f.appendSFNTName('English (US)', 'Family', fam)
            except: pass
            try: f.appendSFNTName('English (US)', 'Fullname', fn)
            except: pass
            try: f.appendSFNTName('English (US)', 'PostScript Name', ps)
            except: pass
            log(f"[FF] Renamed → Family='{fam}' Full='{fn}' PS='{ps}'")
        except Exception as e:
            log(f"[FF] Rename warning:", e)

    log(f"[FF] Inject SAR @ U+{int(sar_dec):04X} from {sar_svg}")
    import_svg_at(
        f,
        sar_dec,
        sar_svg,
        adjusted_values["scale_pct"],
        adjusted_values["lsb"],
        adjusted_values["rsb"],
        adjusted_values["x_nudge"],
        adjusted_values["y_nudge"],
    )

    log(f"[FF] Inject AED @ U+{int(aed_dec):04X} from {aed_svg}")
    import_svg_at(
        f,
        aed_dec,
        aed_svg,
        adjusted_values["scale_pct"],
        adjusted_values["lsb"],
        adjusted_values["rsb"],
        adjusted_values["x_nudge"],
        adjusted_values["y_nudge"],
    )

    # optional hinting/instruction
    try:
        f.selection.none()
        f.selection.select(int(sar_dec))
        f.selection.select(int(aed_dec), 'more')
        try: f.autoHint()
        except: pass
        try: f.autoInstr()
        except: pass
    except: pass

    log(f"[FF] Generate:", out_font)
    try:
        f.generate(out_font)
    except Exception as e:
        log("[FF] Generate failed:", e)
        traceback.print_exc(file=sys.stderr); sys.exit(2)
    finally:
        try: f.close()
        except: pass
    log("[FF] Done.")

if __name__ == "__main__":
    main()
