# chat-node

A small USB-C-powered Wi-Fi voice puck for the kitchen or living room: one microphone, one speaker, one big
lit button. It is a thin audio client. It streams microphone audio to a gateway on a Mac mini over a
WebSocket and plays what the gateway streams back. No AI model and no third-party keys live on the device.

| Folder | What is in it |
|---|---|
| `boards/chat-node/` | KiCad project of the main board (schematic, layout, project library) and the scripts that generate it |
| `mfg/chat-node/` | Generated manufacturing set: Gerbers, drill, BOM, placement, schematic PDF, check reports. Never edit by hand |
| `mech/` | 3D-printed enclosure: FreeCAD scripts, STEP files, renders, fit-check log |
| `firmware/` | ESP-IDF firmware and the wire protocol (`PROTOCOL.md`). Not yet compiled or run on hardware |
| `gateway/` | Small Python bring-up server (echo and tone modes). Not the real gateway, no AI |

## Hardware in brief

- ESP32-S3-WROOM-1-N16R8 (16 MB flash, 8 MB PSRAM, built-in antenna), native USB for flashing and console.
- TDK ICS-43434 I2S microphone; MAX98357A I2S Class-D amplifier into a 40 mm, 4 ohm, 3 W speaker.
- Mic and amplifier are on separate I2S ports, so full duplex can be tried later without a board change.
- Kailh Choc V1 keyboard switch as the main button, lit from below by one SK6812MINI-E RGB LED.
- USB-C, 5 V only: 5.1k on each CC pin, 2 A resettable fuse, ESD array on the data lines, 3.3 V LDO.
- Board: 48 x 37 mm, 2 layers, all assembled parts on one side.

The board hangs under the lid with its component side facing DOWN. The bare back of the board faces the lid:
the microphone listens up through a hole in the board, the LED shines up through a slot, and the switch
stands on the back of the board under the button cap.

| Function | GPIO |
|---|---|
| Mic SCK / WS / SD (I2S0) | 11 / 13 / 14 |
| Amp SD_MODE / DIN / BCLK / LRCLK (I2S1) | 4 / 5 / 6 / 7 |
| Main button (to GND) | 15 |
| Status LED data | 16 |
| USB D- / D+ | 19 / 20 |
| BOOT button | 0 |
| Free | 8, 9, 10, 12, 17, 18 |

Test pads on the component side: 5V, 3V3, GND, EN, mic SD, mic SCK, amp DIN.

## The board files are generated

`chat-node.kicad_sch` and `chat-node.kicad_pcb` are written by scripts in `boards/chat-node/scripts/`.
Re-running them overwrites the KiCad files, so make changes in the scripts, or stop using the scripts once
you start editing in KiCad.

- `make_sch.py` draws the schematic; `layout.py` holds placement, tracks and vias; `make_pcb.py` builds the board.
- `scripts/build.sh sch` regenerates schematic, netlist and board. `scripts/build.sh` regenerates the board only.
- `scripts/export.sh` writes the manufacturing set to `mfg/chat-node/`.

## Parts to buy besides the board and the prints

| Part | Notes |
|---|---|
| Speaker | Same Sky CMS-4017-34SP (40 mm, 4 ohm, 3 W, solder tabs) |
| Main switch | Kailh Choc V1 (PG1350), any variant; a quiet linear one suits a kitchen |
| Speaker lead | 2-pin JST PH plug with wires, soldered to the speaker tabs |
| Screws | 3x M2 x 5 thread-forming (board), 4x M2.5 x 8 thread-forming countersunk (base) |
| Small parts | 1 mm foam pad behind the speaker magnet, a thin foam ring for the microphone port, 4 stick-on feet (8 mm) |

## Assembly

1. Push the Choc switch into the BACK of the board (the side without parts) and solder its two pins on the component side.
2. Solder the JST PH lead to the speaker tabs.
3. Turn the shell upside down. Drop the button cap into its hole from inside.
4. Put the foam ring on the microphone boss. Lower the board in, component side toward you, so the switch stem
   enters the cap; fasten with three M2 screws.
5. Put the speaker with its gasket into the ring under the grille, tabs toward the back. Lead the wires through
   the notch in the partition, plug them into J2, and seal the notch with a dab of glue or foam.
6. Stick the foam pad on the base's speaker pad. Hook the base's right edge in first, swing it shut, four screws, feet.

Flashing, provisioning and the bring-up tests (LED, button, speaker tone, mic level, loopback) are in
`firmware/README.md`. RESET and BOOT are on the component side and are reachable with the base off.

## Check before ordering

- The Choc switch heights and stem slots used for the button cap are nominal values, not measured: compare
  `mech/params.py` with a real switch, and test-print the cap.
- The fab's assembly preview: confirm part rotations, above all U1, U2, U3, J1, D1 (reverse mount) and MK1.
- The firmware has not been built. `firmware/README.md` lists the places most likely to need a fix.
