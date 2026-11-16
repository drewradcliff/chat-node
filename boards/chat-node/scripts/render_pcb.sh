#!/bin/sh
# render_pcb.sh name layers [dpi]  -> build/<name>-1.png   (whole board)
cd "$(dirname "$0")/.."
K="/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
"$K" pcb export pdf --layers "$2" --mode-single --drill-shape-opt 2 -o build/$1.pdf chat-node.kicad_pcb >/dev/null 2>&1 || "$K" pcb export pdf --layers "$2" -o build/$1.pdf chat-node.kicad_pcb 2>&1 | tail -3
DPI=${3:-300}
# crop around the board: page mm box
X1=${4:-100}; Y1=${5:-76}; X2=${6:-152}; Y2=${7:-124}
px() { python3 -c "print(int($1/25.4*$DPI))"; }
pdftoppm -r $DPI -x $(px $X1) -y $(px $Y1) -W $(px "($X2-$X1)") -H $(px "($Y2-$Y1)") -png build/$1.pdf build/$1
