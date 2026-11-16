# chat-node ASSEMBLY: shell, base, button cap, speaker stand-in and the board (board.step) in the
# device frame, plus the interference checks. Stand-ins (names ending _standin) cover what the board
# STEP lacks: the Choc switch and the USB-C receptacle. Not a part to order.
import os, sys, math
MECH = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "/Users/drewradcliff/repos/chat-node/mech"
sys.path.insert(0, MECH)
import params as P
from params import V, common_vol, gap
import FreeCAD as App
import Part

EXPLODE = 0.0        # set > 0 for a look inside: lifts shell, cap and board; writes assembly_exploded.* instead


def checks(log, shell, base, cap, cap_pressed, cap_body_pressed, spk, gasket, board):
    bad = []

    def chk(name, vol, limit=1e-4):
        ok = vol <= limit
        log("  %-52s common volume %.4f mm3  %s" % (name, vol, "ok" if ok else "INTERFERENCE"))
        if not ok:
            bad.append(name)

    def need(name, value, minimum):
        ok = value >= minimum - 1e-6
        log("  %-52s %.2f mm (need %.2f)  %s" % (name, value, minimum, "ok" if ok else "TOO SMALL"))
        if not ok:
            bad.append(name)

    body = max(board.Solids, key=lambda s: s.Volume)
    bb = body.BoundBox
    log("board body in the device frame: X %.2f..%.2f  Y %.2f..%.2f  Z %.2f..%.2f"
        % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))
    housing, stem = P.choc_housing(), P.choc_stem()
    usb, plug, ant = P.usb_receptacle(), P.usb_plug(), P.antenna()
    extras = Part.makeCompound([housing, usb, P.jst_plug(), P.tact_switches(), P.pcb_screw_heads()])

    log("BOARD")
    chk("board (STEP) vs shell", common_vol(board, shell))
    chk("board stand-ins (switch, USB, JST plug, tacts, screw heads) vs shell", common_vol(extras, shell))
    chk("board (STEP) vs base", common_vol(board, base))
    chk("board stand-ins vs base", common_vol(extras, base))
    # the PCB touches its three bosses by design: measure the clearance to everything else
    walls = shell.cut(P.box(P.OUT_X0, P.OUT_X1, P.OUT_Y0, P.OUT_Y1, P.BOARD_BACK_Z - 0.01, P.CEIL_Z - 0.01))
    need("PCB outline to the shell walls", gap(body, walls), 1.0)
    need("lowest board part (JST plug) to the base", gap(P.jst_plug(), base), 1.0)
    need("JST connector to the partition", P.JST_XY[0] - P.JST_X / 2 - P.PART_X1, 1.0)
    log("BUTTON CAP")
    chk("cap vs shell, at rest", common_vol(cap, shell))
    chk("cap vs shell, full press", common_vol(cap_pressed, shell))
    need("cap to shell, at rest", gap(cap, shell), 0.25)
    need("cap to shell, full press", gap(cap_pressed, shell), 0.25)
    chk("cap vs board, full press", common_vol(cap_pressed, board))
    need("cap flange to the board back, full press", gap(cap_pressed, body), 0.3)
    chk("cap vs switch housing + stem (prongs in slots), at rest", common_vol(cap, housing.fuse(stem)))
    chk("cap (without prongs) vs switch housing, full press", common_vol(cap_body_pressed, housing))
    log("  cap ceiling to switch housing top at full press: %.2f mm (they meet: the housing is the hard stop)"
        % gap(cap_body_pressed, housing))
    need("cap skirt to switch housing corners (radial)",
         P.CAP_D / 2 - P.CAP_WALL - P.CHOC_BODY / 2 * math.sqrt(2), 1.0)
    h3 = P.PCB_HOLES[2]
    need("cap flange to the H3 boss (radial)", math.hypot(*h3) - P.PCB_BOSS_D / 2 - P.CAP_FLANGE_D / 2, 0.3)
    need("cap flange to the microphone boss (radial)",
         math.hypot(*P.MIC_XY) - P.MIC_BOSS_D / 2 - P.CAP_FLANGE_D / 2, 0.3)
    log("  cap lift before the flange cone meets the lid seat: %.2f mm" % P.CAP_FLANGE_GAP)
    log("SPEAKER")
    chk("speaker vs shell", common_vol(spk, shell))
    chk("gasket vs shell", common_vol(gasket, shell))
    chk("speaker vs base", common_vol(spk, base))
    need("speaker rim to the locating ring (radial, nominal)", (P.SPK_RING_ID - P.SPK_D) / 2, 0.15)
    need("speaker to shell (anywhere)", gap(spk, shell), 0.15)
    log("  magnet to the base pad: %.2f mm, filled by the %.1f mm foam pad" % (gap(spk, base), P.FOAM_T))
    log("  free air in front of the speaker's front face: %.2f mm (gasket %.1f + lid recess %.1f)"
        % (P.SPK_GASKET_T + P.SPK_RECESS, P.SPK_GASKET_T, P.SPK_RECESS))
    log("USB-C")
    chk("receptacle vs shell", common_vol(usb, shell))
    chk("plug overmould (%.2f x %.1f, r %.1f) vs shell" % (P.USB_PLUG_W, P.USB_PLUG_H, P.USB_PLUG_R), common_vol(plug, shell))
    need("receptacle to shell", gap(usb, shell), 0.2)
    need("plug overmould to the opening", gap(plug, shell), 0.2)
    log("  opening %.1f x %.1f centred X %.2f Z %.2f; receptacle %.2f x %.2f centred X %.2f Z %.2f; "
        "mouth %.1f inside the outer wall surface"
        % (P.USB_OPEN_W, P.USB_OPEN_H, P.USB_X, P.USB_Z, P.USB_SHELL_W, P.USB_SHELL_H, P.USB_X, P.USB_Z,
           P.OUT_Y1 - P.USB_MOUTH_Y))
    log("ANTENNA KEEP-OUT")
    need("antenna to shell (plastic)", gap(ant, shell), P.ANT_PLASTIC_MIN)
    need("antenna to base (plastic)", gap(ant, base), P.ANT_PLASTIC_MIN)
    need("antenna to button cap, full press (plastic)", gap(ant, cap_pressed), P.ANT_PLASTIC_MIN)
    for i, (x, y) in enumerate(P.BASE_SCREWS):
        scr = P.cyl(x, y, P.BASE_SCREW_HEAD_D, 0, P.BASE_T + P.BASE_PILOT_DEPTH)
        need("antenna to base screw %d at (%.1f, %.1f) (metal)" % (i + 1, x, y), gap(ant, scr), P.ANT_METAL_MIN)
    for i, (x, y) in enumerate(P.PCB_HOLES):
        scr = P.cyl(x, y, P.M2_HEAD_D, P.BOARD_COMP_Z - 1.6, P.CEIL_Z)
        need("antenna to PCB screw H%d (metal)" % (i + 1), gap(ant, scr), P.ANT_METAL_MIN)
    need("antenna to speaker (metal)", gap(ant, spk), P.ANT_METAL_MIN)
    log("  note: the Choc switch (board part, metal contacts) is %.1f mm from the antenna region"
        % gap(ant, housing))
    log("BASE / SHELL")
    chk("base vs shell", common_vol(base, shell))
    log("  base to shell: %.2f mm (seated on the rim step, the bosses and the partition)" % gap(base, shell))
    log("RESULT: " + ("all checks pass" if not bad else "FAILED: " + "; ".join(bad)))
    return bad


def main(log):
    shell = P.load("shell").build()
    base = P.load("base").build()
    capm = P.load("button_cap")
    cap, cap_pressed = capm.build(), capm.build(pressed=P.CHOC_TRAVEL)
    cap_body_pressed = capm.build(pressed=P.CHOC_TRAVEL, prongs=False)
    spk, gasket = P.load("speaker_standin").build()
    board = P.load_board()
    for n, s in (("shell", shell), ("base", base), ("cap", cap), ("speaker", spk), ("gasket", gasket)):
        if not s.isValid():
            raise RuntimeError(n + " is not valid")

    bad = checks(log, shell, base, cap, cap_pressed, cap_body_pressed, spk, gasket, board)

    name = "assembly_exploded" if EXPLODE else "assembly"
    doc = App.newDocument(name)
    lift = V(0, 0, EXPLODE)
    up = lambda s, k: s.translated(lift * k) if EXPLODE else s
    items = [("shell", up(shell, 2), P.COL_SHELL), ("base", base, P.COL_BASE),
             ("button_cap", up(cap, 3), P.COL_CAP),
             ("speaker_standin", up(spk, 1), P.COL_SPK), ("speaker_gasket_standin", up(gasket, 1), P.COL_GASKET),
             ("choc_housing_standin", up(P.choc_housing(), 1), P.COL_SWITCH),
             ("choc_stem_standin", up(P.choc_stem(), 1), P.COL_STEM),
             ("usb_receptacle_standin", up(P.usb_receptacle(), 1), P.COL_METAL),
             ("jst_standin", up(P.jst(), 1), P.COL_CONN)]
    # the board keeps its colours when it comes in through the GUI importer
    App.ParamGet("User parameter:BaseApp/Preferences/Mod/Import").SetInt("ImportMode", 0)
    before = set(o.Name for o in doc.Objects)
    if App.GuiUp:
        import ImportGui
        ImportGui.insert(P.BOARD_STEP, doc.Name)
    else:
        import Import
        Import.insert(P.BOARD_STEP, doc.Name)
    new = [o for o in doc.Objects if o.Name not in before]
    roots = [o for o in new if not any(p in new for p in o.InList)]
    pl = P.board_placement()
    if EXPLODE:
        pl = App.Placement(lift, App.Rotation()).multiply(pl)
    for o in roots:
        o.Placement = pl.multiply(o.Placement)
    doc.recompute()
    log("board imported: %d objects, %d root(s)" % (len(new), len(roots)))
    P.save(name, items, log, extra_objs=roots, doc=doc)
    if bad:
        raise RuntimeError("interference checks failed")


if not __name__.startswith("cn_"):      # run when FreeCAD opens the file, not when another script loads it
    P.run(main, "assembly")
