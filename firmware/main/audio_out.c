#include <math.h>
#include <string.h>
#include <stdatomic.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "driver/i2s_std.h"
#include "driver/gpio.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_task_wdt.h"
#include "esp_timer.h"
#include "sdkconfig.h"
#include "board_pins.h"
#include "audio_common.h"
#include "app_state.h"
#include "audio_out.h"

static const char *TAG = "audio_out";

#define RB_SIZE         ((uint32_t)CONFIG_CHAT_NODE_PLAYBACK_BUFFER_KB * 1024u)
#define RB_MASK         (RB_SIZE - 1u)
#define FADE_SAMPLES    64          // ~2.7 ms at 24 kHz: removes clicks at edges
#define PREBUF_GIVE_UP_MS 3000      // audio_start with no data: go idle again

_Static_assert((RB_SIZE & (RB_SIZE - 1u)) == 0, "CHAT_NODE_PLAYBACK_BUFFER_KB must be a power of two");

static i2s_chan_handle_t s_tx;
static uint8_t *s_rb;
// Free-running byte counters; index = counter & RB_MASK. s_w is advanced only
// by writers (under s_wlock), s_r only by the audio task.
static _Atomic uint32_t s_w, s_r;
static _Atomic uint32_t s_clear_pos, s_clear_seq;
static _Atomic uint32_t s_end_pos, s_end_seq;
static _Atomic uint32_t s_start_seq;
static _Atomic uint32_t s_last_write_ms;
static SemaphoreHandle_t s_wlock;

static _Atomic int32_t s_gain_q15;
static _Atomic uint32_t s_volume = CONFIG_CHAT_NODE_DEFAULT_VOLUME;
static atomic_bool s_spk_muted;
static _Atomic uint32_t s_jitter_ms = CONFIG_CHAT_NODE_JITTER_MS;
static _Atomic uint32_t s_underruns, s_overflow;
static atomic_bool s_amp_on;
static int s_ceiling_db = CONFIG_CHAT_NODE_OUTPUT_CEILING_DB;
static audio_out_done_cb_t s_done_cb;

static int16_t s_frame[AUDIO_MAX_FRAME_SAMPLES];

static inline uint32_t now_ms(void) { return (uint32_t)(esp_timer_get_time() / 1000); }

static void amp_enable(bool on)
{
    gpio_set_level(PIN_AMP_SD_MODE, on ? 1 : 0);
    atomic_store(&s_amp_on, on);
}

bool audio_out_amp_on(void) { return atomic_load(&s_amp_on); }
void audio_out_set_done_cb(audio_out_done_cb_t cb) { s_done_cb = cb; }
uint8_t audio_out_volume(void) { return (uint8_t)atomic_load(&s_volume); }
bool audio_out_speaker_muted(void) { return atomic_load(&s_spk_muted); }
uint32_t audio_out_jitter_ms(void) { return atomic_load(&s_jitter_ms); }
int audio_out_ceiling_db(void) { return s_ceiling_db; }
uint32_t audio_out_underruns(void) { return atomic_load(&s_underruns); }
uint32_t audio_out_overflow_bytes(void) { return atomic_load(&s_overflow); }

void audio_out_set_jitter_ms(uint32_t ms)
{
    if (ms < 20) ms = 20;
    if (ms > 1000) ms = 1000;
    atomic_store(&s_jitter_ms, ms);
}

uint32_t audio_out_buffered_ms(void)
{
    uint32_t bytes = atomic_load(&s_w) - atomic_load(&s_r);
    return bytes / 2u * 1000u / app_state_sample_rate();
}

// Volume maps linearly in dB: 100 -> 0 dB, 50 -> -20 dB, 1 -> -39.6 dB, 0 -> off.
// The ceiling is folded into the gain so full scale at volume 100 peaks at the
// ceiling instead of clipping.
void audio_out_set_volume(uint8_t level, bool muted)
{
    if (level > 100) level = 100;
    atomic_store(&s_volume, level);
    atomic_store(&s_spk_muted, muted);
    int32_t g = 0;
    if (!muted && level > 0) {
        float db = -40.0f + 0.4f * (float)level + (float)s_ceiling_db;
        float lin = powf(10.0f, db / 20.0f);
        g = (int32_t)(lin * 32768.0f);
        if (g > 32767) g = 32767;
    }
    atomic_store(&s_gain_q15, g);
}

size_t audio_out_write(const void *data, size_t len, TickType_t wait)
{
    const uint8_t *p = data;
    size_t done = 0;
    TickType_t start = xTaskGetTickCount();
    xSemaphoreTake(s_wlock, portMAX_DELAY);
    while (done < len) {
        uint32_t w = atomic_load_explicit(&s_w, memory_order_relaxed);
        uint32_t r = atomic_load_explicit(&s_r, memory_order_acquire);
        uint32_t space = RB_SIZE - (w - r);
        uint32_t n = (uint32_t)(len - done);
        if (n > space) {
            n = space & ~1u;    // keep sample alignment when only part fits
        }
        if (n == 0) {
            if (xTaskGetTickCount() - start >= wait) {
                break;
            }
            xSemaphoreGive(s_wlock);
            vTaskDelay(pdMS_TO_TICKS(5));
            xSemaphoreTake(s_wlock, portMAX_DELAY);
            continue;
        }
        uint32_t idx = w & RB_MASK;
        uint32_t first = RB_SIZE - idx;
        if (first > n) first = n;
        memcpy(s_rb + idx, p + done, first);
        memcpy(s_rb, p + done + first, n - first);
        atomic_store_explicit(&s_w, w + n, memory_order_release);
        done += n;
    }
    xSemaphoreGive(s_wlock);
    atomic_store(&s_last_write_ms, now_ms());
    if (done < len) {
        atomic_fetch_add(&s_overflow, (uint32_t)(len - done));
        ESP_LOGW(TAG, "playback buffer full, dropped %u bytes", (unsigned)(len - done));
    }
    return done;
}

static void mark(_Atomic uint32_t *pos, _Atomic uint32_t *seq)
{
    xSemaphoreTake(s_wlock, portMAX_DELAY);
    if (pos) {
        atomic_store_explicit(pos, atomic_load(&s_w), memory_order_relaxed);
    }
    atomic_fetch_add_explicit(seq, 1, memory_order_release);
    xSemaphoreGive(s_wlock);
}

void audio_out_start(void) { mark(NULL, &s_start_seq); }
void audio_out_end(void)   { mark(&s_end_pos, &s_end_seq); }
void audio_out_clear(void) { mark(&s_clear_pos, &s_clear_seq); }

static void rb_read(uint8_t *dst, uint32_t n)
{
    uint32_t r = atomic_load_explicit(&s_r, memory_order_relaxed);
    uint32_t idx = r & RB_MASK;
    uint32_t first = RB_SIZE - idx;
    if (first > n) first = n;
    memcpy(dst, s_rb + idx, first);
    memcpy(dst + first, s_rb, n - first);
    atomic_store_explicit(&s_r, r + n, memory_order_release);
}

static esp_err_t tx_init(uint32_t rate)
{
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(AMP_I2S_PORT, I2S_ROLE_MASTER);
    chan_cfg.dma_desc_num = 4;
    chan_cfg.dma_frame_num = 240;
    chan_cfg.auto_clear = true;     // DMA sends zeros if the task ever stalls
    ESP_RETURN_ON_ERROR(i2s_new_channel(&chan_cfg, &s_tx, NULL), TAG, "new channel");

    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(rate),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = PIN_AMP_BCLK,
            .ws = PIN_AMP_LRCLK,
            .dout = PIN_AMP_DIN,
            .din = I2S_GPIO_UNUSED,
            .invert_flags = { .mclk_inv = false, .bclk_inv = false, .ws_inv = false },
        },
    };
    // Mono data in both slots: the amp plays left (SD_MODE high), but this also
    // works if SD_MODE is ever strapped for right or (L+R)/2.
    std_cfg.slot_cfg.slot_mask = I2S_STD_SLOT_BOTH;
    ESP_RETURN_ON_ERROR(i2s_channel_init_std_mode(s_tx, &std_cfg), TAG, "init std");
    return i2s_channel_enable(s_tx);
}

static void tx_set_rate(uint32_t rate)
{
    i2s_std_clk_config_t clk = I2S_STD_CLK_DEFAULT_CONFIG(rate);
    i2s_channel_disable(s_tx);
    esp_err_t err = i2s_channel_reconfig_std_clock(s_tx, &clk);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "reconfig clock %u: %s", (unsigned)rate, esp_err_to_name(err));
    }
    i2s_channel_enable(s_tx);
}

typedef enum { ST_IDLE, ST_PREBUF, ST_PLAYING } play_state_t;

static void audio_out_task(void *arg)
{
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));

    uint32_t rate = app_state_sample_rate();
    uint32_t seen_clear = atomic_load(&s_clear_seq);
    uint32_t seen_end = atomic_load(&s_end_seq);
    uint32_t seen_start = atomic_load(&s_start_seq);
    play_state_t st = ST_IDLE;
    uint32_t st_since = now_ms();
    bool draining = false, rebuffering = false;
    uint32_t drain_pos = 0;
    uint32_t cleared_at = atomic_load(&s_w);
    int16_t last = 0;
    int fade_in = FADE_SAMPLES;

#define SET_ST(x) do { st = (x); st_since = now_ms(); } while (0)

    for (;;) {
        esp_task_wdt_reset();

        uint32_t want = app_state_sample_rate();
        if (want != rate) {
            amp_enable(false);
            tx_set_rate(want);
            rate = want;
            draining = false;
            last = 0;
            SET_ST(ST_IDLE);
        }
        const uint32_t fs = audio_frame_samples(rate);
        const uint32_t fb = fs * 2u;

        uint32_t seq = atomic_load_explicit(&s_clear_seq, memory_order_acquire);
        if (seq != seen_clear) {
            seen_clear = seq;
            uint32_t cp = atomic_load(&s_clear_pos);
            uint32_t r = atomic_load(&s_r);
            cleared_at = cp;
            if ((int32_t)(cp - r) > 0) {    // never move backwards
                atomic_store_explicit(&s_r, cp, memory_order_release);
            }
            draining = false;
            rebuffering = false;
            if (st != ST_IDLE) SET_ST(ST_IDLE);
        }
        seq = atomic_load_explicit(&s_end_seq, memory_order_acquire);
        if (seq != seen_end) {
            seen_end = seq;
            drain_pos = atomic_load(&s_end_pos);
            // An end recorded before a clear handled in this same pass belongs
            // to the flushed stream: no playback_done for it.
            draining = (int32_t)(drain_pos - cleared_at) >= 0;
        }
        seq = atomic_load_explicit(&s_start_seq, memory_order_acquire);
        if (seq != seen_start) {
            seen_start = seq;
            if (st == ST_IDLE) SET_ST(ST_PREBUF);
        }

        uint32_t r = atomic_load_explicit(&s_r, memory_order_relaxed);
        uint32_t avail = atomic_load_explicit(&s_w, memory_order_acquire) - r;

        if (draining && (int32_t)(drain_pos - r) <= 0) {
            draining = false;
            rebuffering = false;
            if (s_done_cb) s_done_cb();
            SET_ST(avail ? ST_PREBUF : ST_IDLE);
        }
        if (st == ST_IDLE && avail > 0) {
            SET_ST(ST_PREBUF);
        }
        if (st == ST_PREBUF) {
            if (!atomic_load(&s_amp_on)) {
                amp_enable(true);   // amp wakes during the prebuffer silence
            }
            uint32_t jit = atomic_load(&s_jitter_ms);
            uint32_t target = (rate * jit / 1000u) * 2u;
            if (rebuffering) target /= 2u;
            bool stalled = avail > 0 && (now_ms() - atomic_load(&s_last_write_ms)) > jit;
            if (avail >= target || (draining && avail > 0) || stalled) {
                SET_ST(ST_PLAYING);
                fade_in = 0;
                rebuffering = false;
            } else if (avail == 0 && now_ms() - st_since > PREBUF_GIVE_UP_MS) {
                SET_ST(ST_IDLE);
            }
        }

        uint32_t produced = 0;
        if (st == ST_PLAYING) {
            uint32_t limit = fb;
            if (draining && drain_pos - r < limit) {
                limit = drain_pos - r;
            }
            uint32_t n = (avail < limit ? avail : limit) & ~1u;
            rb_read((uint8_t *)s_frame, n);
            produced = n / 2u;
            const int32_t g = atomic_load(&s_gain_q15);
            for (uint32_t i = 0; i < produced; i++) {
                int32_t v = ((int32_t)s_frame[i] * g) >> 15;
                if (fade_in < FADE_SAMPLES) {
                    v = v * fade_in / FADE_SAMPLES;
                    fade_in++;
                }
                if (v > 32767) v = 32767;
                if (v < -32768) v = -32768;
                s_frame[i] = (int16_t)v;
            }
            if (produced) {
                last = s_frame[produced - 1];
            }
            if (produced < fs && !(draining && r + n == drain_pos)) {
                atomic_fetch_add(&s_underruns, 1);
                rebuffering = true;
                SET_ST(ST_PREBUF);
            }
        }
        if (produced < fs) {
            // Ramp from the last sample to zero, then silence.
            for (uint32_t i = produced; i < fs; i++) {
                uint32_t k = i - produced;
                s_frame[i] = (k < FADE_SAMPLES) ? (int16_t)((int32_t)last * (int32_t)(FADE_SAMPLES - k) / FADE_SAMPLES) : 0;
            }
            last = 0;
        }

        if (st == ST_IDLE && atomic_load(&s_amp_on) &&
            now_ms() - st_since > CONFIG_CHAT_NODE_AMP_IDLE_OFF_MS) {
            amp_enable(false);
        }

        size_t written = 0;
        // Blocks until DMA has room: this is what paces the loop at 20 ms.
        i2s_channel_write(s_tx, s_frame, fb, &written, pdMS_TO_TICKS(200));
    }
#undef SET_ST
}

esp_err_t audio_out_init(bool reduce_ceiling)
{
    gpio_config_t io = {
        .pin_bit_mask = 1ULL << PIN_AMP_SD_MODE,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_set_level(PIN_AMP_SD_MODE, 0);
    ESP_RETURN_ON_ERROR(gpio_config(&io), TAG, "amp pin");
    amp_enable(false);

    if (reduce_ceiling) {
        s_ceiling_db -= 6;
        ESP_LOGW(TAG, "last reset was a brown-out: output ceiling lowered to %d dBFS", s_ceiling_db);
    }
    s_rb = heap_caps_malloc(RB_SIZE, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    s_wlock = xSemaphoreCreateMutex();
    if (!s_rb || !s_wlock) {
        return ESP_ERR_NO_MEM;
    }
    atomic_store(&s_last_write_ms, now_ms());
    audio_out_set_volume(CONFIG_CHAT_NODE_DEFAULT_VOLUME, false);
    ESP_RETURN_ON_ERROR(tx_init(app_state_sample_rate()), TAG, "tx init");
    if (xTaskCreatePinnedToCore(audio_out_task, "audio_out", 4096, NULL, 19, NULL, 1) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}
