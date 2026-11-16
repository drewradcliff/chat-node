#!/bin/sh
# Generates the manufacturing set for the main board into <repo>/mfg/chat-node/ (never edit that folder by hand).
set -e
cd "$(dirname "$0")/.."
K="/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
OUT=../../mfg/chat-node
CONV=/Users/drewradcliff/.local/share/backplane/builds/v0.15.2/kistack/skills/export/scripts/convert_position.py
rm -rf "$OUT"; mkdir -p "$OUT/gerbers"
q() { "$@" 2>&1 | grep -v -i fontconfig || true; }
q "$K" sch erc --output "$OUT/erc.rpt" --format report --units mm --severity-warning --severity-error chat-node.kicad_sch
q "$K" pcb drc --output "$OUT/drc.rpt" --format report --units mm --severity-warning --severity-error --refill-zones --schematic-parity chat-node.kicad_pcb
q "$K" sch export pdf --output "$OUT/schematic.pdf" chat-node.kicad_sch
q "$K" sch export bom --output "$OUT/bom.csv" \
  --fields 'Value,Reference,Footprint,MPN,Manufacturer,LCSC,${QUANTITY},${DNP},Customer Note' \
  --labels 'Comment,Designator,Footprint,MPN,Manufacturer,LCSC,Qty,DNP,Customer Note' \
  --group-by 'Value,Footprint,MPN,LCSC,${DNP}' --sort-field Reference --ref-range-delimiter '' chat-node.kicad_sch
q "$K" pcb export gerbers --output "$OUT/gerbers" \
  --layers F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
  --subtract-soldermask --precision 5 chat-node.kicad_pcb
q "$K" pcb export drill --output "$OUT/gerbers" --format excellon --drill-origin absolute \
  --excellon-units mm --excellon-zeros-format decimal --generate-map --map-format gerberx2 chat-node.kicad_pcb
q "$K" pcb export pos --output "$OUT/positions_raw.csv" --format csv --units mm --side both --exclude-dnp chat-node.kicad_pcb
python3 "$CONV" --help >/dev/null 2>&1 && python3 "$CONV" "$OUT/positions_raw.csv" "$OUT/positions.csv" || true
q "$K" pcb export step --output "$OUT/chat-node.step" --force --subst-models --no-dnp chat-node.kicad_pcb
ls "$OUT" "$OUT/gerbers"
