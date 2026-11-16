# chat-node enclosure: shared parameters and helpers for every part script.
#
# Device frame (all parts): millimetres, X right, Y back (front faces -Y), Z up.
# Origin: XY at the centre of the main button, Z = 0 at the underside of the
# base plate (stick-on rubber feet go below that).
import os, sys, json, math, traceback

sys.dont_write_bytecode = True
import FreeCAD as App
import Part
from FreeCAD import Vector as V

MECH = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(MECH, "build")

# ───────────────────────── overall envelope ─────────────────────────
OUT_X0, OUT_X1 = -68.9, 31.4        # outer X extent
OUT_Y0, OUT_Y1 = -25.6, 25.6        # outer Y extent
WALL = 2.4                          # side wall thickness
LID_T = 2.4                         # lid (top) thickness
BASE_T = 2.0                        # base plate thickness
CEIL_Z = 22.0                       # underside of the lid
LID_TOP_Z = CEIL_Z + LID_T          # 24.4, outer top
CORNER_R = 7.0                      # outer vertical corner radius (see report: 8 does not fit the board corner)
TOP_FILLET = 2.5                    # soft fillet on the top outer edge
BOTTOM_CHAMFER = 0.3                # light chamfer on outer bottom edges (shell rim and base)

IN_X0, IN_X1 = OUT_X0 + WALL, OUT_X1 - WALL     # -66.5 .. 29.0
IN_Y0, IN_Y1 = OUT_Y0 + WALL, OUT_Y1 - WALL     # -23.2 .. 23.2
IN_R = CORNER_R - WALL                          # inner corner radius, left corners
IN_R_RIGHT = 2.2                    # inner corner radius of the two right corners (relief for the
                                    # board corner at the back and the antenna corner at the front)

# ───────────────────────── base seat (rebate in the shell rim) ─────────────────────────
LIP_T = 1.4                         # shell wall left outside the base plate (hides the seam underneath)
BASE_CLEAR = 0.2                    # gap between base plate edge and the lip, per side
HOOK_LEN = 28.0                     # bevel hook on the right edge (Y length): holds the board-bay end
HOOK_SIZE = 1.0                     # 45 degree bevel, 1 x 1
HOOK_CLEAR = 0.25                   # horizontal gap in the bevel

# ───────────────────────── board (given) ─────────────────────────
BOARD_STEP = os.path.join(MECH, "board.step")
BOARD_BACK_Z = 17.5                 # bare back side of the PCB, faces up
PCB_T = 1.6
BOARD_COMP_Z = BOARD_BACK_Z - PCB_T # 15.9 component side, parts hang below
BOARD_X0, BOARD_X1 = -20.0, 28.0
BOARD_Y0, BOARD_Y1 = -15.0, 22.0
BOARD_R = 1.0
PCB_HOLES = [(24.8, 19.0), (-16.6, 19.0), (-13.0, -12.6)]   # H1, H2, H3
PCB_BOSS_D = 5.0
PCB_PILOT_D = 1.7                   # M2 thread-forming
PCB_PILOT_DEPTH = 5.5               # from the boss face; leaves 1.4 of lid
M2_HEAD_D = 3.8

# ───────────────────────── main switch: Kailh Choc V1 (FROM MEMORY, CHECK AGAINST A REAL SWITCH) ─────────────────────────
CHOC_BODY = 15.0                    # housing square
CHOC_HOUSING_H = 5.0                # housing top above the board back face
CHOC_STEM_H = 8.0                   # stem top above the board back face, at rest
CHOC_TRAVEL = 3.0
CHOC_STEM_X, CHOC_STEM_Y = 10.3, 4.5
CHOC_SLOT_PITCH = 5.7               # between the two keycap slots, along X
CHOC_SLOT_X, CHOC_SLOT_Y = 1.2, 3.0
CHOC_SLOT_DEPTH = 3.5

# ───────────────────────── button cap ─────────────────────────
CAP_D = 28.0
CAP_HOLE_D = 28.6                   # hole in the lid
CAP_FLANGE_D = 30.4
CAP_PROUD = 2.3                     # cap top above the lid at rest
CAP_WALL = 1.2                      # skirt wall
CAP_DISH = 0.3                      # depth of the dished top at the centre
CAP_DISH_D = 25.0
CAP_TOP_FILLET = 0.5
CAP_FLANGE_LAND = 0.5               # vertical land of the flange below its 45 degree cone
CAP_FLANGE_GAP = 0.5                # vertical lift before the flange cone meets the lid seat
LID_SEAT_R = 15.6                   # outer radius of the 45 degree seat cone under the lid hole
LID_HOLE_TOP_CHAMFER = 0.3
PRONG_X, PRONG_Y = 1.15, 2.95       # the two prongs into the Choc stem slots (fit needs a test print)
PRONG_LEN = 3.0
PRONG_TIP_CHAMFER = 0.2

CAP_CEIL_REST_Z = BOARD_BACK_Z + CHOC_STEM_H            # cap ceiling sits on the stem top: 25.5
CAP_TOP_REST_Z = LID_TOP_Z + CAP_PROUD                  # 26.7
LID_SEAT_TOP_Z = CEIL_Z + (LID_SEAT_R - CAP_HOLE_D / 2) # where the seat cone meets the hole: 23.3
CAP_FLANGE_EDGE_Z = CEIL_Z + (LID_SEAT_R - CAP_FLANGE_D / 2) - CAP_FLANGE_GAP   # 21.9
CAP_BOTTOM_REST_Z = CAP_FLANGE_EDGE_Z - CAP_FLANGE_LAND                         # 21.4

# ───────────────────────── microphone port ─────────────────────────
MIC_XY = (17.0, 10.29)
MIC_BOSS_D = 5.0
MIC_GASKET_GAP = 0.6                # boss face above the board back (foam ring, not printed)
MIC_HOLE_D = 1.5
MIC_DISH_DEPTH = 2.0                # 45 degree countersink from the lid top, shortens the tube
MIC_DISH_D = MIC_HOLE_D + 2 * MIC_DISH_DEPTH

# ───────────────────────── USB-C opening ─────────────────────────
USB_X = 3.5
USB_Z = BOARD_COMP_Z - 1.58         # 14.32
USB_MOUTH_Y = 23.0
USB_SHELL_W, USB_SHELL_H, USB_SHELL_L = 8.94, 3.16, 7.35
USB_OPEN_W, USB_OPEN_H = 13.4, 7.4  # rounded-rectangle opening through the back wall
USB_OPEN_R = 2.5                    # its corner radius (a full stadium clips the corners of a 12.35 x 6.5 overmould)
USB_OPEN_CHAMFER = 0.5              # outside edge
USB_SLIDE_W, USB_SLIDE_DEPTH = 11.0, 0.5   # shallow channel inside the back wall so the receptacle
                                           # nose (0.2 from the wall) passes when the board goes in
USB_PLUG_W, USB_PLUG_H = 12.35, 6.5        # largest overmould the USB-C spec allows
USB_PLUG_R = 1.5                           # assumed corner radius of that overmould

# ───────────────────────── ESP32 module / antenna keep-out ─────────────────────────
ANT_X0, ANT_X1 = 9.0, 27.0
ANT_Y0, ANT_Y1 = -21.0, -15.0
MODULE_Y1 = 4.5
MODULE_H = 3.2
ANT_PLASTIC_MIN = 1.5
ANT_METAL_MIN = 15.0

# ───────────────────────── speaker connector (JST PH, vertical) ─────────────────────────
JST_XY = (-15.0, -0.7)
JST_X, JST_Y, JST_H = 5.0, 8.0, 6.6
JST_PLUG_H = 10.0

# ───────────────────────── speaker: Same Sky CMS-4017-34SP (bought) ─────────────────────────
SPK_XY = (-45.0, 0.0)
SPK_D = 40.0
SPK_D_TOL = 0.3
SPK_DEPTH = 17.5
SPK_FLANGE_T = 1.7
SPK_BASKET_D = 37.0                 # stand-in envelope between flange and magnet
SPK_MAGNET_D = 23.0
SPK_SHOULDER = 11.3                 # from the front face
SPK_GASKET_T, SPK_GASKET_ID, SPK_GASKET_OD = 1.2, 36.0, 38.8
SPK_OPEN_D = 35.6                   # baffle opening
SPK_FRONT_Z = CEIL_Z - SPK_GASKET_T # 20.8
SPK_BACK_Z = SPK_FRONT_Z - SPK_DEPTH  # 3.3
SPK_TAB_ANGLE = 90.0                # solder tabs point to the back (+Y)

SPK_RING_ID = SPK_D + SPK_D_TOL + 0.3   # locating ring under the lid: 40.6
SPK_RING_WALL = 1.3                 # a hair over the 1.2 of room, so the ring runs into the left wall and the partition
SPK_RING_H = 2.5
SPK_RING_NOTCH = 14.0               # gap in the ring for the solder tabs
SPK_RECESS = 0.6                    # the lid is thinned over the 35.6 opening: free air in front of the cone
GRILLE_HOLE_D = 2.8
GRILLE_PITCH = 4.0                  # ring spacing and hole spacing: web 1.2
GRILLE_RINGS = 4

FOAM_T = 1.0                        # foam pad between magnet and base
FOAM_COMPRESSED = 0.7               # designed gap
SPK_PAD_D = 25.0                    # raised pad on the base under the magnet
SPK_PAD_TOP_Z = SPK_BACK_Z - FOAM_COMPRESSED    # 2.6

# ───────────────────────── partition ─────────────────────────
PART_X0, PART_X1 = -23.5, -21.5
NOTCH_Y, NOTCH_W, NOTCH_H = 11.5, 3.0, 2.5      # wire notch at the base side

# ───────────────────────── base screws (M2.5 thread-forming, countersunk) ─────────────────────────
BASE_SCREWS = [(-62.5, 19.2), (-62.5, -19.2), (-24.5, 19.5), (-10.0, -19.6)]
BASE_BOSS_D = 6.0
BASE_PILOT_D = 2.1
BASE_PILOT_DEPTH = 9.0
BASE_SCREW_CLEAR_D = 2.9
BASE_CSK_D = 5.2                    # 90 degree countersink
BASE_SCREW_HEAD_D = 5.0
BOSS_WEB = 3.0                      # width of the webs tying a boss to the nearest walls

# ───────────────────────── feet ─────────────────────────
FEET = [(-54.5, 18.0), (-54.5, -18.0), (22.0, 17.0), (22.0, -17.0)]
FOOT_D, FOOT_DEPTH = 8.0, 0.5

# ───────────────────────── colours ─────────────────────────
COL_SHELL = (0.16, 0.16, 0.18)      # black PA12
COL_BASE = (0.24, 0.24, 0.26)
COL_CAP = (0.93, 0.94, 0.90)        # translucent white resin
COL_SPK = (0.62, 0.63, 0.66)        # steel frame
COL_GASKET = (0.08, 0.08, 0.08)
COL_SWITCH = (0.85, 0.85, 0.82)
COL_STEM = (0.80, 0.25, 0.20)
COL_METAL = (0.78, 0.78, 0.80)
COL_CONN = (0.92, 0.90, 0.82)


# ───────────────────────── geometry helpers ─────────────────────────
def rrect(x0, x1, y0, y1, r, z=0.0):
    """Face of a rounded rectangle. r: one radius or (x0y0, x1y0, x1y1, x0y1)."""
    if not isinstance(r, (tuple, list)):
        r = (r,) * 4
    r00, r10, r11, r01 = r
    e = []

    def line(a, b):
        if (a - b).Length > 1e-9:
            e.append(Part.makeLine(a, b))

    def arc(cx, cy, rad, a0, a1):
        if rad > 1e-9:
            e.append(Part.makeCircle(rad, V(cx, cy, z), V(0, 0, 1), a0, a1))

    line(V(x0 + r00, y0, z), V(x1 - r10, y0, z)); arc(x1 - r10, y0 + r10, r10, 270, 360)
    line(V(x1, y0 + r10, z), V(x1, y1 - r11, z)); arc(x1 - r11, y1 - r11, r11, 0, 90)
    line(V(x1 - r11, y1, z), V(x0 + r01, y1, z)); arc(x0 + r01, y1 - r01, r01, 90, 180)
    line(V(x0, y1 - r01, z), V(x0, y0 + r00, z)); arc(x0 + r00, y0 + r00, r00, 180, 270)
    return Part.Face(Part.Wire(e))


def prism(x0, x1, y0, y1, r, z0, z1):
    return rrect(x0, x1, y0, y1, r, z0).extrude(V(0, 0, z1 - z0))


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cyl(x, y, d, z0, z1):
    return Part.makeCylinder(d / 2.0, z1 - z0, V(x, y, z0))


def cone(x, y, d0, z0, d1, z1):
    return Part.makeCone(d0 / 2.0, d1 / 2.0, z1 - z0, V(x, y, z0))


def xz_prism(pts, y0, y1):
    """Extrude a polygon given in (x, z) along Y."""
    w = Part.makePolygon([V(x, y0, z) for x, z in pts] + [V(pts[0][0], y0, pts[0][1])])
    return Part.Face(w).extrude(V(0, y1 - y0, 0))


def rrect_xz(xc, zc, w, h, r, y):
    """Wire of a rounded rectangle in the XZ plane at Y = y."""
    k = r * (1 - math.sqrt(0.5))
    x0, x1, z0, z1 = xc - w / 2, xc + w / 2, zc - h / 2, zc + h / 2
    p = lambda x, z: V(x, y, z)
    e = [Part.makeLine(p(x0 + r, z0), p(x1 - r, z0)),
         Part.Arc(p(x1 - r, z0), p(x1 - k, z0 + k), p(x1, z0 + r)).toShape(),
         Part.makeLine(p(x1, z0 + r), p(x1, z1 - r)),
         Part.Arc(p(x1, z1 - r), p(x1 - k, z1 - k), p(x1 - r, z1)).toShape(),
         Part.makeLine(p(x1 - r, z1), p(x0 + r, z1)),
         Part.Arc(p(x0 + r, z1), p(x0 + k, z1 - k), p(x0, z1 - r)).toShape(),
         Part.makeLine(p(x0, z1 - r), p(x0, z0 + r)),
         Part.Arc(p(x0, z0 + r), p(x0 + k, z0 + k), p(x0 + r, z0)).toShape()]
    return Part.Wire(e)


def fuse_all(shapes):
    s = shapes[0]
    for o in shapes[1:]:
        s = s.fuse(o)
    return s.removeSplitter()


def edges_at_z(shape, z, tol=1e-6):
    return [e for e in shape.Edges if all(abs(v.Z - z) < tol for v in e.Vertexes)]


def common_vol(a, b):
    c = a.common(b)
    return c.Volume if not c.isNull() else 0.0


def gap(a, b):
    return a.distToShape(b)[0]


# ───────────────────────── board and stand-ins ─────────────────────────
def board_placement():
    """board.step: origin at the switch centre, back face at Z = 0, parts at +Z.
    Rotate 180 degrees about Y (X -> -X, Z -> -Z), then lift the back face to BOARD_BACK_Z."""
    return App.Placement(V(0, 0, BOARD_BACK_Z), App.Rotation(V(0, 1, 0), 180))


def load_board():
    s = Part.Shape()
    s.read(BOARD_STEP)
    s.Placement = board_placement()
    return s


def choc_housing():
    h = CHOC_BODY / 2
    return box(-h, h, -h, h, BOARD_BACK_Z, BOARD_BACK_Z + CHOC_HOUSING_H)


def choc_stem(pressed=0.0):
    top = BOARD_BACK_Z + CHOC_STEM_H - pressed
    s = box(-CHOC_STEM_X / 2, CHOC_STEM_X / 2, -CHOC_STEM_Y / 2, CHOC_STEM_Y / 2,
            BOARD_BACK_Z + CHOC_HOUSING_H - 1.0, top)
    for sx in (-1, 1):
        cx = sx * CHOC_SLOT_PITCH / 2
        s = s.cut(box(cx - CHOC_SLOT_X / 2, cx + CHOC_SLOT_X / 2, -CHOC_SLOT_Y / 2, CHOC_SLOT_Y / 2,
                      top - CHOC_SLOT_DEPTH, top + 1))
    return s


def usb_receptacle():
    return box(USB_X - USB_SHELL_W / 2, USB_X + USB_SHELL_W / 2, USB_MOUTH_Y - USB_SHELL_L, USB_MOUTH_Y,
               USB_Z - USB_SHELL_H / 2, USB_Z + USB_SHELL_H / 2)


def usb_plug():
    """Overmould of a plugged-in cable, 0.5 short of the receptacle mouth."""
    y0 = USB_MOUTH_Y + 0.5
    return Part.Face(rrect_xz(USB_X, USB_Z, USB_PLUG_W, USB_PLUG_H, USB_PLUG_R, y0)).extrude(V(0, OUT_Y1 + 12 - y0, 0))


def jst():
    x, y = JST_XY
    return box(x - JST_X / 2, x + JST_X / 2, y - JST_Y / 2, y + JST_Y / 2, BOARD_COMP_Z - JST_H, BOARD_COMP_Z)


def jst_plug():
    x, y = JST_XY
    return box(x - JST_X / 2, x + JST_X / 2, y - JST_Y / 2, y + JST_Y / 2, BOARD_COMP_Z - JST_PLUG_H, BOARD_COMP_Z)


def antenna():
    return box(ANT_X0, ANT_X1, ANT_Y0, ANT_Y1, BOARD_COMP_Z - MODULE_H, BOARD_COMP_Z)


def tact_switches():
    return Part.makeCompound([box(x - 2, x + 2, y - 1.6, y + 1.6, BOARD_COMP_Z - 1.5, BOARD_COMP_Z)
                              for x, y in ((24.0, 13.7), (24.0, 8.0))])


def pcb_screw_heads():
    return Part.makeCompound([cyl(x, y, M2_HEAD_D, BOARD_COMP_Z - 1.6, BOARD_COMP_Z) for x, y in PCB_HOLES])


# ───────────────────────── logging, saving, fab files ─────────────────────────
class Log:
    def __init__(self, name):
        os.makedirs(BUILD, exist_ok=True)
        self.f = open(os.path.join(BUILD, name + ".log"), "w")

    def __call__(self, *a):
        msg = " ".join(str(x) for x in a)
        self.f.write(msg + "\n"); self.f.flush()
        try:
            print(msg)
        except Exception:
            pass


def load(name):
    """Import a sibling part script as a module (without running its main)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("cn_" + name, os.path.join(MECH, name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def save(doc_name, items, log, extra_objs=None, doc=None):
    """items: [(name, shape, colour)]. Saves <doc_name>.FCStd and a coloured <doc_name>.step."""
    doc = doc or App.newDocument(doc_name)
    objs = []
    for name, shape, col in items:
        if not shape.isValid():
            raise RuntimeError(name + ": shape is not valid")
        o = doc.addObject("Part::Feature", name)
        o.Shape = shape
        objs.append((o, col))
    doc.recompute()
    if App.GuiUp:
        for o, col in objs:
            o.ViewObject.ShapeColor = col
    out = [o for o, _ in objs] + list(extra_objs or [])
    doc.saveAs(os.path.join(MECH, doc_name + ".FCStd"))
    step = os.path.join(MECH, doc_name + ".step")
    if App.GuiUp:
        import ImportGui
        ImportGui.export(out, step)
        log("exported", step, "(coloured, GUI)")
    else:
        import Import
        Import.export(out, step)
        log("exported", step, "(console build: no colours)")
    return doc


def features(shape):
    try:
        bb = shape.optimalBoundingBox(False, False)
    except Exception:
        bb = shape.BoundBox
    size = sorted([bb.XLength, bb.YLength, bb.ZLength], reverse=True)
    return {"volume_cm3": round(shape.Volume / 1000.0, 3), "area_cm2": round(shape.Area / 100.0, 2),
            "size_x_mm": round(size[0], 2), "size_y_mm": round(size[1], 2), "size_z_mm": round(size[2], 2)}


def write_fab(part, title, shape, options, log):
    fab = {"kind": "3dp", "name": title, "source": part + ".step", "qty": 1,
           "options": options, "features": features(shape)}
    with open(os.path.join(MECH, part + ".fab.json"), "w") as f:
        json.dump(fab, f, indent=2); f.write("\n")
    log("fab:", json.dumps(fab["features"]))


def run(main, name):
    """Run a part script's main, log errors, and leave FreeCAD (the GUI would keep running)."""
    log = Log(name)
    code = 0
    try:
        main(log)
        log("OK")
    except Exception:
        log(traceback.format_exc())
        code = 1
    log.f.close()
    sys.stdout.flush()
    os._exit(code)
