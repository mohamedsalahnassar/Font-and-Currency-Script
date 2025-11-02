# ff_inject.py
# Run via FontForge:
#   fontforge -lang=py -script ff_inject.py \
#     inFont sarDec sarSvg aedDec aedSvg outFont renameSuffix \
#     scalePct lsb rsb xNudge yNudge refCode vfitMode topPad bottomPad
import sys, traceback
import fontforge
import psMat


def log(*a): sys.stderr.write(" ".join(str(x) for x in a) + "\n")


def codepoint_from_str(s):
    s = s.strip().upper()
    if s.startswith("U+"): s = s[2:]
    if s.startswith("0X"): s = s[2:]
    return int(s, 16)


def bbox(g):
    try:    return g.boundingBox()  # (xmin,ymin,xmax,ymax)
    except: return (0, 0, g.width, 0)


def measure(g):
    xmin, ymin, xmax, ymax = bbox(g)
    width = g.width
    lsb = xmin
    rsb = width - xmax
    return dict(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax,
                width=width, lsb=lsb, rsb=rsb, height=ymax-ymin)


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


def vertical_autofit(g, ref_g, mode="top", top_pad=0, bottom_pad=0):
    """
    Uniformly scale & shift g to match ref_g vertically.
    mode:
      - "top": align g.top to ref.top - top_pad, height to (ref.height - pads)
      - "center": center g within ref bbox height (pads respected)
      - "baseline": align g.bottom to ref.bottom + bottom_pad
    """
    rm = measure(ref_g)
    gm = measure(g)
    ref_top, ref_bot = rm["ymax"], rm["ymin"]
    ref_h = max(1.0, (ref_top - ref_bot) - float(top_pad) - float(bottom_pad))

    g_h = max(1.0, gm["height"])
    scale = ref_h / g_h

    g.transform(psMat.scale(scale, scale))
    gm = measure(g)

    if mode == "top":
        desired_top = ref_top - float(top_pad)
        dy = desired_top - gm["ymax"]
    elif mode == "center":
        ref_mid = (ref_top + ref_bot) / 2.0
        g_mid  = (gm["ymax"] + gm["ymin"]) / 2.0
        dy = ref_mid - g_mid
    elif mode == "baseline":
        desired_bottom = ref_bot + float(bottom_pad)
        dy = desired_bottom - gm["ymin"]
    else:
        dy = 0

    if abs(dy) > 0.001:
        g.transform(psMat.translate(0, dy))


def apply_metrics_exact(g, scale_pct, target_lsb, target_rsb):
    """
    Deterministic horizontal spacing:
      1) base scale
      2) normalize xmin -> 0
      3) width = LSB + bbox_w + RSB
      4) translate outline by +LSB
      5) correction pass to hit exact LSB/RSB
    """
    m0 = measure(g); log(f"[FF] BEFORE  lsb={m0['lsb']:.2f} rsb={m0['rsb']:.2f} width={m0['width']:.2f}")

    # 1) base scale
    s = float(scale_pct) / 100.0
    if abs(s - 1.0) > 1e-6:
        g.transform(psMat.scale(s, s))

    # 2) normalize xmin -> 0
    xmin, _, xmax, _ = bbox(g)
    if abs(xmin) > 0.001:
        g.transform(psMat.translate(-xmin, 0))

    # 3) enforce RSB via width
    xmin2, _, xmax2, _ = bbox(g)  # xmin2 ≈ 0
    box_w = xmax2 - xmin2
    g.width = int(round(float(target_lsb) + box_w + float(target_rsb)))

    # 4) shift outline to get LSB
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


def import_svg_at(fnt, codepoint, svg_path, base_scale, lsb, rsb,
                  x_nudge, y_nudge, ref_code, vfit_mode, top_pad, bottom_pad):
    cp = int(codepoint)
    g = fnt.createChar(cp)
    try: g.clear()
    except: pass

    g.importOutlines(svg_path)
    safe_cleanup(g)

    # Vertical auto-fit (before horizontal spacing)
    try:
        ref_g = fnt[ref_code]
    except Exception:
        ref_g = None
    if ref_g is not None and vfit_mode.lower() in ("top","center","baseline"):
        vertical_autofit(g, ref_g, vfit_mode.lower(), float(top_pad), float(bottom_pad))

    # Horizontal spacing
    apply_metrics_exact(g, scale_pct=base_scale, target_lsb=lsb, target_rsb=rsb)

    # Final nudges
    dx = int(float(x_nudge)); dy = int(float(y_nudge))
    if dx or dy:
        g.transform(psMat.translate(dx, dy))

    mF = measure(g); log(f"[FF] AFTER   lsb={mF['lsb']:.2f} rsb={mF['rsb']:.2f} width={mF['width']:.2f} (dx={dx},dy={dy})")


def main():
    # Expect 16 args after script name
    if len(sys.argv) < 17:
        sys.stderr.write("Usage: ff_inject.py inFont sarDec sarSvg aedDec aedSvg outFont renameSuffix scalePct lsb rsb xNudge yNudge refCode vfitMode topPad bottomPad\n")
        sys.exit(1)

    (in_font, sar_dec, sar_svg, aed_dec, aed_svg,
     out_font, rename_suffix, scale_pct, lsb, rsb, x_nudge, y_nudge,
     ref_code_str, vfit_mode, top_pad, bottom_pad) = sys.argv[1:17]

    scale_pct = float(scale_pct); lsb = int(lsb); rsb = int(rsb)
    ref_code  = codepoint_from_str(ref_code_str)
    top_pad   = float(top_pad); bottom_pad = float(bottom_pad)

    log(f"[FF] Open: {in_font}")
    f = fontforge.open(in_font)

    # Optional rename
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
            log(f"[FF] Renamed → Family='%s' Full='%s' PS='%s'" % (fam, fn, ps))
        except Exception as e:
            log("[FF] Rename warning:", e)

    # Inject SAR & AED
    log(f"[FF] Inject SAR @ U+{int(sar_dec):04X} from {sar_svg}")
    import_svg_at(f, int(sar_dec), sar_svg, scale_pct, lsb, rsb,
                  x_nudge, y_nudge, ref_code, vfit_mode, top_pad, bottom_pad)

    log(f"[FF] Inject AED @ U+{int(aed_dec):04X} from {aed_svg}")
    import_svg_at(f, int(aed_dec), aed_svg, scale_pct, lsb, rsb,
                  x_nudge, y_nudge, ref_code, vfit_mode, top_pad, bottom_pad)

    # Hint/instruct just the injected glyphs
    try:
        f.selection.none()
        f.selection.select(int(sar_dec))
        f.selection.select(int(aed_dec), 'more')
        try: f.autoHint()
        except: pass
        try: f.autoInstr()
        except: pass
    except: pass

    log(f"[FF] Generate: %s" % out_font)
    try:
        f.generate(out_font)
    except Exception as e:
        log("[FF] Generate failed:", e); traceback.print_exc(file=sys.stderr); sys.exit(2)
    finally:
        try: f.close()
        except: pass
    log("[FF] Done.")


if __name__ == "__main__":
    main()
