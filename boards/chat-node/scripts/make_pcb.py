"""Builds chat-node.kicad_pcb from the schematic netlist: placement, outline, routing, zones.
Run with KiCad's Python:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 make_pcb.py
Coordinates below are mm relative to the centre of the main switch (SW1), as seen on the
component side (F.Cu). +x is right, +y is down (toward the antenna end of the module)."""
import os, sys, math
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sexp import parse, find, first  # noqa: E402
import layout  # noqa: E402

PROJ = os.path.normpath(os.path.join(HERE, '..'))
NET = os.path.join(PROJ, 'build', 'chat-node.net')
OUT = os.path.join(PROJ, 'chat-node.kicad_pcb')
SYSFP = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'
OX, OY = 130.0, 100.0


def P(x, y):
    return VECTOR2I(FromMM(OX + x), FromMM(OY + y))


def load_netlist():
    t = parse(open(NET).read())
    comps = {}
    for c in find(first(t, 'components'), 'comp'):
        ref = first(c, 'ref')[1]
        props = {p[1][1]: p[2][1] for p in find(c, 'property') if len(p) > 2}
        fields = first(c, 'fields')
        if fields:
            for f in find(fields, 'field'):
                props[first(f, 'name')[1]] = f[2] if len(f) > 2 else ''
        comps[ref] = dict(value=first(c, 'value')[1], fp=first(c, 'footprint')[1],
                          tstamp=first(c, 'tstamps')[1], props=props)
    nets = {}
    for n in find(first(t, 'nets'), 'net'):
        name = first(n, 'name')[1]
        for node in find(n, 'node'):
            nets[(first(node, 'ref')[1], first(node, 'pin')[1])] = name
    return comps, nets


def main():
    comps, padnets = load_netlist()
    board = pcbnew.BOARD()
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.SetBoardThickness(FromMM(1.6))
    ds.m_TrackMinWidth = FromMM(0.15)
    ds.m_MinClearance = FromMM(0.15)
    ds.m_ViasMinSize = FromMM(0.45)
    ds.m_MinThroughDrill = FromMM(0.3)
    ds.m_CopperEdgeClearance = FromMM(0.3)
    ds.m_HoleToHoleMin = FromMM(0.25)
    ds.m_HoleClearance = FromMM(0.2)
    ds.SetAuxOrigin(P(0, 0))
    ds.m_ViasMinAnnularWidth = FromMM(0.075)
    ds.m_SilkClearance = FromMM(0.05)
    try:
        nc = ds.m_NetSettings.GetDefaultNetclass()
        nc.SetClearance(FromMM(0.15))
        nc.SetTrackWidth(FromMM(0.2))
        nc.SetViaDiameter(FromMM(0.6))
        nc.SetViaDrill(FromMM(0.3))
    except Exception as e:
        print('netclass:', e)

    nets = {}

    def net(name):
        if name not in nets:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
            nets[name] = ni
        return nets[name]

    # ---- footprints
    missing = []
    for ref, (x, y, rot) in layout.PLACE.items():
        if ref not in comps:
            missing.append(ref)
            continue
        c = comps[ref]
        lib, name = c['fp'].split(':')
        libdir = os.path.join(PROJ, 'lib', 'chat-node.pretty') if lib == 'chat-node' else os.path.join(SYSFP, lib + '.pretty')
        fp = pcbnew.FootprintLoad(libdir, name)
        if fp is None:
            raise SystemExit('footprint not found: ' + c['fp'])
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(ref)
        fp.SetValue(c['value'])
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        fp.SetPath(pcbnew.KIID_PATH('/' + c['tstamp']))
        for k, v in c['props'].items():
            if k in ('Reference', 'Value', 'Footprint', 'Datasheet', 'Description') or k.startswith('ki_'):
                continue
            try:
                fp.SetField(k, v)
            except Exception:
                pass
        for fld in fp.GetFields():
            if fld.GetName() not in ('Reference', 'Value'):
                fld.SetVisible(False)
        for pad in fp.Pads():
            n = padnets.get((ref, pad.GetNumber()))
            if n:
                pad.SetNet(net(n))
        if ref == 'U1':   # module thermal vias: 0.2 mm drill in the library part, opened to 0.3 mm (no-extra-cost drill)
            for pad in fp.Pads():
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and ToMM(pad.GetDrillSize().x) < 0.3:
                    pad.SetDrillSize(VECTOR2I(FromMM(0.3), FromMM(0.3)))
        if ref == 'J1':
            for pad in fp.Pads():
                if pad.GetNetname() == 'GND' and pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        for pad in fp.Pads():
            if (ref, pad.GetNumber()) in layout.SOLID_PADS:
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        if ref in layout.DNP:
            fp.SetDNP(True)
        if ref in layout.NO_POS:
            fp.SetExcludedFromPosFiles(True)
        # tidy silkscreen reference
        r = fp.Reference()
        if ref in layout.HIDE_REF:
            r.SetVisible(False)
        else:
            r.SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8)))
            r.SetTextThickness(FromMM(0.12))
            if ref in layout.REFPOS:
                rx, ry, ra = layout.REFPOS[ref]
                r.SetPosition(P(rx, ry))
                r.SetTextAngleDegrees(ra)
        board.Add(fp)
    unplaced = sorted(set(comps) - set(layout.PLACE))
    if unplaced or missing:
        print('UNPLACED:', unplaced, 'NOT IN NETLIST:', missing)

    # ---- outline
    def edge_line(a, b):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a)); s.SetEnd(P(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.1))
        board.Add(s)

    def edge_arc(c, start, mid, end):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(P(*start), P(*mid), P(*end))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.1))
        board.Add(s)

    x0, y0, x1, y1 = layout.OUTLINE
    r = layout.CORNER_R
    k = r * (1 - math.sqrt(0.5))
    edge_line((x0 + r, y0), (x1 - r, y0)); edge_line((x1, y0 + r), (x1, y1 - r))
    edge_line((x1 - r, y1), (x0 + r, y1)); edge_line((x0, y1 - r), (x0, y0 + r))
    edge_arc(None, (x0, y0 + r), (x0 + k, y0 + k), (x0 + r, y0))
    edge_arc(None, (x1 - r, y0), (x1 - k, y0 + k), (x1, y0 + r))
    edge_arc(None, (x1, y1 - r), (x1 - k, y1 - k), (x1 - r, y1))
    edge_arc(None, (x0 + r, y1), (x0 + k, y1 - k), (x0, y1 - r))

    # ---- tracks and vias
    LAYER = {'F': pcbnew.F_Cu, 'B': pcbnew.B_Cu}
    for name, lay, w, pts in layout.TRACKS:
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(P(*a)); t.SetEnd(P(*b))
            t.SetWidth(FromMM(w)); t.SetLayer(LAYER[lay]); t.SetNet(net(name))
            board.Add(t)
    for name, x, y, size, drill in layout.VIAS:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(P(x, y))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetDrill(FromMM(drill))
        try:
            v.SetWidth(pcbnew.F_Cu, FromMM(size))
        except TypeError:
            v.SetWidth(FromMM(size))
        v.SetNet(net(name))
        board.Add(v)

    # ---- silkscreen text
    for txt, x, y, size, lay, ang in layout.TEXTS:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(txt)
        t.SetPosition(P(x, y))
        t.SetLayer(pcbnew.F_SilkS if lay == 'F' else pcbnew.B_SilkS)
        t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
        t.SetTextThickness(FromMM(max(0.1, size * 0.15)))
        t.SetTextAngleDegrees(ang)
        if lay == 'B':
            t.SetMirrored(True)
        board.Add(t)

    # ---- ground pours
    for lay in (() if os.environ.get('NOZONE') else (pcbnew.F_Cu, pcbnew.B_Cu)):
        z = pcbnew.ZONE(board)
        z.SetLayer(lay)
        z.SetNet(net('GND'))
        z.SetAssignedPriority(0)
        z.SetLocalClearance(FromMM(0.25))
        z.SetMinThickness(FromMM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(FromMM(0.25))
        z.SetThermalReliefSpokeWidth(FromMM(0.35))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        ol = z.Outline()
        ol.NewOutline()
        for (x, y) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ol.Append(FromMM(OX + x), FromMM(OY + y))
        z.SetZoneName('GND_' + ('F' if lay == pcbnew.F_Cu else 'B'))
        board.Add(z)
    if not os.environ.get('NOZONE'):
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    pcbnew.SaveBoard(OUT, board)
    print('saved', OUT)

    # ---- pad dump for planning
    with open(os.path.join(PROJ, 'build', 'pads.txt'), 'w') as f:
        for fp in sorted(board.GetFootprints(), key=lambda q: q.GetReference()):
            for pad in fp.Pads():
                p = pad.GetPosition()
                sz = pad.GetSize(pcbnew.F_Cu) if hasattr(pad, 'GetSize') else None
                bb = pad.GetBoundingBox()
                f.write('%-5s %-4s %-24s (%7.3f,%7.3f)  bbox x %.2f..%.2f y %.2f..%.2f\n' % (
                    fp.GetReference(), pad.GetNumber(), pad.GetNetname(), ToMM(p.x) - OX, ToMM(p.y) - OY,
                    ToMM(bb.GetLeft()) - OX, ToMM(bb.GetRight()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetBottom()) - OY))


if __name__ == '__main__':
    main()
