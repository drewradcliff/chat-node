#!/bin/sh
# Regenerates schematic netlist + board. usage: build.sh [sch]
cd "$(dirname "$0")/.."
K="/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
if [ "$1" = "sch" ]; then
  (cd scripts && python3 make_sch.py) || exit 1
  "$K" sch export netlist --format kicadsexpr -o build/chat-node.net chat-node.kicad_sch 2>&1 | grep -v Fontconfig
fi
(cd scripts && $KP make_pcb.py 2>&1 | grep -v -i "fontconfig")
