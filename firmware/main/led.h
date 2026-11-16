#pragma once

#include <stdint.h>
#include "esp_err.h"

typedef enum {
    LED_BOOTING = 0,
    LED_PROVISIONING,
    LED_WIFI_CONNECTING,
    LED_GATEWAY_CONNECTING,
    LED_IDLE,
    LED_LISTENING,
    LED_THINKING,
    LED_SPEAKING,
    LED_MUTED,
    LED_ERROR,
    LED_FACTORY_RESET,
    LED_STATE_COUNT
} led_state_t;

// Starts the LED task; it polls app_state_led_state() every 20 ms.
esp_err_t led_init(void);
void led_set_brightness(uint8_t brightness);
uint8_t led_brightness(void);
