// Main button on PIN_BUTTON. A polling task (5 ms) debounces it and reports
// gestures. Press and release are reported at once (push-to-talk latency);
// long and double press are reported in addition to them, not instead.
#pragma once

#include <stdint.h>
#include "esp_err.h"

typedef enum {
    BUTTON_PRESS,
    BUTTON_RELEASE,         // duration_ms = how long it was held
    BUTTON_LONG_PRESS,      // fired while still held, at CONFIG_CHAT_NODE_LONG_PRESS_MS
    BUTTON_DOUBLE_PRESS,    // fired on the second press
    BUTTON_RESET_WARNING,   // held past CONFIG_CHAT_NODE_RESET_WARNING_MS
    BUTTON_RESET_CANCEL,    // released after the warning, before the reset
    BUTTON_FACTORY_RESET,   // held for CONFIG_CHAT_NODE_FACTORY_RESET_MS
} button_event_t;

// Called from the button task. Must not block for long.
typedef void (*button_cb_t)(button_event_t ev, uint32_t duration_ms);

esp_err_t button_init(button_cb_t cb);
