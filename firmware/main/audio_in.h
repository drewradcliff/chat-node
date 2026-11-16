// Microphone capture. Owns I2S0 (RX) and the "audio_in" task.
//
// The task always runs (the ICS-43434 needs SCK to stay awake), converts each
// 20 ms block to 16-bit mono at the wire rate and, when app_state allows it,
// posts it to the mic message buffer that the WebSocket sender drains.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/message_buffer.h"
#include "esp_err.h"
#include "audio_common.h"

// One message in the mic buffer. Only epoch + the used part of pcm is stored.
typedef struct {
    uint32_t epoch;
    int16_t pcm[AUDIO_MAX_FRAME_SAMPLES];
} mic_frame_t;

esp_err_t audio_in_init(void);
MessageBufferHandle_t audio_in_frames(void);

void audio_in_set_gain_shift(uint8_t shift);
uint8_t audio_in_gain_shift(void);

// Level of the most recent 20 ms frame (16-bit scale), for `miclevel`.
void audio_in_level(uint32_t *rms, uint32_t *peak);
uint32_t audio_in_dropped_frames(void);

// Blocking: records `samples` at the current wire rate into `buf` (local only,
// nothing is sent). Returns false on timeout or if a capture is running.
bool audio_in_capture(int16_t *buf, size_t samples, TickType_t timeout);
