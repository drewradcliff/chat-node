#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_check.h"
#include "esp_timer.h"
#include "sdkconfig.h"
#include "board_pins.h"
#include "button.h"

static const char *TAG = "button";
static button_cb_t s_cb;

static inline uint32_t now_ms(void) { return (uint32_t)(esp_timer_get_time() / 1000); }

static void button_task(void *arg)
{
    bool raw_last = false, pressed = false;
    uint32_t raw_since = now_ms(), press_at = 0, release_at = 0;
    bool can_double = false, was_double = false;
    bool long_fired = false, warn_fired = false, reset_fired = false;
    TickType_t wake = xTaskGetTickCount();

    for (;;) {
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(5));
        uint32_t now = now_ms();
        bool raw = gpio_get_level(PIN_BUTTON) == 0;     // active low
        if (raw != raw_last) {
            raw_last = raw;
            raw_since = now;
        }
        if (raw != pressed && now - raw_since >= CONFIG_CHAT_NODE_DEBOUNCE_MS) {
            pressed = raw;
            if (pressed) {
                press_at = now;
                long_fired = warn_fired = reset_fired = false;
                s_cb(BUTTON_PRESS, 0);
                was_double = can_double && (now - release_at) <= CONFIG_CHAT_NODE_DOUBLE_PRESS_MS;
                if (was_double) {
                    s_cb(BUTTON_DOUBLE_PRESS, 0);
                }
            } else {
                s_cb(BUTTON_RELEASE, now - press_at);
                if (warn_fired && !reset_fired) {
                    s_cb(BUTTON_RESET_CANCEL, 0);
                }
                // A third quick press must not count as another double.
                can_double = !long_fired && !was_double;
                release_at = now;
            }
        }
        if (pressed) {
            uint32_t held = now - press_at;
            if (!long_fired && held >= CONFIG_CHAT_NODE_LONG_PRESS_MS) {
                long_fired = true;
                s_cb(BUTTON_LONG_PRESS, held);
            }
            if (!warn_fired && held >= CONFIG_CHAT_NODE_RESET_WARNING_MS) {
                warn_fired = true;
                s_cb(BUTTON_RESET_WARNING, held);
            }
            if (!reset_fired && held >= CONFIG_CHAT_NODE_FACTORY_RESET_MS) {
                reset_fired = true;
                s_cb(BUTTON_FACTORY_RESET, held);
            }
        }
    }
}

esp_err_t button_init(button_cb_t cb)
{
    s_cb = cb;
    gpio_config_t io = {
        .pin_bit_mask = 1ULL << PIN_BUTTON,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&io), TAG, "gpio");
    if (xTaskCreatePinnedToCore(button_task, "button", 3072, NULL, 8, NULL, 0) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}
