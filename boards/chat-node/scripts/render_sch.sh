#!/bin/sh
# usage: render_sch.sh [dpi]   -> build/sch.png (+ crops with: render_sch.sh dpi x y w h name  in px)
cd "$(dirname "$0")/.."
K="/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
DPI=${1:-110}
"$K" sch export pdf -o build/sch.pdf chat-node.kicad_sch >/dev/null 2>&1
if [ -n "$6" ]; then
  pdftoppm -r $DPI -x $2 -y $3 -W $4 -H $5 -png build/sch.pdf build/$6
else
  pdftoppm -r $DPI -png build/sch.pdf build/sch
fi
