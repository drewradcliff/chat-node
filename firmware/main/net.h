// Wi-Fi station: connects with the stored credentials and reconnects forever
// with exponential backoff + jitter. Owns no task; runs from event callbacks.
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "esp_err.h"

esp_err_t net_init(void);
// Loads credentials and (re)connects. ESP_ERR_NOT_FOUND if none are stored.
esp_err_t net_wifi_start(void);
bool net_wifi_wait(TickType_t timeout);
bool net_wifi_is_up(void);
int net_wifi_rssi(void);
void net_ip_str(char *out, size_t len);

// Exponential backoff with "equal jitter": half fixed, half random.
uint32_t net_backoff_next(uint32_t *state_ms);
