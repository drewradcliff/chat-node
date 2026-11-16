# chat-node firmware

Firmware for the chat-node voice puck: a thin audio client on an
ESP32-S3-WROOM-1-N16R8. It captures the microphone, streams it over one
WebSocket to the gateway on the home LAN, and plays the audio the gateway
streams back. **No AI model, wake word, speech recognition or third-party API
key lives on the device.** The gateway owns the AI connection, tools,
household integrations, device authentication and sessions.

The wire protocol is in [PROTOCOL.md](PROTOCOL.md). A bring-up gateway stub
(echo / tone, no AI) is in [`../gateway`](../gateway).

> Status: written against ESP-IDF v5.3 APIs but **not yet compiled or run on
> hardware**. Expect small fixes at the first build.

## Hardware summary

All pins are defined in one place, [`main/board_pins.h`](main/board_pins.h).

| function | part | port / pins |
|---|---|---|
| Microphone | TDK ICS-43434, LR = GND (left slot) | I2S0 RX: SCK GPIO11, WS GPIO13, SD GPIO14 |
| Amplifier | MAX98357A → 4 Ω 3 W speaker, 5 V | I2S1 TX: DIN GPIO5, BCLK GPIO6, LRCLK GPIO7; SD_MODE GPIO4 |
| Main button | key switch to GND | GPIO15 (internal pull-up, active low) |
| Status LED | SK6812MINI-E via 74AHCT1G125 | GPIO16 (RMT) |
| USB | native USB-Serial-JTAG | GPIO19 D-, GPIO20 D+ (only console and programming port) |
| BOOT / RESET | development buttons | GPIO0 / EN |
| Spare, unconnected | | GPIO8, 9, 10, 12, 17, 18 |

GPIO35/36/37 belong to the octal PSRAM. UART0 (GPIO43/44) is not brought out:
the native USB port is the only console.

Notes that affect firmware and bring-up:

- **Amplifier supply:** the MAX98357A has one 10 µF + 100 nF at its supply and
  sits behind a 2 A resettable fuse on USB 5 V. A 3 W peak into 4 Ω can pull
  close to 1 A from 5 V, more than a 500 mA USB port can give, so the
  firmware caps output at **−6 dBFS peak** at volume 100
  (`CONFIG_CHAT_NODE_OUTPUT_CEILING_DB`). After a brown-out reset it lowers the
  cap another 6 dB until the next normal boot and reports
  `reset_reason: "brownout"` to the gateway. With little bulk capacitance at
  the amp, check loud low-frequency content on the weakest supply you intend
  to support before raising the ceiling.
- **Amplifier gain** is set in hardware: 9 dB as built. Fitting R6 gives
  15 dB. If you fit R6, lower the ceiling by 6 dB to keep the same maximum
  speaker power. Volume is digital (0–100, 40 dB range).
- **SD_MODE (GPIO4)** has the amp's internal 100 kΩ pull-down, so the amp stays
  off through reset and boot. Firmware drives it high only while audio is
  playing (and during the jitter-buffer prebuffer), and low again after 500 ms
  of silence.
- **GPIO0 (BOOT)** has no external pull-up, only the chip's own (as on
  Espressif's ESP32-S3-DevKitC-1). Firmware never touches GPIO0.
- **RESET and BOOT buttons** are on the component side of the board and can be
  reached once the enclosure base is removed.
- **Microphone:** the ICS-43434 needs a continuous SCK and a sample rate of
  23–51.6 kHz. The firmware always clocks it at 48 kHz (SCK 3.072 MHz) and
  decimates to the wire rate, so 16 kHz sessions don't push it out of normal
  mode. The first 100 ms after the clocks start are discarded (start-up is
  about 85 ms).

## Build

Requires ESP-IDF **v5.3 or newer** (`idf.py --version`). The managed components
(`espressif/esp_websocket_client`, `espressif/led_strip` 2.x) download on the
first build.

```sh
cd firmware
idf.py set-target esp32s3      # once; sdkconfig.defaults already selects it
idf.py build
```

Settings are under `idf.py menuconfig` → **chat-node** (sample rate, mic gain,
jitter buffer, volume and ceiling, button timings, LED brightness, backoff,
full duplex, Wi-Fi power save).

## Flash over the native USB port

Connect USB-C. The board enumerates as "USB JTAG/serial debug unit"
(`/dev/cu.usbmodem*` on macOS, `/dev/ttyACM*` on Linux, a COM port on Windows).

```sh
idf.py -p /dev/cu.usbmodemXXXX flash monitor
```

esptool resets the S3 into the bootloader over USB on its own. If that fails
(the firmware crashed early, the port disappeared, or the chip is in a reset
loop), enter the ROM bootloader by hand. With the enclosure base removed:

1. hold **BOOT**,
2. press and release **RESET**,
3. release **BOOT**,
4. run `idf.py -p <port> flash` (the port name can change in download mode),
5. press **RESET** to start the new firmware if it does not start by itself.

`idf.py monitor` (exit with Ctrl-]) shows logs and the `chat-node>` console
prompt. Logs and the console share the port, so log lines can land in the
middle of what you type; that does not affect the command.

## Provisioning (USB console)

Credentials, the gateway URL, the token and the pinned certificate are stored
in NVS on the device, never in this source tree.

```
chat-node> wifi set "My Network" "my wifi password"
chat-node> gateway set wss://192.168.1.50:8765/ <device-token>
chat-node> gateway cert
Paste the PEM certificate (gateway cert or its CA), then an empty line:
-----BEGIN CERTIFICATE-----
...
-----END CERTIFICATE-----

chat-node> status
```

| command | what it does |
|---|---|
| `wifi set <ssid> <pass>` | save Wi-Fi credentials and connect (use `""` for an open network) |
| `gateway set <url> <token>` | save gateway URL and per-device token, reconnect |
| `gateway cert` / `gateway cert clear` | pin the gateway's certificate (or its CA) by pasting the PEM / remove it |
| `gateway insecure on\|off` | allow `ws://` (development only; off by default) |
| `status` | firmware, link and conversation state, audio, Wi-Fi, gateway, heap |
| `volume [0-100]` | show or set speaker volume (saved) |
| `mute [on\|off]` | show or set local mic mute (saved) |
| `duplex [on\|off]` | full-duplex mic streaming for experiments (not saved) |
| `factory-reset yes` | erase all stored credentials and settings, reboot |
| `reboot` | restart |
| `tone <hz> <ms>` | speaker test |
| `miclevel [seconds]` | mic RMS/peak meter, 10 lines per second |
| `loopback <seconds>` | record then play back locally, no network |

- The token is sent only in the `Authorization: Bearer` header of the
  WebSocket upgrade and is never printed by `status`.
- `wss://` is required unless `gateway insecure on` is set. With a pinned
  certificate the device trusts only that certificate (or CA). Without one, it
  falls back to the public CA bundle, which only suits a gateway with a
  publicly issued certificate.
- The certificate's subjectAltName must match the host in the URL (IP or
  name). [`../gateway/README.md`](../gateway/README.md) has the `openssl`
  command.
- **Button factory reset:** hold the main button for 10 s. After 5 s the LED
  strobes white as a warning; releasing before 10 s cancels. Credentials and
  settings are erased and the device reboots into provisioning (orange blink).

BLE provisioning is **not implemented**; the USB console is the provisioning
method.

## Bring-up tests, in order

Each step uses only what the steps before it proved. Steps 1–5 need no network.

1. **USB and boot.** `idf.py monitor`, press RESET. Expect the boot log, then
   `chat-node 0.1.0, reset reason: ...`, the device id and the `chat-node>`
   prompt. `status` should show PSRAM free ≈ 8 MB minus the buffers.
2. **LED.** At boot the LED is white, then blinks orange (no Wi-Fi stored).
   `mute on` → solid red; `mute off` → orange blink again. Check the colours
   read correctly through the cap (red is not green: GRB order) and the
   brightness is comfortable (`CONFIG_CHAT_NODE_LED_BRIGHTNESS`, default
   48/255). The full table is in `main/led.c`.
3. **Button.** Each gesture logs a line: `button press`, `button release 120 ms`,
   a double press logs `double_press`, holding 1.5 s logs `long_press` and
   toggles mute (LED red). Holding 5 s logs `reset_warning` and the LED
   strobes white; **release before 10 s** unless you want a factory reset.
   Check that a single press never logs two presses (debounce).
4. **Speaker.** `volume 30`, then `tone 440 1000`, `tone 1000 500`,
   `tone 200 2000`. Expect a clean tone with no click when the amp switches on
   or off (it switches off 0.5 s after the tone). Then `volume 100` and
   `tone 150 3000` on the weakest USB supply you have: the device must not
   reset. If `status` later shows `last reset: brownout`, the supply is too weak.
5. **Microphone.** `miclevel 10`. A quiet room should read around −70 to −55 dBFS
   RMS; talking at 30 cm, around −35 to −20 dBFS; a clap near the mic peaks
   near 0 dBFS. Silence reading −96 dBFS means no data (check SCK/WS/SD and that
   the ICS-43434 is powered); a steady reading near full scale means the wrong
   slot or format. Adjust `CONFIG_CHAT_NODE_MIC_GAIN_SHIFT` (6 dB per step;
   the gateway can also set `mic_gain_shift`).
6. **Local loopback.** `loopback 3`, speak during the 3 s, then hear it back.
   It should be clear, at the right pitch (a wrong pitch means a sample-rate
   mismatch) and without crackle.
7. **Wi-Fi.** `wifi set ...`. The LED blinks blue while connecting and turns
   yellow-blinking (connecting to the gateway) or orange (no gateway stored)
   once it has an IP. `status` shows the IP and RSSI.
8. **Gateway stub, echo.** Start `../gateway/gateway.py` (see its README), then
   `gateway set ...`. The LED turns dim green (idle). Press and hold the
   button and speak: blue (listening). Release: purple (thinking), then cyan
   (speaking) while your words play back, then green. Press during playback
   to check barge-in: playback stops at once and the LED turns blue.
   With `--record-dir` the stub saves each recording as a WAV to inspect.
9. **Resilience.** Stop the stub during playback: the audio stops, the amp
   switches off, the LED blinks yellow, and the device reconnects when the
   stub is back (retries 1 s, 2 s, 4 s ... up to 60 s, with jitter). Turn the
   access point off and on: same, with blue blinking. Hold the button 1.5 s
   while listening: the LED turns red and the stub logs `mic_mute`; no more
   audio arrives until you unmute.
10. **TLS.** Switch the stub to `--cert/--key`, pin the cert with
    `gateway cert`, `gateway insecure off`, `gateway set wss://...`.

## Software structure

All sources are in `main/`. Each module owns its tasks and buffers:

| module | owns | role |
|---|---|---|
| `audio_in` | I2S0, task `audio_in` (core 1, prio 18), mic message buffer (PSRAM) | 48 kHz capture → DC-blocking high-pass → FIR decimation → 16-bit with gain shift → 20 ms frames; level meter; loopback capture |
| `audio_out` | I2S1, amp SD pin, task `audio_out` (core 1, prio 19), playback ring buffer (PSRAM, 512 KiB) | jitter buffer, underrun fades, volume and ceiling, start/end/clear markers, amp power |
| `ws_client` | task `ws_sup` (connect / keepalive / backoff), task `ws_tx` (only sender), control queue | one WebSocket; received binary → `audio_out`, text → `protocol` |
| `net` | Wi-Fi station, retry timer | connect and reconnect forever with backoff and jitter |
| `protocol` | — | JSON parse/build per PROTOCOL.md |
| `app_state` | atomics | link state, conversation state, mute, full duplex, sample rate; decides when mic audio may leave and which LED state shows |
| `button` | task `button` (5 ms poll) | debounce, press/release/long/double, factory-reset hold |
| `led` | RMT LED strip, task `led` (50 Hz) | one table of colours and animations |
| `storage` | NVS namespace `chatnode` | credentials, gateway, cert, volume, mute |
| `console_cmds` | esp_console REPL on USB-Serial-JTAG | provisioning and bring-up commands |
| `main.c` | — | start-up order, button actions, mute and factory reset |

Audio paths never wait on the network. The capture task posts frames to a
message buffer without blocking (it drops a frame and counts it if the
buffer is full). The playback task only reads from its ring buffer. Neither
allocates memory per frame. The three tasks that must keep running
(`audio_in`, `audio_out`, `ws_tx`) are on the task watchdog (5 s, then
reboot). Wi-Fi power save is off (`WIFI_PS_NONE`) for latency.

Mic gating: audio leaves the device only when the link is ready, the mic is
not muted, and the gateway's state is `listening` (in full-duplex mode, also
`thinking`/`speaking`). Muting bumps an epoch, so frames already queued are
dropped too.

Half duplex is the default. The two I2S ports have separate clocks and
separate tasks, so `duplex on` (or `full_duplex` from the gateway, or
`CONFIG_CHAT_NODE_FULL_DUPLEX`) streams the mic during playback for echo
cancellation experiments. Expect the speaker in the mic: there is no AEC on
the device.

The partition table (`partitions.csv`, 16 MB) has NVS, `nvs_keys`, two 6 MB
OTA slots and a core-dump partition. **OTA updating itself is not implemented
yet**; the slots are there so it can be added without repartitioning.

## Securing a deployed unit (not enabled by default)

Flash encryption and NVS encryption are **off** in `sdkconfig.defaults` on
purpose: enabling flash encryption burns eFuses and **cannot be undone**. Do
this only on units that leave your bench, and try the whole procedure on one
sacrificial board first.

**NVS encryption** keeps the Wi-Fi password, token and certificate unreadable
if someone dumps the flash. ESP-IDF v5.x offers two schemes on the S3:

- *Flash-encryption based* (`CONFIG_NVS_ENCRYPTION=y` with
  `CONFIG_NVS_SEC_KEY_PROTECT_USING_FLASH_ENC=y`): the XTS keys live in the
  `nvs_keys` partition, which is already in `partitions.csv` and marked
  `encrypted`. Requires flash encryption.
- *HMAC based* (`CONFIG_NVS_SEC_KEY_PROTECT_USING_HMAC=y` with an eFuse key
  block that has the HMAC_UP purpose): no flash encryption needed, but the
  firmware image itself stays readable.

The firmware needs no code changes: `nvs_flash_init()` sets up encrypted NVS
when these options are on. Existing plaintext NVS becomes unreadable, so
provision the unit again afterwards.

**Flash encryption** (menuconfig → Security features → Enable flash
encryption on boot):

1. Start in **Development** mode. The first boot encrypts the flash in place
   (this takes a while; don't unplug it). Later builds are flashed with
   `idf.py encrypted-flash`.
2. Only when the firmware is final, use **Release** mode. It permanently stops
   plaintext reflashing over USB and may disable JTAG; the device can then only
   be updated by OTA, **which this firmware does not implement yet**. Don't
   use Release mode until OTA exists.
3. Consider Secure Boot v2 as well, so only your signed images run. It is
   also one-way: keep the signing key safe and backed up.

Check the ESP-IDF v5.3 *Security → Flash Encryption* and *NVS Encryption*
guides for the exact eFuses each mode burns before running it on a unit.
