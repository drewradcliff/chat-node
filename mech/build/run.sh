#!/bin/zsh
# run part scripts through the offscreen FreeCAD GUI with a watchdog (macOS has no `timeout`)
cd /Users/drewradcliff/repos/chat-node/mech
for p in "$@"; do
  QT_QPA_PLATFORM=offscreen /Applications/FreeCAD.app/Contents/MacOS/FreeCAD $p.py >/dev/null 2>&1 & pid=$!
  (sleep 300; kill $pid 2>/dev/null) & w=$!
  wait $pid; echo "$p exit $?"; kill $w 2>/dev/null
done
