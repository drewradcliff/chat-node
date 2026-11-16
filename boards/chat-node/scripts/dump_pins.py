import sys
from symlib import get_symbol, pins
for spec in sys.argv[1:]:
    lib, name = spec.split(':')
    s = get_symbol(lib, name)
    print('==', spec)
    for p in sorted(pins(s), key=lambda p: (p[7], len(p[0]), p[0])):
        print('  %-4s %-16s at(%7.2f,%7.2f) ang %3d len %.2f %s u%d' % p)
