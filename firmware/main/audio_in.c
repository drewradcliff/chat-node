#include <math.h>
#include <string.h>
#include <stdatomic.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "driver/i2s_std.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_task_wdt.h"
#include "sdkconfig.h"
#include "board_pins.h"
#include "app_state.h"
#include "audio_in.h"

static const char *TAG = "audio_in";

#define MIC_FRAME       (AUDIO_MIC_RATE * AUDIO_FRAME_MS / 1000)   // 960 samples
#define NTAPS           47
// ICS-43434 start-up is ~85 ms after clocks start; output before that is junk.
#define WARMUP_FRAMES   (100 / AUDIO_FRAME_MS)
#define MB_FRAMES       (CONFIG_CHAT_NODE_MIC_QUEUE_MS / AUDIO_FRAME_MS)
#define MB_BYTES        (MB_FRAMES * (sizeof(mic_frame_t) + sizeof(size_t)))

static i2s_chan_handle_t s_rx;
static MessageBufferHandle_t s_mb;
static StaticMessageBuffer_t s_mb_struct;

// Hot-path buffers: static, never allocated per frame.
static int32_t s_raw[MIC_FRAME];
static float s_fir[NTAPS - 1 + MIC_FRAME];
static float s_taps[NTAPS];
static mic_frame_t s_msg;

static _Atomic uint32_t s_gain_shift = CONFIG_CHAT_NODE_MIC_GAIN_SHIFT;
static _Atomic uint32_t s_rms, s_peak, s_dropped;

static portMUX_TYPE s_cap_mux = portMUX_INITIALIZER_UNLOCKED;
static int16_t *s_cap_buf;
static size_t s_cap_len, s_cap_pos;
static SemaphoreHandle_t s_cap_done;

MessageBufferHandle_t audio_in_frames(void) { return s_mb; }
void audio_in_set_gain_shift(uint8_t shift) { atomic_store(&s_gain_shift, shift > 8 ? 8 : shift); }
uint8_t audio_in_gain_shift(void) { return (uint8_t)atomic_load(&s_gain_shift); }
uint32_t audio_in_dropped_frames(void) { return atomic_load(&s_dropped); }

void audio_in_level(uint32_t *rms, uint32_t *peak)
{
    *rms = atomic_load(&s_rms);
    *peak = atomic_load(&s_peak);
}

// Windowed-sinc low-pass for decimation by `decim`, cutoff at 90 % of the
// output Nyquist. Runs only when the wire rate changes.
static void design_taps(int decim)
{
    const float wc = 0.9f / (float)decim;     // relative to input Nyquist
    const int m = (NTAPS - 1) / 2;
    float sum = 0;
    for (int n = 0; n < NTAPS; n++) {
        int k = n - m;
        float x = (float)M_PI * wc * (float)k;
        float sinc = (k == 0) ? 1.0f : sinf(x) / x;
        float win = 0.54f - 0.46f * cosf(2.0f * (float)M_PI * (float)n / (float)(NTAPS - 1));
        s_taps[n] = wc * sinc * win;
        sum += s_taps[n];
    }
    for (int n = 0; n < NTAPS; n++) {
        s_taps[n] /= sum;
    }
    memset(s_fir, 0, sizeof(s_fir));
}

static esp_err_t rx_init(void)
{
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(MIC_I2S_PORT, I2S_ROLE_MASTER);
    chan_cfg.dma_desc_num = 6;
    chan_cfg.dma_frame_num = 240;   // 5 ms per descriptor at 48 kHz
    ESP_RETURN_ON_ERROR(i2s_new_channel(&chan_cfg, NULL, &s_rx), TAG, "new channel");

    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(AUDIO_MIC_RATE),
        // 24-bit data in 32-bit slots, Philips I2S, BCLK = 64 fs = 3.072 MHz.
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = PIN_MIC_SCK,
            .ws = PIN_MIC_WS,
            .dout = I2S_GPIO_UNUSED,
            .din = PIN_MIC_SD,
            .invert_flags = { .mclk_inv = false, .bclk_inv = false, .ws_inv = false },
        },
    };
    std_cfg.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT;   // LR pin tied to GND
    ESP_RETURN_ON_ERROR(i2s_channel_init_std_mode(s_rx, &std_cfg), TAG, "init std");
    return i2s_channel_enable(s_rx);
}

static void capture_feed(const int16_t *pcm, size_t n)
{
    bool done = false;
    taskENTER_CRITICAL(&s_cap_mux);
    if (s_cap_buf) {
        size_t take = s_cap_len - s_cap_pos;
        if (take > n) take = n;
        memcpy(s_cap_buf + s_cap_pos, pcm, take * sizeof(int16_t));
        s_cap_pos += take;
        if (s_cap_pos >= s_cap_len) {
            s_cap_buf = NULL;
            done = true;
        }
    }
    taskEXIT_CRITICAL(&s_cap_mux);
    if (done) {
        xSemaphoreGive(s_cap_done);
    }
}

bool audio_in_capture(int16_t *buf, size_t samples, TickType_t timeout)
{
    taskENTER_CRITICAL(&s_cap_mux);
    bool busy = s_cap_buf != NULL;
    if (!busy) {
        xSemaphoreTake(s_cap_done, 0);  // clear a stale give
        s_cap_buf = buf;
        s_cap_len = samples;
        s_cap_pos = 0;
    }
    taskEXIT_CRITICAL(&s_cap_mux);
    if (busy) {
        return false;
    }
    if (xSemaphoreTake(s_cap_done, timeout) == pdTRUE) {
        return true;
    }
    taskENTER_CRITICAL(&s_cap_mux);
    s_cap_buf = NULL;
    taskEXIT_CRITICAL(&s_cap_mux);
    return false;
}

static void audio_in_task(void *arg)
{
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));

    // One-pole DC blocker: y = x - x1 + a*y1, a = 1 - 2*pi*fc/fs.
    const float a = 1.0f - 2.0f * (float)M_PI * (float)CONFIG_CHAT_NODE_MIC_HPF_HZ / (float)AUDIO_MIC_RATE;
    float x1 = 0, y1 = 0;
    uint32_t rate = 0;
    int decim = 1;
    int warmup = WARMUP_FRAMES;

    for (;;) {
        esp_task_wdt_reset();

        uint32_t want = app_state_sample_rate();
        if (want != rate) {
            rate = want;
            decim = (int)(AUDIO_MIC_RATE / rate);
            design_taps(decim);
            ESP_LOGI(TAG, "wire rate %u Hz (decimate by %d)", (unsigned)rate, decim);
        }

        size_t got = 0;
        esp_err_t err = i2s_channel_read(s_rx, s_raw, sizeof(s_raw), &got, pdMS_TO_TICKS(200));
        if (err != ESP_OK || got != sizeof(s_raw)) {
            ESP_LOGW(TAG, "i2s read: %s (%u bytes)", esp_err_to_name(err), (unsigned)got);
            continue;
        }
        if (warmup > 0) {
            warmup--;
            continue;
        }

        for (int i = 0; i < MIC_FRAME; i++) {
            float x = (float)(s_raw[i] >> 8);          // 24-bit signed, MSB aligned
            float y = x - x1 + a * y1;
            x1 = x;
            y1 = y;
            s_fir[NTAPS - 1 + i] = y;
        }

        const float scale = (float)(1u << atomic_load(&s_gain_shift)) / 256.0f;
        const int out_n = MIC_FRAME / decim;
        uint32_t peak = 0;
        uint64_t sumsq = 0;
        for (int k = 0; k < out_n; k++) {
            float acc;
            if (decim == 1) {
                acc = s_fir[NTAPS - 1 + k];
            } else {
                const float *src = &s_fir[k * decim];
                acc = 0;
                for (int j = 0; j < NTAPS; j++) {
                    acc += s_taps[j] * src[j];
                }
            }
            float v = acc * scale;
            int32_t s = (int32_t)lrintf(v);
            if (s > 32767) s = 32767;
            if (s < -32768) s = -32768;
            s_msg.pcm[k] = (int16_t)s;
            uint32_t mag = (uint32_t)(s < 0 ? -s : s);
            if (mag > peak) peak = mag;
            sumsq += (uint64_t)((int64_t)s * s);
        }
        memmove(s_fir, &s_fir[MIC_FRAME], (NTAPS - 1) * sizeof(float));

        atomic_store(&s_peak, peak);
        atomic_store(&s_rms, (uint32_t)sqrtf((float)(sumsq / (uint64_t)out_n)));

        capture_feed(s_msg.pcm, (size_t)out_n);

        if (app_state_mic_should_stream()) {
            s_msg.epoch = app_state_mic_epoch();
            size_t len = sizeof(uint32_t) + (size_t)out_n * sizeof(int16_t);
            // Never block: if the network is behind, drop this frame.
            if (xMessageBufferSend(s_mb, &s_msg, len, 0) != len) {
                atomic_fetch_add(&s_dropped, 1);
            }
        }
    }
}

esp_err_t audio_in_init(void)
{
    uint8_t *storage = heap_caps_malloc(MB_BYTES + 1, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!storage) {
        return ESP_ERR_NO_MEM;
    }
    s_mb = xMessageBufferCreateStatic(MB_BYTES, storage, &s_mb_struct);
    s_cap_done = xSemaphoreCreateBinary();
    if (!s_mb || !s_cap_done) {
        return ESP_ERR_NO_MEM;
    }
    ESP_RETURN_ON_ERROR(rx_init(), TAG, "rx init");
    if (xTaskCreatePinnedToCore(audio_in_task, "audio_in", 4096, NULL, 18, NULL, 1) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}
