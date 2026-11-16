# chat-node SHELL: lid plus all four side walls in one piece, printed lid-down (MJF PA12, black).
# All dimensions are named parameters in params.py (device frame: mm, Z up, front faces -Y).
import os, sys, math
MECH = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "/Users/drewradcliff/repos/chat-node/mech"
sys.path.insert(0, MECH)
import params as P
from params import V, box, cyl, cone, prism
import Part


def cavity(z0, z1):
    return prism(P.IN_X0, P.IN_X1, P.IN_Y0, P.IN_Y1, (P.IN_R, P.IN_R_RIGHT, P.IN_R_RIGHT, P.IN_R), z0, z1)


def rebate_outline():
    """(x0, x1, y0, y1, r) of the rebate that takes the base plate."""
    return (P.OUT_X0 + P.LIP_T, P.OUT_X1 - P.LIP_T, P.OUT_Y0 + P.LIP_T, P.OUT_Y1 - P.LIP_T, P.CORNER_R - P.LIP_T)


def grille_holes():
    """Concentric rings of holes over the speaker opening: [(x, y)]."""
    cx, cy = P.SPK_XY
    pts = [(cx, cy)]
    for k in range(1, P.GRILLE_RINGS + 1):
        r = k * P.GRILLE_PITCH
        n = int(math.pi / math.asin(P.GRILLE_PITCH / (2 * r)) + 1e-9)   # chord between holes >= pitch
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * (k % 2)) / n
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def build():
    H = P.LID_TOP_Z
    # outer body with soft top edge and light bottom chamfer
    body = prism(P.OUT_X0, P.OUT_X1, P.OUT_Y0, P.OUT_Y1, P.CORNER_R, 0, H)
    body = body.makeFillet(P.TOP_FILLET, P.edges_at_z(body, H))
    body = body.makeChamfer(P.BOTTOM_CHAMFER, P.edges_at_z(body, 0))
    # hollow it; rebate for the base plate at the rim
    body = body.cut(cavity(-1, P.CEIL_Z))
    rx0, rx1, ry0, ry1, rr = rebate_outline()
    body = body.cut(prism(rx0, rx1, ry0, ry1, rr, -1, P.BASE_T))

    # ── features hanging from the lid, clipped to the cavity ──
    inner = []
    # partition between speaker chamber and board bay, with the wire notch at the base side
    part = box(P.PART_X0, P.PART_X1, P.OUT_Y0, P.OUT_Y1, P.BASE_T, P.CEIL_Z)
    part = part.cut(box(P.PART_X0 - 1, P.PART_X1 + 1, P.NOTCH_Y - P.NOTCH_W / 2, P.NOTCH_Y + P.NOTCH_W / 2,
                        P.BASE_T - 1, P.BASE_T + P.NOTCH_H))
    inner.append(part)
    # PCB bosses and microphone boss
    for x, y in P.PCB_HOLES:
        inner.append(cyl(x, y, P.PCB_BOSS_D, P.BOARD_BACK_Z, P.CEIL_Z))
    mx, my = P.MIC_XY
    inner.append(cyl(mx, my, P.MIC_BOSS_D, P.BOARD_BACK_Z + P.MIC_GASKET_GAP, P.CEIL_Z))
    # base screw bosses: full-height columns tied to the two nearest walls
    w = P.BOSS_WEB / 2
    for x, y in P.BASE_SCREWS:
        inner.append(cyl(x, y, P.BASE_BOSS_D, P.BASE_T, P.CEIL_Z))
        ywall = P.OUT_Y1 if y > 0 else P.OUT_Y0
        inner.append(box(x - w, x + w, min(y, ywall), max(y, ywall), P.BASE_T, P.CEIL_Z))
        if x < P.IN_X0 + 2 * P.BASE_BOSS_D:                      # corner boss: tie to the left wall too
            inner.append(box(P.OUT_X0, x, y - w, y + w, P.BASE_T, P.CEIL_Z))
    # speaker locating ring (open towards the solder tabs)
    sx, sy = P.SPK_XY
    ring = cyl(sx, sy, P.SPK_RING_ID + 2 * P.SPK_RING_WALL, P.CEIL_Z - P.SPK_RING_H, P.CEIL_Z)
    ring = ring.cut(cyl(sx, sy, P.SPK_RING_ID, P.CEIL_Z - P.SPK_RING_H - 1, P.CEIL_Z + 1))
    a = math.radians(P.SPK_TAB_ANGLE)
    nb = box(0, P.SPK_RING_ID, -P.SPK_RING_NOTCH / 2, P.SPK_RING_NOTCH / 2, P.CEIL_Z - P.SPK_RING_H - 1, P.CEIL_Z + 1)
    nb.rotate(V(0, 0, 0), V(0, 0, 1), P.SPK_TAB_ANGLE)
    nb.translate(V(sx, sy, 0))
    inner.append(ring.cut(nb))
    clip = cavity(P.BASE_T, P.CEIL_Z + 0.5)
    for f in inner:
        v0 = body.Volume
        body = body.fuse(f.common(clip))
        if body.Volume < v0:
            raise RuntimeError("fusing an inner feature failed")

    # bevel hook shelf in the rebate on the right: the base plate's bevelled edge hooks over it
    hx = P.IN_X1
    body = body.fuse(P.xz_prism([(hx, 0), (hx + P.HOOK_SIZE + 0.2, 0), (hx + P.HOOK_SIZE + 0.2, P.HOOK_SIZE),
                                 (hx + P.HOOK_SIZE, P.HOOK_SIZE)], -P.HOOK_LEN / 2, P.HOOK_LEN / 2))

    # ── cuts ──
    cuts = []
    # button hole, 45 degree seat cone underneath (captures the cap flange), small top chamfer
    cuts.append(cyl(0, 0, P.CAP_HOLE_D, P.CEIL_Z - 1, H + 1))
    cuts.append(cone(0, 0, 2 * P.LID_SEAT_R, P.CEIL_Z, P.CAP_HOLE_D, P.LID_SEAT_TOP_Z))
    c = P.LID_HOLE_TOP_CHAMFER
    cuts.append(cone(0, 0, P.CAP_HOLE_D, H - c, P.CAP_HOLE_D + 2 * c + 0.2, H + 0.1))
    # speaker: thinned lid over the baffle opening, grille holes
    cuts.append(cyl(sx, sy, P.SPK_OPEN_D, P.CEIL_Z - 0.01, P.CEIL_Z + P.SPK_RECESS))
    for x, y in grille_holes():
        cuts.append(cyl(x, y, P.GRILLE_HOLE_D, P.CEIL_Z, H + 1))
    # microphone tube and countersunk dish from the top
    cuts.append(cyl(mx, my, P.MIC_HOLE_D, P.BOARD_BACK_Z, H + 1))
    cuts.append(cone(mx, my, P.MIC_HOLE_D, H - P.MIC_DISH_DEPTH, P.MIC_DISH_D + 0.2, H + 0.1))
    # pilot holes
    for x, y in P.PCB_HOLES:
        cuts.append(cyl(x, y, P.PCB_PILOT_D, P.BOARD_BACK_Z - 1, P.BOARD_BACK_Z + P.PCB_PILOT_DEPTH))
    for x, y in P.BASE_SCREWS:
        cuts.append(cyl(x, y, P.BASE_PILOT_D, P.BASE_T - 1, P.BASE_T + P.BASE_PILOT_DEPTH))
    # USB-C: rounded opening through the back wall, chamfered outside, plus the slide-in channel inside
    cuts.append(Part.Face(P.rrect_xz(P.USB_X, P.USB_Z, P.USB_OPEN_W, P.USB_OPEN_H, P.USB_OPEN_R, P.IN_Y1 - 1))
                .extrude(V(0, P.WALL + 2, 0)))
    ch = P.USB_OPEN_CHAMFER
    cuts.append(Part.makeLoft([P.rrect_xz(P.USB_X, P.USB_Z, P.USB_OPEN_W, P.USB_OPEN_H, P.USB_OPEN_R, P.OUT_Y1 - ch),
                               P.rrect_xz(P.USB_X, P.USB_Z, P.USB_OPEN_W + 2 * ch + 0.2, P.USB_OPEN_H + 2 * ch + 0.2,
                                          P.USB_OPEN_R + ch + 0.1, P.OUT_Y1 + 0.1)], True))
    cuts.append(box(P.USB_X - P.USB_SLIDE_W / 2, P.USB_X + P.USB_SLIDE_W / 2, P.IN_Y1 - 1, P.IN_Y1 + P.USB_SLIDE_DEPTH,
                    P.BASE_T, P.USB_Z))
    for c in cuts:
        body = body.cut(c)
    return body.removeSplitter()


def main(log):
    s = build()
    log("shell valid:", s.isValid(), "solids:", len(s.Solids), "volume cm3: %.2f" % (s.Volume / 1000))
    bb = s.BoundBox
    log("shell box X %.2f..%.2f  Y %.2f..%.2f  Z %.2f..%.2f" % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))
    if len(s.Solids) != 1:
        raise RuntimeError("shell is not one solid")
    n = len(grille_holes())
    open_a = n * math.pi * P.GRILLE_HOLE_D ** 2 / 4
    log("grille: %d holes of %.1f, open area %.0f mm2 = %.0f%% of the %.1f opening, web %.2f"
        % (n, P.GRILLE_HOLE_D, open_a, 100 * open_a / (math.pi * P.SPK_OPEN_D ** 2 / 4), P.SPK_OPEN_D,
           P.GRILLE_PITCH - P.GRILLE_HOLE_D))
    log("mic tube length: %.2f (hole %.1f)" % (P.LID_TOP_Z - P.MIC_DISH_DEPTH - P.BOARD_BACK_Z - P.MIC_GASKET_GAP,
                                                P.MIC_HOLE_D))
    log("lid left over PCB pilot holes: %.2f" % (P.LID_TOP_Z - P.BOARD_BACK_Z - P.PCB_PILOT_DEPTH))
    P.save("shell", [("shell", s, P.COL_SHELL)], log)
    P.write_fab("shell", "Shell", s, {"process": "mjf", "material": "pa12", "color": "black"}, log)


if not __name__.startswith("cn_"):      # run when FreeCAD opens the file, not when another script loads it
    P.run(main, "shell")
