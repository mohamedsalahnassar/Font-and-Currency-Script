# ff_inject.py
# Run via:
#   fontforge -lang=py -script ff_inject.py \
#     inFont sarDec sarSvg aedDec aedSvg outFont renameSuffix scalePct lsb rsb xNudge yNudge
import sys, traceback
import fontforge
import psMat

def log(*a): sys.stderr.write(" ".join(str(x) for x in a) + "\n")

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

    scale_pct = float(scale_pct); lsb = int(lsb); rsb = int(rsb)

    log(f"[FF] Open: {in_font}")
    f = fontforge.open(in_font)

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
    import_svg_at(f, sar_dec, sar_svg, scale_pct, lsb, rsb, x_nudge, y_nudge)

    log(f"[FF] Inject AED @ U+{int(aed_dec):04X} from {aed_svg}")
    import_svg_at(f, aed_dec, aed_svg, scale_pct, lsb, rsb, x_nudge, y_nudge)

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
