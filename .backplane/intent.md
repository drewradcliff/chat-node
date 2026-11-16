# Goal
A compact USB-C-powered Wi-Fi smart speaker for the kitchen or living room: a thin audio client (mic, speaker, button) that streams voice to an AI gateway on a Mac mini.

# Parts
- Main board — `boards/chat-node/` — custom ESP32-S3 PCB (48 x 37 mm, 2 layers) with I2S mic, I2S Class-D amp, RGB LED, USB-C. To be ordered, assembled.
- Enclosure — `mech/` — 3D-printed shell, base plate and translucent button cap. To be ordered.
- Firmware — `firmware/` — ESP-IDF audio client (WebSocket, 24 kHz 16-bit mono PCM). Not ordered.
- Gateway test stub — `gateway/` — small Python bring-up server, not the real Mac mini gateway. Not ordered.
- Speaker — bought: 40 mm, 4 ohm, 3 W (Same Sky CMS-4017-34SP), on a JST PH lead.
- Main button switch — bought: Kailh Choc V1 keyboard switch, hand soldered to the board (two pins).

# Notes
- No AI on the device and no OpenAI or third-party keys on it; the Mac mini gateway owns those.
- USB-C power only: no battery, no charging.
- One I2S MEMS mic, one small speaker, one large button, one RGB status LED.
- Pre-certified ESP32-S3 module with built-in antenna; native USB for programming.
- Half-duplex in revision one, but pins and hardware keep full-duplex possible.
- Cheap, simple to assemble, few unique parts; parts must ship to the United States.
- The board hangs component-side down under the lid: the mic listens and the LED shines up through the board.
