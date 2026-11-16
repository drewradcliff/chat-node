# chat-node bring-up gateway (test stub)

> **This is a bring-up stub, not the production gateway.** It has no OpenAI or
> other AI integration, it never asks for or handles an API key, and it has no
> household integrations. It speaks [`../firmware/PROTOCOL.md`](../firmware/PROTOCOL.md)
> so a chat-node device can be tested before the real gateway on the Mac mini
> exists.

What it does:

- checks the device's `Authorization: Bearer <token>` header before accepting
  the WebSocket (wrong token → HTTP 401)
- logs every control message in both directions
- **echo** mode (default): press → `listening` (records the mic audio);
  release → `thinking` → `speaking` (plays the recording back) → `idle` once
  the device reports `playback_done`. A press while speaking is a barge-in:
  `audio_clear` then `listening`. A long press (mute) cancels the turn.
- **tone** mode: the same turn, but the reply is a 1 s 440 Hz tone at −12 dBFS.
- optional TLS (`wss://`) with a self-signed certificate
- optional WAV dump of what the mic sent (`--record-dir`), handy for judging
  mic level and quality on a computer

## Setup

Python 3.9 or newer, one dependency (`websockets`), in a virtual environment:

```sh
cd gateway
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Make a token for the device (keep it out of git; any printable string with no
spaces works):

```sh
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Run

Plain `ws://` for first bring-up (the device must be told to allow it with
`gateway insecure on`):

```sh
CHATNODE_TOKEN=<token> .venv/bin/python gateway.py --mode echo --record-dir recordings
```

On the device console:

```
gateway insecure on
gateway set ws://<mac-ip>:8765/ <token>
```

### With TLS (recommended, and what a deployed device should use)

Make a self-signed certificate whose names include the address the device
connects to (hostname and/or IP):

```sh
openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
  -keyout gateway-key.pem -out gateway-cert.pem \
  -subj "/CN=chat-gateway.local" \
  -addext "subjectAltName=DNS:chat-gateway.local,IP:192.168.1.50"
```

(Replace the IP with the gateway machine's address; `-addext` needs OpenSSL
1.1.1+ or a recent LibreSSL, as shipped with macOS.)

```sh
CHATNODE_TOKEN=<token> .venv/bin/python gateway.py --cert gateway-cert.pem --key gateway-key.pem
```

Pin the certificate on the device: run `gateway cert` on the console, paste
the contents of `gateway-cert.pem` (never the key), then press Enter on an
empty line. Then:

```
gateway insecure off
gateway set wss://192.168.1.50:8765/ <token>
```

The `.pem` files are git-ignored. The key stays on the gateway machine.

## Options

| option | meaning |
|---|---|
| `--token` / `CHATNODE_TOKEN` | the device token (required) |
| `--mode echo\|tone` | reply with the recording or a test tone |
| `--host`, `--port` | listen address (default `0.0.0.0:8765`) |
| `--cert`, `--key` | enable `wss://` |
| `--sample-rate 16000\|24000\|48000` | override the device's rate (sent in `welcome.config`) |
| `--jitter-ms N` | override the device's playback jitter target |
| `--volume N` | send a `volume` message on connect |
| `--pace realtime\|burst` | stream playback at ~real time (default) or all at once (tests the device's buffer) |
| `--record-dir DIR` | save each echo recording as a WAV |
| `-v` | debug logging, including the `websockets` library |

Recordings are capped at 8 s so a burst always fits the device's playback
buffer (≈10.9 s at 24 kHz).

## Self-test (no hardware)

`selftest.py` starts the stub in-process and drives it with a fake device:
wrong token rejected, hello/welcome, ping/pong, a full echo turn (checks every
byte comes back), barge-in, and mute cancelling a turn.

```sh
.venv/bin/python selftest.py
```
