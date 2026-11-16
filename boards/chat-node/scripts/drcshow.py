import re,sys
t=open('build/drc.rpt').read()
skip=set(sys.argv[1:]) or {'silk_over_copper','silk_overlap','text_height','silk_edge_clearance','lib_footprint_mismatch','lib_footprint_issues'}
for b in re.split(r'\n(?=\[)',t):
    m=re.match(r'\[(\w+)\]',b)
    if not m or m.group(1) in skip: continue
    def rel(mm): return '@(%.2f, %.2f)'%(float(mm.group(1))-130,float(mm.group(2))-100)
    print(re.sub(r'@\(([\d.]+) mm, ([\d.]+) mm\)',rel,b.strip().split('\n\n** ')[0])); print()
