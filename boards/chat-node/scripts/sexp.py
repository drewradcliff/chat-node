"""Minimal KiCad s-expression reader/writer."""
import re

class Sym(str):
    """Bare (unquoted) atom."""

_tok = re.compile(r'\s*(\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+)')

def parse(text):
    pos = 0
    stack = [[]]
    n = len(text)
    while True:
        m = _tok.match(text, pos)
        if not m:
            break
        t = m.group(1)
        pos = m.end()
        if t == '(':
            stack.append([])
        elif t == ')':
            l = stack.pop()
            stack[-1].append(l)
        elif t[0] == '"':
            stack[-1].append(t[1:-1].replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n'))
        else:
            stack[-1].append(Sym(t))
    return stack[0][0]

def q(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'

def dump(x, ind=0):
    if isinstance(x, list):
        simple = all(not isinstance(i, list) for i in x)
        if simple:
            return '(' + ' '.join(dump(i) for i in x) + ')'
        out = '(' + dump(x[0])
        for i in x[1:]:
            if isinstance(i, list):
                out += '\n' + '\t' * (ind + 1) + dump(i, ind + 1)
            else:
                out += ' ' + dump(i)
        out += '\n' + '\t' * ind + ')'
        return out
    if isinstance(x, Sym):
        return str(x)
    if isinstance(x, str):
        return q(x)
    if isinstance(x, float):
        s = ('%.4f' % x).rstrip('0').rstrip('.')
        return s if s not in ('-0', '') else '0'
    return str(x)

def find(l, name):
    return [i for i in l if isinstance(i, list) and i and i[0] == name]

def first(l, name):
    r = find(l, name)
    return r[0] if r else None
