# chat-node BASE plate: closes the shell from below, sits in the rebate of the shell rim,
# printed flat with the underside down (MJF PA12, black).
# All dimensions are named parameters in params.py (device frame: mm, Z up, front faces -Y).
import os, sys
MECH = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "/Users/drewradcliff/repos/chat-node/mech"
sys.path.insert(0, MECH)
import params as P
from params import box, cyl, cone, prism


def outline():
    c = P.LIP_T + P.BASE_CLEAR
    return (P.OUT_X0 + c, P.OUT_X1 - c, P.OUT_Y0 + c, P.OUT_Y1 - c, P.CORNER_R - c)


def build():
    x0, x1, y0, y1, r = outline()
    b = prism(x0, x1, y0, y1, r, 0, P.BASE_T)
    b = b.makeChamfer(P.BOTTOM_CHAMFER, P.edges_at_z(b, 0))
    # 45 degree bevel on the right edge: hooks over the shelf in the shell
    hx = P.IN_X1 - P.HOOK_CLEAR
    b = b.cut(P.xz_prism([(hx - 1, -1), (x1 + 1, -1), (x1 + 1, x1 + 1 - hx)],
                         -P.HOOK_LEN / 2 - 0.3, P.HOOK_LEN / 2 + 0.3))
    # raised pad under the speaker magnet (a 1 mm foam pad goes on it)
    sx, sy = P.SPK_XY
    b = b.fuse(cyl(sx, sy, P.SPK_PAD_D, P.BASE_T - 0.5, P.SPK_PAD_TOP_Z))
    # countersunk screw holes
    csk = (P.BASE_CSK_D - P.BASE_SCREW_CLEAR_D) / 2
    for x, y in P.BASE_SCREWS:
        b = b.cut(cyl(x, y, P.BASE_SCREW_CLEAR_D, -1, P.BASE_T + 1))
        b = b.cut(cone(x, y, P.BASE_CSK_D + 0.2, -0.1, P.BASE_SCREW_CLEAR_D, csk))
    # recesses for the stick-on feet
    for x, y in P.FEET:
        b = b.cut(cyl(x, y, P.FOOT_D, -1, P.FOOT_DEPTH))
    return b.removeSplitter()


def main(log):
    s = build()
    bb = s.BoundBox
    log("base valid:", s.isValid(), "solids:", len(s.Solids), "volume cm3: %.2f" % (s.Volume / 1000))
    log("base box X %.2f..%.2f  Y %.2f..%.2f  Z %.2f..%.2f" % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))
    if len(s.Solids) != 1:
        raise RuntimeError("base is not one solid")
    log("speaker pad top Z %.2f, speaker back Z %.2f: gap %.2f for a %.1f foam pad"
        % (P.SPK_PAD_TOP_Z, P.SPK_BACK_Z, P.SPK_BACK_Z - P.SPK_PAD_TOP_Z, P.FOAM_T))
    P.save("base", [("base", s, P.COL_BASE)], log)
    P.write_fab("base", "Base plate", s, {"process": "mjf", "material": "pa12", "color": "black"}, log)


if not __name__.startswith("cn_"):      # run when FreeCAD opens the file, not when another script loads it
    P.run(main, "base")
