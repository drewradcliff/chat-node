// Speaker playback. Owns I2S1 (TX), the amp shutdown pin and the "audio_out"
// task, which writes one 20 ms frame per iteration (silence when idle).
//
// Writers (the WebSocket task, console tests) push PCM into a PSRAM ring
// buffer and set markers; markers are recorded at the writer's position so
// they stay ordered with the audio around them.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "esp_err.h"

typedef void (*audio_out_done_cb_t)(void);

// reduce_ceiling: lower the output ceiling a further 6 dB (after a brown-out).
esp_err_t audio_out_init(bool reduce_ceiling);

// Copies 16-bit LE mono PCM at the current wire rate. Waits up to `wait` for
// space, then drops the rest. Returns bytes accepted.
size_t audio_out_write(const void *data, size_t len, TickType_t wait);
void audio_out_start(void);     // a stream begins: wake the amp, prebuffer
void audio_out_end(void);       // no more data for this stream: drain it
void audio_out_clear(void);     // flush now (barge-in, disconnect)

// Called from the audio task once a stream ended with audio_out_end() has
// fully played. Must not block.
void audio_out_set_done_cb(audio_out_done_cb_t cb);

void audio_out_set_volume(uint8_t level, bool muted);   // level 0-100
uint8_t audio_out_volume(void);
bool audio_out_speaker_muted(void);
void audio_out_set_jitter_ms(uint32_t ms);
uint32_t audio_out_jitter_ms(void);
int audio_out_ceiling_db(void);

uint32_t audio_out_buffered_ms(void);
uint32_t audio_out_underruns(void);
uint32_t audio_out_overflow_bytes(void);
bool audio_out_amp_on(void);
