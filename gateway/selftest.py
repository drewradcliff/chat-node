#!/usr/bin/env python3
"""Self-test for the bring-up gateway stub: runs it in-process and drives it
with a fake chat-node device speaking PROTOCOL.md. No hardware needed."""

import asyncio
import json
import math
import struct
import sys

from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

import gateway

TOKEN = "selftest-token"
RATE = 24000


def frame(i):
    return b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * (i * 480 + n) / RATE)))
                    for n in range(480))


async def expect(ws, msg_type, timeout=5.0, **fields):
    """Read until a text message of msg_type arrives; return (msg, binary bytes seen)."""
    got_bytes = 0
    while True:
        m = await asyncio.wait_for(ws.recv(), timeout)
        if isinstance(m, bytes):
            got_bytes += len(m)
            continue
        msg = json.loads(m)
        if msg["type"] == msg_type and all(msg.get(k) == v for k, v in fields.items()):
            return msg, got_bytes


async def run():
    args = gateway.parse_args(["--host", "127.0.0.1", "--port", "0", "--token", TOKEN, "--pace", "burst"])
    ready = asyncio.get_running_loop().create_future()
    server = asyncio.create_task(gateway.serve_forever(args, ready))
    port = await ready
    uri = f"ws://127.0.0.1:{port}/"

    # 1. wrong token is refused at the upgrade
    try:
        async with connect(uri, additional_headers={"Authorization": "Bearer nope"}):
            raise AssertionError("bad token accepted")
    except InvalidStatus as e:
        assert e.response.status_code == 401, e
    print("ok  bad token -> 401")

    headers = {"Authorization": f"Bearer {TOKEN}", "X-Chat-Node-Id": "cn-selftest"}
    async with connect(uri, additional_headers=headers) as ws:
        await ws.send(json.dumps({"type": "hello", "protocol": 1, "device_id": "cn-selftest", "fw": "test",
                                  "sample_rate": RATE, "muted": False, "volume": 70}))
        await expect(ws, "welcome")
        await expect(ws, "state", state="idle")
        print("ok  hello -> welcome, idle")

        await ws.send(json.dumps({"type": "ping", "id": 7}))
        await expect(ws, "pong", id=7)
        print("ok  ping -> pong")

        # 2. echo turn
        await ws.send(json.dumps({"type": "button", "event": "press"}))
        await expect(ws, "state", state="listening")
        sent = b"".join(frame(i) for i in range(25))          # 0.5 s
        for i in range(25):
            await ws.send(sent[i * 960:(i + 1) * 960])
        await ws.send(json.dumps({"type": "button", "event": "release", "duration_ms": 600}))
        await expect(ws, "state", state="thinking")
        await expect(ws, "state", state="speaking")
        await expect(ws, "audio_start")
        _, nbytes = await expect(ws, "audio_end")
        assert nbytes == len(sent), (nbytes, len(sent))
        await ws.send(json.dumps({"type": "playback_done", "underruns": 0}))
        await expect(ws, "state", state="idle")
        print(f"ok  echo turn: {nbytes} bytes played back, idle after playback_done")

        # 3. barge-in during speaking
        await ws.send(json.dumps({"type": "button", "event": "press"}))
        await expect(ws, "state", state="listening")
        for i in range(10):
            await ws.send(frame(i))
        await ws.send(json.dumps({"type": "button", "event": "release", "duration_ms": 300}))
        await expect(ws, "state", state="speaking")
        await ws.send(json.dumps({"type": "button", "event": "press"}))
        await expect(ws, "audio_clear")
        await expect(ws, "state", state="listening")
        print("ok  press while speaking -> audio_clear, listening")

        # 4. long press (mute) cancels the turn
        await ws.send(json.dumps({"type": "mic_mute", "muted": True, "source": "button"}))
        await ws.send(json.dumps({"type": "button", "event": "long_press", "duration_ms": 1500}))
        await expect(ws, "state", state="idle")
        print("ok  mute + long_press -> idle")

    server.cancel()
    print("all passed")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except AssertionError as e:
        print("FAILED:", e)
        sys.exit(1)
