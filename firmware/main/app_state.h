// Shared device state. Every field is atomic so any task may read it without
// locks; the gateway owns the conversation state, the device owns mic mute.
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "led.h"

typedef enum {
    LINK_BOOTING = 0,
    LINK_NEEDS_PROVISIONING,
    LINK_WIFI_CONNECTING,
    LINK_GATEWAY_CONNECTING,
    LINK_READY,             // socket open and the gateway has sent "welcome"
} link_state_t;

typedef enum {
    CONV_IDLE = 0,
    CONV_LISTENING,
    CONV_THINKING,
    CONV_SPEAKING,
    CONV_ERROR,
} conv_state_t;

void app_state_init(bool muted, bool full_duplex, uint32_t sample_rate);

void app_state_set_link(link_state_t s);
link_state_t app_state_link(void);

void app_state_set_conv(conv_state_t s);
conv_state_t app_state_conv(void);

// Error shown on the LED (auth failure, gateway "error" message) until cleared.
void app_state_set_fault(bool fault);
bool app_state_fault(void);

// Muting bumps the mic epoch so frames already queued are discarded too.
void app_state_set_muted(bool muted);
bool app_state_muted(void);
uint32_t app_state_mic_epoch(void);

void app_state_set_full_duplex(bool on);
bool app_state_full_duplex(void);

bool app_state_rate_supported(uint32_t rate);
void app_state_set_sample_rate(uint32_t rate);
uint32_t app_state_sample_rate(void);

void app_state_set_reset_warning(bool on);

// True when captured mic audio may be sent to the gateway right now.
bool app_state_mic_should_stream(void);

led_state_t app_state_led_state(void);

const char *app_state_conv_name(conv_state_t s);
bool app_state_conv_from_name(const char *name, conv_state_t *out);
const char *app_state_link_name(link_state_t s);
