# STAND-IN for the bought speaker Same Sky CMS-4017-34SP and its gasket ring. NOT a part to order
# or print: it only shows the envelope for fit checks. Firing up, in the device frame.
# All dimensions are named parameters in params.py.
import os, sys, math
MECH = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "/Users/drewradcliff/repos/chat-node/mech"
sys.path.insert(0, MECH)
import params as P
from params import V, box, cyl, cone
import Part


def build():
    """Returns (speaker, gasket)."""
    x, y = P.SPK_XY
    zf = P.SPK_FRONT_Z
    z_fl = zf - P.SPK_FLANGE_T
    z_sh = zf - P.SPK_SHOULDER
    spk = cyl(x, y, P.SPK_D, z_fl, zf)                                   # front flange
    spk = spk.fuse(cyl(x, y, P.SPK_BASKET_D, z_sh, z_fl))                # basket envelope
    spk = spk.fuse(cyl(x, y, P.SPK_MAGNET_D, P.SPK_BACK_Z, z_sh))        # magnet
    spk = spk.cut(cone(x, y, 8.0, zf - 4.0, P.SPK_OPEN_D - 1.0, zf + 0.01))   # cone/diaphragm dish
    # two solder tabs under the rim
    tabs = []
    for dx in (-5.0, 5.0):
        t = box(dx - 1.4, dx + 1.4, P.SPK_D / 2 - 1.2, P.SPK_D / 2 - 0.7, z_fl - 4.0, z_fl + 0.1)
        t = t.fuse(box(dx - 1.4, dx + 1.4, P.SPK_BASKET_D / 2 - 0.2, P.SPK_D / 2 - 0.7, z_fl - 0.6, z_fl + 0.1))
        tabs.append(t)
    tabs = P.fuse_all(tabs)
    tabs.rotate(V(0, 0, 0), V(0, 0, 1), P.SPK_TAB_ANGLE - 90.0)
    tabs.translate(V(x, y, 0))
    spk = spk.fuse(tabs).removeSplitter()
    gasket = cyl(x, y, P.SPK_GASKET_OD, zf, zf + P.SPK_GASKET_T).cut(cyl(x, y, P.SPK_GASKET_ID, zf - 1, zf + 2))
    return spk, gasket


def main(log):
    spk, gasket = build()
    bb = spk.BoundBox
    log("speaker stand-in valid:", spk.isValid(), gasket.isValid())
    log("speaker box X %.2f..%.2f  Y %.2f..%.2f  Z %.2f..%.2f" % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))
    P.save("speaker_standin", [("speaker_standin", spk, P.COL_SPK), ("speaker_gasket_standin", gasket, P.COL_GASKET)], log)


if not __name__.startswith("cn_"):      # run when FreeCAD opens the file, not when another script loads it
    P.run(main, "speaker_standin")
