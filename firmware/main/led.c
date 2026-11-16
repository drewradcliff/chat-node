#include <math.h>
#include <stdatomic.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "led_strip.h"
#include "sdkconfig.h"
#include "board_pins.h"
#include "app_state.h"
#include "led.h"

static const char *TAG = "led";

typedef enum { PAT_SOLID, PAT_BLINK, PAT_BREATHE } led_pattern_t;

typedef struct {
    uint8_t r, g, b;
    led_pattern_t pattern;
    uint16_t period_ms;     // blink/breathe period
} led_style_t;

// The one table to edit for colours and animations.
static const led_style_t LED_TABLE[LED_STATE_COUNT] = {
    [LED_BOOTING]            = { 255, 255, 255, PAT_SOLID,   0    },  // white
    [LED_PROVISIONING]       = { 255, 100,   0, PAT_BLINK,   1000 },  // orange slow blink
    [LED_WIFI_CONNECTING]    = {   0,   0, 255, PAT_BLINK,   500  },  // blue blink
    [LED_GATEWAY_CONNECTING] = { 255, 200,   0, PAT_BLINK,   500  },  // yellow blink
    [LED_IDLE]               = {   0,  80,   0, PAT_SOLID,   0    },  // dim green
    [LED_LISTENING]          = {   0,  60, 255, PAT_SOLID,   0    },  // blue
    [LED_THINKING]           = { 160,   0, 255, PAT_BREATHE, 1200 },  // purple breathing
    [LED_SPEAKING]           = {   0, 220, 200, PAT_BREATHE, 600  },  // cyan breathing
    [LED_MUTED]              = { 255,   0,   0, PAT_SOLID,   0    },  // red
    [LED_ERROR]              = { 255,   0,   0, PAT_BLINK,   250  },  // red fast blink
    [LED_FACTORY_RESET]      = { 255, 255, 255, PAT_BLINK,   150  },  // white strobe
};

static led_strip_handle_t s_strip;
static atomic_uint s_brightness = CONFIG_CHAT_NODE_LED_BRIGHTNESS;

void led_set_brightness(uint8_t b) { atomic_store(&s_brightness, b); }
uint8_t led_brightness(void) { return (uint8_t)atomic_load(&s_brightness); }

static float pattern_level(const led_style_t *st, uint32_t t_ms)
{
    if (st->pattern == PAT_SOLID || st->period_ms == 0) {
        return 1.0f;
    }
    float phase = (float)(t_ms % st->period_ms) / (float)st->period_ms;
    if (st->pattern == PAT_BLINK) {
        return phase < 0.5f ? 1.0f : 0.0f;
    }
    float v = 0.5f - 0.5f * cosf(2.0f * (float)M_PI * phase);
    return 0.05f + 0.95f * v * v;   // squared: looks more even to the eye
}

static void led_task(void *arg)
{
    uint8_t last_r = 1, last_g = 1, last_b = 1;
    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        const led_style_t *st = &LED_TABLE[app_state_led_state()];
        uint32_t t = (uint32_t)(esp_timer_get_time() / 1000);
        float k = pattern_level(st, t) * (float)atomic_load(&s_brightness) / 255.0f;
        uint8_t r = (uint8_t)(st->r * k), g = (uint8_t)(st->g * k), b = (uint8_t)(st->b * k);
        if (r != last_r || g != last_g || b != last_b) {
            // Colour order (GRB) is handled by led_strip's pixel format.
            led_strip_set_pixel(s_strip, 0, r, g, b);
            led_strip_refresh(s_strip);
            last_r = r; last_g = g; last_b = b;
        }
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(20));
    }
}

esp_err_t led_init(void)
{
    led_strip_config_t strip_cfg = {
        .strip_gpio_num = PIN_LED_DATA,
        .max_leds = 1,
        .led_pixel_format = LED_PIXEL_FORMAT_GRB,
        .led_model = LED_MODEL_SK6812,
        .flags.invert_out = false,  // the 74AHCT1G125 buffer does not invert
    };
    led_strip_rmt_config_t rmt_cfg = {
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = 10 * 1000 * 1000,
        .flags.with_dma = false,
    };
    esp_err_t err = led_strip_new_rmt_device(&strip_cfg, &rmt_cfg, &s_strip);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "led_strip init failed: %s", esp_err_to_name(err));
        return err;
    }
    led_strip_clear(s_strip);
    xTaskCreatePinnedToCore(led_task, "led", 3072, NULL, 3, NULL, 0);
    return ESP_OK;
}
