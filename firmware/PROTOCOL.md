# chat-node device ↔ gateway protocol (version 1)

One WebSocket per device, opened by the device to the gateway on the home LAN.

- **Binary frames** carry raw audio: mono, signed 16-bit little-endian PCM at the
  session sample rate. No header.
  - device → gateway: microphone audio, one frame per 20 ms block
    (480 samples = 960 bytes at 24 kHz).
  - gateway → device: playback audio, any length (even byte count). 20–100 ms
    per frame is a good size. The device buffers it (several seconds) and plays
    it through a jitter buffer.
- **Text frames** carry one JSON object each, always with a string `"type"`.
  Keep them small (device → gateway ≤ 384 bytes, gateway → device ≤ 2 KB) and
  unfragmented (one WebSocket frame per message). Unknown types are logged and
  ignored; unknown fields are ignored.

The **gateway is the authority on conversation state.** The device reports
button events and streams audio; the gateway decides what they mean and tells
the device which state it is in. The one exception is **local mic mute**: when
the user mutes, the device stops audio leaving at once, whatever the gateway
says, and the gateway cannot unmute it.

## Connection and authentication

```
GET /<path> HTTP/1.1
Upgrade: websocket
Authorization: Bearer <per-device token>
X-Chat-Node-Id: cn-a1b2c3d4e5f6
User-Agent: chat-node/0.1.0
```

- `wss://` is the default. The device verifies the gateway's certificate
  against a PEM pinned on the device (the gateway's self-signed certificate or
  the CA that issued it); with none pinned it falls back to the public CA
  bundle. `ws://` is refused unless enabled on the device for development.
- The gateway must check the token before accepting the upgrade and answer
  `401` if it is wrong. The device shows the error LED and keeps retrying with
  backoff.
- WebSocket ping/pong runs underneath (device pings every 5 s). The JSON
  `ping`/`pong` below is the application keepalive.

## Session start

```
device                                   gateway
  |--- (upgrade, Bearer token) ------------>|
  |--- hello ------------------------------>|
  |<-- welcome (optional config) -----------|
  |<-- state {"state":"idle"} --------------|
```

The device sends no mic audio until it has received `welcome` (it shows the
"connecting to gateway" LED until then, and reconnects if no `welcome` arrives
within 10 s).

## Device → gateway

| type | fields | when |
|---|---|---|
| `hello` | `protocol`, `device_id`, `fw`, `sample_rate`, `audio{format,channels,frame_ms,rates}`, `caps[]`, `muted`, `volume`, `full_duplex`, `reset_reason` | first message after connect |
| `button` | `event`: `press` \| `release` \| `long_press` \| `double_press`; `duration_ms` (release, long_press) | on each gesture |
| `mic_mute` | `muted` (bool), `source`: `button` \| `console` | when local mute changes |
| `playback_done` | `underruns` (count since boot) | the stream closed by `audio_end` has finished playing out of the speaker |
| `config_ack` | effective `sample_rate`, `jitter_ms`, `full_duplex`, `led_brightness`, `mic_gain_shift` | after every `config` (and a `welcome` with config) |
| `ping` | `id` | every 15 s |
| `pong` | `id` (echoed) | reply to a gateway `ping` |
| `error` | `code`, `message` | the device rejected something (`bad_message`, `bad_state`, `unsupported_rate`) |

Button events are sent immediately and are not exclusive:

- a short press: `press`, `release`
- a long press (default 1.5 s): `press`, `long_press` (while held), `release`.
  The device toggles local mic mute on a long press and sends `mic_mute`
  **before** `long_press`. The gateway should treat a long press as cancelling
  whatever the `press` started.
- a double press (second press within 350 ms of the first release):
  `press`, `release`, `press`, `double_press`, `release`.
- holding 10 s factory-resets the device's stored credentials; the
  socket simply closes.

Example `hello`:

```json
{"type":"hello","protocol":1,"device_id":"cn-a1b2c3d4e5f6","fw":"0.1.0",
 "sample_rate":24000,
 "audio":{"format":"pcm_s16le","channels":1,"frame_ms":20,"rates":[16000,24000,48000]},
 "caps":["mic","speaker","button","led","mic_mute","volume","full_duplex"],
 "muted":false,"volume":70,"full_duplex":false,"reset_reason":"poweron"}
```

## Gateway → device

| type | fields | effect |
|---|---|---|
| `welcome` | `session` (optional, informational), `config` (optional, same fields as `config`) | session accepted; device becomes ready |
| `state` | `state`: `idle` \| `listening` \| `thinking` \| `speaking` \| `error` | sets the conversation state (LED, mic gating); clears a previous `error` message |
| `audio_start` | — | a playback stream begins (device wakes the amp and prebuffers) |
| `audio_end` | — | no more audio for this stream; play what is buffered, then send `playback_done` |
| `audio_clear` | — | drop all buffered playback now (barge-in). No `playback_done` follows |
| `volume` | `level` 0–100 (optional), `muted` bool (optional) | speaker volume / speaker mute (not the mic) |
| `config` | `sample_rate` (16000 \| 24000 \| 48000), `jitter_ms` (20–1000), `full_duplex` (bool), `led_brightness` (0–255), `mic_gain_shift` (0–8); all optional | applied at once, answered with `config_ack` |
| `ping` / `pong` | `id` | keepalive |
| `error` | `code`, `message` | logged; LED shows error until the next `state` |

Audio markers are applied in order with the binary frames around them: an
`audio_clear` drops exactly the audio received before it, so audio sent right
after it is kept. Send `config` with a new `sample_rate` only while idle; it
also clears buffered playback.

Example turn:

```json
{"type":"state","state":"speaking"}
{"type":"audio_start"}
<binary PCM> <binary PCM> ...
{"type":"audio_end"}
                                   <- {"type":"playback_done","underruns":0}
{"type":"state","state":"idle"}
```

## Conversation states

| state | LED | mic audio sent (half duplex, default) | mic audio sent (`full_duplex`) |
|---|---|---|---|
| `idle` | dim green | no | no |
| `listening` | blue | **yes** | yes |
| `thinking` | purple, breathing | no | yes |
| `speaking` | cyan, breathing | no | yes |
| `error` | red, fast blink | no | no |

In every state: if the mic is muted locally, nothing is sent. Mic frames
captured just before a mute that are still queued are discarded too.

```
                     press
          +-------------------------+
          |                         v
       +------+   cancel/timeout +-----------+
  ---> | idle |<-----------------| listening |<----------------+
       +------+                  +-----------+                 |
          ^                         | release / end of speech  | press while speaking
          |                         v                          | (barge-in: gateway sends
          |                    +----------+                    |  audio_clear, then
          |                    | thinking |                    |  state listening)
          |                    +----------+                    |
          |                         | first reply audio        |
          |  playback_done          v                          |
          +-----------------  +----------+  -------------------+
                              | speaking |
                              +----------+
       any state --(gateway fault)--> error --(next state message)--> ...
       socket lost: device flushes playback, amp off, state = idle, LED "connecting"
```

All transitions are made by the gateway; the arrows show the usual triggers.
The device does nothing local on a press while `speaking` except send the
`button` event: barge-in is the gateway's decision.

## Device link states (local, not sent)

booting → (no credentials: provisioning needed) → connecting to Wi-Fi →
connecting to gateway → ready. On any loss the device goes back to the matching
"connecting" state and retries forever with exponential backoff (1 s doubling to
60 s, half of each delay randomised), reset after a session that reached
`welcome`.

## Keepalive and timeouts

- Device sends `{"type":"ping","id":n}` every 15 s; the gateway should answer
  `pong` with the same id.
- If the device receives nothing at all for 45 s, or the WebSocket ping/pong
  fails for 20 s, it drops the socket and reconnects.
- A gateway should consider a device gone if it receives nothing (mic audio,
  ping, WebSocket ping) for 30 s.

## Versioning

`hello.protocol` is 1. Additive changes (new optional fields or message types)
keep the number; anything else increments it, and a gateway that does not
support the device's version should send `error` with code
`unsupported_protocol` and close.
