"""Builds the project symbol library (lib/chat-node.kicad_sym) from KiCad stock symbols."""
import os
from sexp import Sym, dump, find
from symlib import get_symbol

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'lib', 'chat-node.kicad_sym')


def derive(lib, name, new, props):
    s = get_symbol(lib, name)
    s[1] = new
    for u in find(s, 'symbol'):
        u[1] = u[1].replace(name, new, 1)
    for p in find(s, 'property'):
        if p[1] in props:
            p[2] = props[p[1]]
    return s


syms = [
    derive('Regulator_Linear', 'AMS1117-3.3', 'SGM2212-3.3', {
        'Value': 'SGM2212-3.3', 'Footprint': 'Package_TO_SOT_SMD:SOT-223-3_TabPin2',
        'Datasheet': 'https://www.sg-micro.com/product/SGM2212',
        'Description': '800 mA low-dropout regulator, 3.3 V fixed, SOT-223 (pin 1 GND, pin 2 + tab OUT, pin 3 IN)',
        'ki_keywords': 'LDO regulator 3.3V 800mA'}),
    derive('Switch', 'SW_Push', 'SW_Kailh_Choc_V1', {
        'Value': 'Kailh Choc V1', 'Footprint': 'chat-node:SW_Kailh_Choc_V1_Reverse',
        'Datasheet': 'https://www.kailhswitch.com/mechanical-keyboard-switches/low-profile-key-switches/',
        'Description': 'Kailh Choc V1 (PG1350) low-profile keyboard switch, SPST momentary',
        'ki_keywords': 'keyboard switch choc PG1350'}),
]
doc = [Sym('kicad_symbol_lib'), [Sym('version'), 20241209], [Sym('generator'), 'kicad_symbol_editor'],
       [Sym('generator_version'), '9.0']] + syms
open(OUT, 'w').write(dump(doc) + '\n')
print('wrote', os.path.normpath(OUT))
