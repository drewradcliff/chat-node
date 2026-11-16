// Persistent settings in NVS (namespace "chatnode"). Credentials, the gateway
// URL, token and certificate live only here, never in the source tree.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"

#define STORAGE_SSID_MAX    32
#define STORAGE_PASS_MAX    64
#define STORAGE_URL_MAX     256
#define STORAGE_TOKEN_MAX   256
#define STORAGE_CERT_MAX    8192

typedef struct {
    char ssid[STORAGE_SSID_MAX + 1];
    char pass[STORAGE_PASS_MAX + 1];
} wifi_creds_t;

typedef struct {
    char url[STORAGE_URL_MAX];
    char token[STORAGE_TOKEN_MAX];
    bool allow_insecure;    // permits ws:// (development only)
} gateway_cfg_t;

esp_err_t storage_init(void);

bool storage_get_wifi(wifi_creds_t *out);
esp_err_t storage_set_wifi(const char *ssid, const char *pass);

bool storage_get_gateway(gateway_cfg_t *out);
esp_err_t storage_set_gateway(const char *url, const char *token);
esp_err_t storage_set_insecure(bool allow);

// Returns a heap copy (NUL-terminated PEM) or NULL; caller frees.
char *storage_get_cert(void);
bool storage_has_cert(void);
esp_err_t storage_set_cert(const char *pem);   // NULL or "" clears it

uint8_t storage_get_volume(uint8_t def);
esp_err_t storage_set_volume(uint8_t v);
bool storage_get_muted(void);
esp_err_t storage_set_muted(bool m);

// Erases everything chat-node stored (credentials, gateway, cert, settings).
esp_err_t storage_factory_reset(void);

// "cn-" + Wi-Fi STA MAC in hex, e.g. "cn-a1b2c3d4e5f6".
const char *storage_device_id(void);
