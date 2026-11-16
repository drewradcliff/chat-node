# chat-node BUTTON CAP: translucent cap on the Kailh Choc stem, guided by the lid hole and
# held captive by a flange under the lid. Printed top-down in clear/white resin (SLA).
# Modelled in the device frame at its REST position; build(pressed=3.0) gives it fully pressed.
# All dimensions are named parameters in params.py.
import os, sys
MECH = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "/Users/drewradcliff/repos/chat-node/mech"
sys.path.insert(0, MECH)
import params as P
from params import V, box
import Part


def build(pressed=0.0, prongs=True):
    ro, ri, rf = P.CAP_D / 2, P.CAP_D / 2 - P.CAP_WALL, P.CAP_FLANGE_D / 2
    top, ceil = P.CAP_TOP_REST_Z, P.CAP_CEIL_REST_Z
    zf, zb = P.CAP_FLANGE_EDGE_Z, P.CAP_BOTTOM_REST_Z
    # profile (r, z): top, skirt, 45 degree flange cone, land, hollow inside
    pts = [(0, top), (ro, top), (ro, zf + (rf - ro)), (rf, zf), (rf, zb), (ri, zb), (ri, ceil), (0, ceil)]
    w = Part.makePolygon([V(r, 0, z) for r, z in pts] + [V(0, 0, top)])
    cap = Part.Face(w).revolve(V(0, 0, 0), V(0, 0, 1), 360)
    cap = cap.makeFillet(P.CAP_TOP_FILLET, [e for e in P.edges_at_z(cap, top)])
    # dished top
    rd, d = P.CAP_DISH_D / 2, P.CAP_DISH
    rs = (rd * rd + d * d) / (2 * d)
    cap = cap.cut(Part.makeSphere(rs, V(0, 0, top - d + rs)))
    # two prongs into the keycap slots of the stem
    if prongs:
        for sx in (-1, 1):
            cx = sx * P.CHOC_SLOT_PITCH / 2
            p = box(cx - P.PRONG_X / 2, cx + P.PRONG_X / 2, -P.PRONG_Y / 2, P.PRONG_Y / 2,
                    ceil - P.PRONG_LEN, ceil + 0.2)
            p = p.makeChamfer(P.PRONG_TIP_CHAMFER, P.edges_at_z(p, ceil - P.PRONG_LEN))
            cap = cap.fuse(p)
    cap = cap.removeSplitter()
    if pressed:
        cap.translate(V(0, 0, -pressed))
    return cap


def main(log):
    s = build()
    bb = s.BoundBox
    log("cap valid:", s.isValid(), "solids:", len(s.Solids), "volume cm3: %.3f" % (s.Volume / 1000))
    log("cap box X %.2f..%.2f  Y %.2f..%.2f  Z %.2f..%.2f (rest)" % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))
    if len(s.Solids) != 1:
        raise RuntimeError("cap is not one solid")
    t_rim = P.CAP_TOP_REST_Z - P.CAP_CEIL_REST_Z
    log("top thickness: %.2f at the rim, %.2f at the centre of the dish" % (t_rim, t_rim - P.CAP_DISH))
    log("top at rest %.2f = %.2f proud of the lid; at full press %.2f = %.2f below the lid top"
        % (P.CAP_TOP_REST_Z, P.CAP_TOP_REST_Z - P.LID_TOP_Z, P.CAP_TOP_REST_Z - P.CHOC_TRAVEL,
           P.LID_TOP_Z - P.CAP_TOP_REST_Z + P.CHOC_TRAVEL))
    log("flange bottom: %.2f at rest, %.2f at full press (board back at %.2f)"
        % (P.CAP_BOTTOM_REST_Z, P.CAP_BOTTOM_REST_Z - P.CHOC_TRAVEL, P.BOARD_BACK_Z))
    P.save("button_cap", [("button_cap", s, P.COL_CAP)], log)
    P.write_fab("button_cap", "Button cap", s,
                {"process": "sla", "material": "clear_resin", "color": "translucent"}, log)


if not __name__.startswith("cn_"):      # run when FreeCAD opens the file, not when another script loads it
    P.run(main, "button_cap")
