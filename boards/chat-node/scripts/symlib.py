"""Pull symbols out of KiCad libraries, flattening 'extends'."""
import copy, os
from sexp import parse, find, first, Sym

SYMDIR = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols'
_cache = {}

def load_lib(path):
    if path not in _cache:
        _cache[path] = parse(open(path, encoding='utf-8').read())
    return _cache[path]

def get_symbol(lib, name, libdir=SYMDIR):
    path = lib if lib.endswith('.kicad_sym') else os.path.join(libdir, lib + '.kicad_sym')
    tree = load_lib(path)
    for s in find(tree, 'symbol'):
        if s[1] == name:
            ext = first(s, 'extends')
            if ext:
                parent = copy.deepcopy(get_symbol(lib, ext[1], libdir))
                # rename parent + sub-units, override properties
                old = parent[1]
                parent[1] = name
                for u in find(parent, 'symbol'):
                    u[1] = u[1].replace(old, name, 1)
                props = {p[1]: p for p in find(s, 'property')}
                for i, p in enumerate(parent):
                    if isinstance(p, list) and p[0] == 'property' and p[1] in props:
                        parent[i] = props.pop(p[1])
                return parent
            return copy.deepcopy(s)
    raise KeyError(name)

def pins(sym):
    """[(number, name, x, y, angle, length, etype, unit)]"""
    out = []
    for u in find(sym, 'symbol'):
        unit = int(u[1].rsplit('_', 2)[-2])
        for p in find(u, 'pin'):
            at = first(p, 'at')
            out.append((first(p, 'number')[1], first(p, 'name')[1], float(at[1]), float(at[2]),
                        float(at[3]) if len(at) > 3 else 0.0, float(first(p, 'length')[1]), str(p[1]), unit))
    return out
