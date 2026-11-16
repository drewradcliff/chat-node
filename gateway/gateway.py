#!/usr/bin/env python3
"""chat-node BRING-UP gateway stub.

This is NOT the production gateway. It has no OpenAI (or any other AI)
integration, never asks for or reads an API key, and exists only so a chat-node
device can be brought up and tested against firmware/PROTOCOL.md.

Modes:
  echo  press -> listening (records mic audio); release -> thinking -> speaking
        (plays the recording back) -> idle after the device's playback_done.
        A press while speaking is a barge-in: audio_clear, then listening.
  tone  press -> listening; release -> thinking -> speaking (a test tone) -> idle.
"""

import argparse
import asyncio
import hmac
import json
import logging
import math
import os
import ssl
import struct
import sys
import time
import wave
from http import HTTPStatus
from typing import Optional

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

PROTOCOL_VERSION = 1
FRAME_MS = 20
SUPPORTED_RATES = (16000, 24000, 48000)
MAX_RECORD_S = 8.0          # stays well inside the device's ~10 s playback buffer
SEND_CHUNK_MS = 40

log = logging.getLogger("gateway")


def tone_pcm(rate: int, hz: float = 440.0, ms: int = 1000, dbfs: float = -12.0) -> bytes:
    n = rate * ms // 1000
    amp = 32767 * 10 ** (dbfs / 20)
    ramp = max(1, rate // 200)
    out = bytearray()
    for i in range(n):
        env = min(1.0, i / ramp, (n - i) / ramp)
        out += struct.pack("<h", int(amp * env * math.sin(2 * math.pi * hz * i / rate)))
    return bytes(out)


class DeviceSession:
    def __init__(self, ws, args):
        self.ws = ws
        self.args = args
        self.device_id = ws.request.headers.get("X-Chat-Node-Id", "?")
        self.rate = 24000
        self.state = "idle"
        self.recording = bytearray()
        self.play_task: Optional[asyncio.Task] = None
        self.playback_done = asyncio.Event()
        self.mic_muted = False
        self.ping_id = 0

    async def send(self, msg_type: str, **fields):
        msg = {"type": msg_type, **fields}
        log.info("[%s] -> %s", self.device_id, json.dumps(msg))
        await self.ws.send(json.dumps(msg))

    async def set_state(self, state: str):
        self.state = state
        await self.send("state", state=state)

    # ---- inbound -----------------------------------------------------------

    async def run(self):
        async for message in self.ws:
            if isinstance(message, bytes):
                self.on_audio(message)
            else:
                await self.on_text(message)

    def on_audio(self, data: bytes):
        if self.state != "listening":
            return      # full-duplex devices may stream while speaking; ignored here
        if len(self.recording) < MAX_RECORD_S * self.rate * 2:
            self.recording += data

    async def on_text(self, text: str):
        try:
            msg = json.loads(text)
            t = msg["type"]
        except (ValueError, KeyError, TypeError):
            log.warning("[%s] bad control message: %r", self.device_id, text[:200])
            await self.send("error", code="bad_message", message="expected JSON with a type")
            return
        if t != "ping":
            log.info("[%s] <- %s", self.device_id, text)

        if t == "hello":
            await self.on_hello(msg)
        elif t == "button":
            await self.on_button(msg.get("event"), msg.get("duration_ms"))
        elif t == "mic_mute":
            self.mic_muted = bool(msg.get("muted"))
            if self.mic_muted and self.state == "listening":
                self.recording.clear()
                await self.set_state("idle")
        elif t == "playback_done":
            self.playback_done.set()
        elif t == "ping":
            await self.ws.send(json.dumps({"type": "pong", "id": msg.get("id")}))
        elif t == "config_ack":
            if msg.get("sample_rate") in SUPPORTED_RATES:
                self.rate = msg["sample_rate"]
        elif t in ("pong", "error"):
            pass
        else:
            log.warning("[%s] unknown type %r", self.device_id, t)

    async def on_hello(self, msg):
        if msg.get("protocol") != PROTOCOL_VERSION:
            await self.send("error", code="unsupported_protocol",
                            message=f"stub speaks protocol {PROTOCOL_VERSION}")
            await self.ws.close()
            return
        self.rate = msg.get("sample_rate", 24000)
        self.mic_muted = bool(msg.get("muted"))
        config = {}
        if self.args.sample_rate:
            config["sample_rate"] = self.args.sample_rate
            self.rate = self.args.sample_rate
        if self.args.jitter_ms:
            config["jitter_ms"] = self.args.jitter_ms
        welcome = {"session": f"stub-{int(time.time())}"}
        if config:
            welcome["config"] = config
        await self.send("welcome", **welcome)
        if self.args.volume is not None:
            await self.send("volume", level=self.args.volume)
        await self.set_state("idle")

    async def on_button(self, event, duration_ms):
        if event == "press":
            if self.state == "speaking" or (self.play_task and not self.play_task.done()):
                await self.cancel_playback()
                await self.send("audio_clear")          # barge-in
            self.recording.clear()
            if not self.mic_muted:
                await self.set_state("listening")
        elif event == "release":
            if self.state == "listening":
                pcm = bytes(self.recording) if self.args.mode == "echo" else tone_pcm(self.rate)
                self.recording.clear()
                self.play_task = asyncio.create_task(self.respond(pcm))
        elif event == "long_press":
            # Long press toggles mute on the device; cancel the turn the press began.
            self.recording.clear()
            await self.set_state("idle")
        elif event == "double_press":
            pass

    # ---- outbound audio ----------------------------------------------------

    async def cancel_playback(self):
        if self.play_task and not self.play_task.done():
            self.play_task.cancel()
            try:
                await self.play_task
            except asyncio.CancelledError:
                pass
        self.play_task = None

    async def respond(self, pcm: bytes):
        await self.set_state("thinking")
        if self.args.record_dir and self.args.mode == "echo" and pcm:
            self.save_wav(pcm)
        await asyncio.sleep(0.3)
        if not pcm:
            log.info("[%s] nothing recorded", self.device_id)
            await self.set_state("idle")
            return
        await self.set_state("speaking")
        self.playback_done.clear()
        await self.send("audio_start")
        chunk = self.rate * 2 * SEND_CHUNK_MS // 1000
        start = time.monotonic()
        for i, off in enumerate(range(0, len(pcm), chunk)):
            await self.ws.send(pcm[off:off + chunk])
            if self.args.pace == "realtime":
                # Run ~100 ms ahead of real time, like a streaming TTS would.
                due = start + (i + 1) * SEND_CHUNK_MS / 1000 - 0.1
                delay = due - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
        await self.send("audio_end")
        duration = len(pcm) / (2 * self.rate)
        try:
            await asyncio.wait_for(self.playback_done.wait(), timeout=duration + 3)
        except asyncio.TimeoutError:
            log.warning("[%s] no playback_done, going idle anyway", self.device_id)
        await self.set_state("idle")

    def save_wav(self, pcm: bytes):
        os.makedirs(self.args.record_dir, exist_ok=True)
        path = os.path.join(self.args.record_dir,
                            f"{self.device_id}-{time.strftime('%Y%m%d-%H%M%S')}.wav")
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.rate)
            w.writeframes(pcm)
        log.info("[%s] saved %s (%.1f s)", self.device_id, path, len(pcm) / (2 * self.rate))


def make_process_request(token: str):
    expected = ("Bearer " + token).encode()

    def process_request(connection, request):
        got = request.headers.get("Authorization", "").encode()
        if not hmac.compare_digest(got, expected):
            log.warning("rejected connection from %s: bad or missing token",
                        connection.remote_address)
            return connection.respond(HTTPStatus.UNAUTHORIZED, "unauthorized\n")
        return None

    return process_request


def make_handler(args):
    async def handler(ws):
        session = DeviceSession(ws, args)
        log.info("device %s connected from %s", session.device_id, ws.remote_address)
        try:
            await session.run()
        except ConnectionClosed:
            pass
        finally:
            await session.cancel_playback()
            log.info("device %s disconnected", session.device_id)

    return handler


def build_ssl(args) -> Optional[ssl.SSLContext]:
    if not args.cert:
        return None
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(args.cert, args.key)
    return ctx


async def serve_forever(args, ready: Optional[asyncio.Future] = None):
    ctx = build_ssl(args)
    async with serve(make_handler(args), args.host, args.port,
                     process_request=make_process_request(args.token),
                     ssl=ctx, compression=None, max_size=2 ** 20) as server:
        port = server.sockets[0].getsockname()[1] if server.sockets else args.port
        log.info("bring-up gateway (%s mode) on %s://%s:%d/ - NOT the production gateway",
                 args.mode, "wss" if ctx else "ws", args.host, port)
        if ready is not None:
            ready.set_result(port)
        await asyncio.Future()


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="chat-node bring-up gateway stub (no AI, no API keys)")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--token", default=os.environ.get("CHATNODE_TOKEN"),
                   help="device token (or env CHATNODE_TOKEN)")
    p.add_argument("--mode", choices=("echo", "tone"), default="echo")
    p.add_argument("--cert", help="TLS certificate (PEM); enables wss://")
    p.add_argument("--key", help="TLS private key (PEM)")
    p.add_argument("--sample-rate", type=int, choices=SUPPORTED_RATES,
                   help="override the device's rate via config")
    p.add_argument("--jitter-ms", type=int, help="override the device's jitter buffer target")
    p.add_argument("--volume", type=int, help="send this speaker volume (0-100) on connect")
    p.add_argument("--pace", choices=("realtime", "burst"), default="realtime",
                   help="send playback at ~real time or all at once")
    p.add_argument("--record-dir", help="save each echo recording as a WAV file here")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    if not args.token:
        p.error("a token is required: --token or CHATNODE_TOKEN")
    if bool(args.cert) != bool(args.key):
        p.error("--cert and --key go together")
    return args


def main():
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if not args.verbose:
        logging.getLogger("websockets").setLevel(logging.WARNING)
    try:
        asyncio.run(serve_forever(args))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
