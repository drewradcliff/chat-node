"""Small KiCad schematic writer: places library symbols, computes pin positions,
draws wires/labels/power symbols. Coordinates in mm, y down, on a 1.27 grid."""
import copy, math, uuid, os
from sexp import Sym, dump, find, first
from symlib import get_symbol, pins

NS = uuid.UUID('6f1d8c1e-0c8f-4a57-9a11-c0ffee000001')


def Y(b):
    return Sym('yes' if b else 'no')


class Comp:
    def __init__(self, sch, ref, libid, x, y, rot, mirror, sym):
        self.sch, self.ref, self.libid = sch, ref, libid
        self.x, self.y, self.rot, self.mirror = x, y, rot, mirror
        self._pins = {}
        for num, name, px, py, ang, ln, et, unit in pins(sym):
            self._pins.setdefault(num, []).append((px, py))
        self.names = {num: name for num, name, *_ in pins(sym)}

    def _tx(self, px, py):
        if self.mirror == 'y':
            px = -px
        if self.mirror == 'x':
            py = -py
        a = math.radians(self.rot)
        rx = px * math.cos(a) - py * math.sin(a)
        ry = px * math.sin(a) + py * math.cos(a)
        return (round(self.x + rx, 4), round(self.y - ry, 4))

    def p(self, num):
        px, py = self._pins[str(num)][0]
        return self._tx(px, py)


class Sch:
    def __init__(self, project, title, paper='A3', rev='1', date=''):
        self.project = project
        self.root_uuid = str(uuid.uuid5(NS, 'root'))
        self.items = []
        self.libsyms = {}
        self.n = 0
        self.pwr_n = 0
        self.head = [Sym('kicad_sch'), [Sym('version'), 20250114], [Sym('generator'), 'eeschema'],
                     [Sym('generator_version'), '9.0'], [Sym('uuid'), self.root_uuid], [Sym('paper'), paper],
                     [Sym('title_block'), [Sym('title'), title], [Sym('date'), date], [Sym('rev'), rev]]]

    def uid(self, tag=''):
        self.n += 1
        return str(uuid.uuid5(NS, '%s-%d' % (tag, self.n)))

    # ---- library handling
    def _lib(self, libid, libpath=None):
        if libid not in self.libsyms:
            lib, name = libid.split(':')
            s = get_symbol(libpath or lib, name)
            s = copy.deepcopy(s)
            s[1] = libid
            self.libsyms[libid] = s
        return self.libsyms[libid]

    @staticmethod
    def _font(size=1.27, color=None, bold=False):
        f = [Sym('font'), [Sym('size'), size, size]]
        if bold:
            f.append([Sym('bold'), Sym('yes')])
        if color:
            f.append([Sym('color')] + list(color))
        return f

    def _prop(self, name, value, x, y, hide=False, just=None, rot=0, size=1.27):
        eff = [Sym('effects'), self._font(size)]
        if just:
            eff.append([Sym('justify')] + [Sym(j) for j in just.split()])
        if hide:
            eff.append([Sym('hide'), Sym('yes')])
        return [Sym('property'), name, value, [Sym('at'), x, y, rot], eff]

    def sym(self, ref, libid, x, y, rot=0, mirror=None, value=None, fp='', props=None,
            ref_at=None, val_at=None, libpath=None, dnp=False, in_bom=True, on_board=True,
            hide_ref=False, hide_val=False, datasheet=''):
        s = self._lib(libid, libpath)
        c = Comp(self, ref, libid, x, y, rot, mirror, s)
        if value is None:
            value = first([p for p in find(s, 'property') if p[1] == 'Value'], 'property') or libid.split(':')[1]
            value = libid.split(':')[1]
        rx, ry, rj = ref_at if ref_at else (0, -3.81, None)
        vx, vy, vj = val_at if val_at else (0, 3.81, None)
        node = [Sym('symbol'), [Sym('lib_id'), libid], [Sym('at'), x, y, rot]]
        if mirror:
            node.append([Sym('mirror'), Sym(mirror)])
        pr = 90 if rot in (90, 270) else 0
        node += [[Sym('unit'), 1], [Sym('exclude_from_sim'), Sym('no')], [Sym('in_bom'), Y(in_bom)],
                 [Sym('on_board'), Y(on_board)], [Sym('dnp'), Y(dnp)], [Sym('uuid'), self.uid(ref)],
                 self._prop('Reference', ref, x + rx, y + ry, hide=hide_ref, just=rj, rot=pr),
                 self._prop('Value', value, x + vx, y + vy, hide=hide_val, just=vj, rot=pr),
                 self._prop('Footprint', fp, x, y, hide=True),
                 self._prop('Datasheet', datasheet, x, y, hide=True),
                 self._prop('Description', '', x, y, hide=True)]
        for k, v in (props or {}).items():
            node.append(self._prop(k, v, x, y, hide=True))
        for num in c._pins:
            node.append([Sym('pin'), num, [Sym('uuid'), self.uid(ref + num)]])
        node.append([Sym('instances'), [Sym('project'), self.project,
                     [Sym('path'), '/' + self.root_uuid, [Sym('reference'), ref], [Sym('unit'), 1]]]])
        self.items.append(node)
        return c

    def pwr(self, name, pt, rot=0, val_at=None):
        self.pwr_n += 1
        ref = '#PWR%03d' % self.pwr_n if name != 'PWR_FLAG' else '#FLG%03d' % self.pwr_n
        x, y = pt
        if val_at is None:
            down = name == 'GND'
            if rot == 0:
                val_at = (0, 3.81 if down else -3.81, None)
            elif rot == 180:
                val_at = (0, -3.81 if down else 3.81, None)
            elif rot == 90:
                val_at = (3.81 if down else -3.81, 0, None)
            else:
                val_at = (-3.81 if down else 3.81, 0, None)
        if name == 'PWR_FLAG':
            val_at = (0, -5.08, None) if rot == 0 else (0, 5.08, None)
        return self.sym(ref, 'power:' + name, x, y, rot=rot, value=name, hide_ref=True,
                        val_at=val_at, hide_val=(name == 'GND' or name == 'PWR_FLAG'))

    # ---- drawing
    def wire(self, *pts, color=None):
        for a, b in zip(pts, pts[1:]):
            st = [Sym('stroke'), [Sym('width'), 0], [Sym('type'), Sym('default')]]
            if color:
                st.append([Sym('color')] + list(color))
            self.items.append([Sym('wire'), [Sym('pts'), [Sym('xy'), a[0], a[1]], [Sym('xy'), b[0], b[1]]],
                               st, [Sym('uuid'), self.uid('w')]])

    def junction(self, pt, color=None):
        self.items.append([Sym('junction'), [Sym('at'), pt[0], pt[1]], [Sym('diameter'), 0],
                           [Sym('color')] + list(color or (0, 0, 0, 0)), [Sym('uuid'), self.uid('j')]])

    def nc(self, pt):
        self.items.append([Sym('no_connect'), [Sym('at'), pt[0], pt[1]], [Sym('uuid'), self.uid('nc')]])

    def label(self, name, pt, rot=0, color=None):
        just = {0: 'left bottom', 180: 'right bottom', 90: 'left bottom', 270: 'right bottom'}[rot]
        self.items.append([Sym('label'), name, [Sym('at'), pt[0], pt[1], rot],
                           [Sym('effects'), self._font(1.27, color), [Sym('justify')] + [Sym(j) for j in just.split()]],
                           [Sym('uuid'), self.uid('l')]])

    def stub(self, pt, dx, name, color=None, dy=0):
        """Wire from a pin sideways and put a label at the far end reading away from the pin."""
        end = (round(pt[0] + dx, 4), round(pt[1] + dy, 4))
        self.wire(pt, end, color=color)
        self.label(name, end, 0 if dx > 0 else 180, color=color)
        return end

    def box(self, x1, y1, x2, y2, title, color):
        self.items.append([Sym('rectangle'), [Sym('start'), x1, y1], [Sym('end'), x2, y2],
                           [Sym('stroke'), [Sym('width'), 0.25], [Sym('type'), Sym('dash')], [Sym('color')] + list(color)],
                           [Sym('fill'), [Sym('type'), Sym('none')]], [Sym('uuid'), self.uid('r')]])
        self.text(title, x1 + 1.9, y1 + 4.4, size=2.2, bold=True, color=color)

    def text(self, s, x, y, size=1.27, bold=False, color=None, just='left bottom'):
        self.items.append([Sym('text'), s, [Sym('exclude_from_sim'), Sym('no')], [Sym('at'), x, y, 0],
                           [Sym('effects'), self._font(size, color, bold), [Sym('justify')] + [Sym(j) for j in just.split()]],
                           [Sym('uuid'), self.uid('t')]])

    def write(self, path):
        doc = list(self.head)
        doc.append([Sym('lib_symbols')] + list(self.libsyms.values()))
        order = {'junction': 0, 'no_connect': 1, 'wire': 2, 'rectangle': 3, 'text': 4, 'label': 5, 'symbol': 6}
        doc += sorted(self.items, key=lambda i: order[str(i[0])])
        doc.append([Sym('sheet_instances'), [Sym('path'), '/', [Sym('page'), '1']]])
        doc.append([Sym('embedded_fonts'), Sym('no')])
        open(path, 'w', encoding='utf-8').write(dump(doc) + '\n')
