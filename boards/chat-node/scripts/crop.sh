#!/bin/sh
# crop.sh name x1 y1 x2 y2 (mm) [dpi]
cd "$(dirname "$0")/.."
DPI=${6:-170}
px() { python3 -c "print(int($1/25.4*$DPI))"; }
pdftoppm -r $DPI -x $(px $2) -y $(px $3) -W $(px "($4-$2)") -H $(px "($5-$3)") -png build/sch.pdf build/$1
