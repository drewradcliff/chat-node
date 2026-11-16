#include <stdatomic.h>
#include <string.h>
#include "app_state.h"

static atomic_int s_link = LINK_BOOTING;
static atomic_int s_conv = CONV_IDLE;
static atomic_bool s_fault;
static atomic_bool s_muted;
static atomic_bool s_full_duplex;
static atomic_bool s_reset_warning;
static _Atomic uint32_t s_epoch;
static _Atomic uint32_t s_rate = 24000;

static const char *const CONV_NAMES[] = {
    [CONV_IDLE] = "idle",
    [CONV_LISTENING] = "listening",
    [CONV_THINKING] = "thinking",
    [CONV_SPEAKING] = "speaking",
    [CONV_ERROR] = "error",
};

static const char *const LINK_NAMES[] = {
    [LINK_BOOTING] = "booting",
    [LINK_NEEDS_PROVISIONING] = "needs_provisioning",
    [LINK_WIFI_CONNECTING] = "wifi_connecting",
    [LINK_GATEWAY_CONNECTING] = "gateway_connecting",
    [LINK_READY] = "ready",
};

void app_state_init(bool muted, bool full_duplex, uint32_t sample_rate)
{
    atomic_store(&s_muted, muted);
    atomic_store(&s_full_duplex, full_duplex);
    atomic_store(&s_rate, app_state_rate_supported(sample_rate) ? sample_rate : 24000);
}

void app_state_set_link(link_state_t s)
{
    atomic_store(&s_link, (int)s);
    if (s != LINK_READY) {
        atomic_store(&s_conv, CONV_IDLE);
    }
}

link_state_t app_state_link(void) { return (link_state_t)atomic_load(&s_link); }

void app_state_set_conv(conv_state_t s) { atomic_store(&s_conv, (int)s); }
conv_state_t app_state_conv(void) { return (conv_state_t)atomic_load(&s_conv); }

void app_state_set_fault(bool f) { atomic_store(&s_fault, f); }
bool app_state_fault(void) { return atomic_load(&s_fault); }

void app_state_set_muted(bool muted)
{
    if (muted) {
        // Order matters: bump the epoch before the flag so the sender drops
        // anything captured under the old epoch.
        atomic_fetch_add(&s_epoch, 1);
    }
    atomic_store(&s_muted, muted);
}

bool app_state_muted(void) { return atomic_load(&s_muted); }
uint32_t app_state_mic_epoch(void) { return atomic_load(&s_epoch); }

void app_state_set_full_duplex(bool on) { atomic_store(&s_full_duplex, on); }
bool app_state_full_duplex(void) { return atomic_load(&s_full_duplex); }

bool app_state_rate_supported(uint32_t rate)
{
    return rate == 16000 || rate == 24000 || rate == 48000;
}

void app_state_set_sample_rate(uint32_t rate)
{
    if (app_state_rate_supported(rate)) {
        atomic_store(&s_rate, rate);
    }
}

uint32_t app_state_sample_rate(void) { return atomic_load(&s_rate); }

void app_state_set_reset_warning(bool on) { atomic_store(&s_reset_warning, on); }

bool app_state_mic_should_stream(void)
{
    if (atomic_load(&s_muted) || atomic_load(&s_link) != LINK_READY) {
        return false;
    }
    conv_state_t c = app_state_conv();
    if (c == CONV_LISTENING) {
        return true;
    }
    return atomic_load(&s_full_duplex) && (c == CONV_THINKING || c == CONV_SPEAKING);
}

led_state_t app_state_led_state(void)
{
    // Priority, highest first. Mute is a privacy indicator, so it beats
    // everything except boot and the factory-reset warning.
    if (atomic_load(&s_reset_warning)) return LED_FACTORY_RESET;
    link_state_t link = app_state_link();
    if (link == LINK_BOOTING) return LED_BOOTING;
    if (atomic_load(&s_muted)) return LED_MUTED;
    if (link == LINK_NEEDS_PROVISIONING) return LED_PROVISIONING;
    if (link == LINK_WIFI_CONNECTING) return LED_WIFI_CONNECTING;
    if (atomic_load(&s_fault)) return LED_ERROR;
    if (link == LINK_GATEWAY_CONNECTING) return LED_GATEWAY_CONNECTING;
    switch (app_state_conv()) {
    case CONV_LISTENING: return LED_LISTENING;
    case CONV_THINKING:  return LED_THINKING;
    case CONV_SPEAKING:  return LED_SPEAKING;
    case CONV_ERROR:     return LED_ERROR;
    case CONV_IDLE:
    default:             return LED_IDLE;
    }
}

const char *app_state_conv_name(conv_state_t s)
{
    return ((unsigned)s < sizeof(CONV_NAMES) / sizeof(CONV_NAMES[0])) ? CONV_NAMES[s] : "?";
}

bool app_state_conv_from_name(const char *name, conv_state_t *out)
{
    for (unsigned i = 0; i < sizeof(CONV_NAMES) / sizeof(CONV_NAMES[0]); i++) {
        if (strcmp(name, CONV_NAMES[i]) == 0) {
            *out = (conv_state_t)i;
            return true;
        }
    }
    return false;
}

const char *app_state_link_name(link_state_t s)
{
    return ((unsigned)s < sizeof(LINK_NAMES) / sizeof(LINK_NAMES[0])) ? LINK_NAMES[s] : "?";
}
