#pragma once

#include <stdint.h>

#define AUDIO_FRAME_MS          20
// The mic always runs at 48 kHz (inside the ICS-43434's 23-51.6 kHz normal
// mode) and is decimated to the wire rate, so wire rates must divide 48000.
#define AUDIO_MIC_RATE          48000
#define AUDIO_MAX_RATE          48000
#define AUDIO_MAX_FRAME_SAMPLES (AUDIO_MAX_RATE * AUDIO_FRAME_MS / 1000)

static inline uint32_t audio_frame_samples(uint32_t rate)
{
    return rate * AUDIO_FRAME_MS / 1000;
}
