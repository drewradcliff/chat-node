#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "storage.h"

static const char *TAG = "storage";
static const char *NS = "chatnode";
static char s_device_id[20];

esp_err_t storage_init(void)
{
    // With CONFIG_NVS_ENCRYPTION enabled this also sets up the encrypted
    // partition (keys from nvs_keys or HMAC); nothing else changes here.
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS partition unusable (%s), erasing", esp_err_to_name(err));
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    if (err != ESP_OK) {
        return err;
    }
    uint8_t mac[6] = {0};
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(s_device_id, sizeof(s_device_id), "cn-%02x%02x%02x%02x%02x%02x",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    return ESP_OK;
}

const char *storage_device_id(void) { return s_device_id; }

static bool get_str(nvs_handle_t h, const char *key, char *out, size_t len)
{
    size_t l = len;
    return nvs_get_str(h, key, out, &l) == ESP_OK;
}

bool storage_get_wifi(wifi_creds_t *out)
{
    nvs_handle_t h;
    memset(out, 0, sizeof(*out));
    if (nvs_open(NS, NVS_READONLY, &h) != ESP_OK) {
        return false;
    }
    bool ok = get_str(h, "wifi_ssid", out->ssid, sizeof(out->ssid)) && out->ssid[0];
    if (ok && !get_str(h, "wifi_pass", out->pass, sizeof(out->pass))) {
        out->pass[0] = '\0';
    }
    nvs_close(h);
    return ok;
}

static esp_err_t write_begin(nvs_handle_t *h) { return nvs_open(NS, NVS_READWRITE, h); }

static esp_err_t write_end(nvs_handle_t h, esp_err_t err)
{
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    nvs_close(h);
    return err;
}

esp_err_t storage_set_wifi(const char *ssid, const char *pass)
{
    if (!ssid || strlen(ssid) == 0 || strlen(ssid) > STORAGE_SSID_MAX ||
        !pass || strlen(pass) > STORAGE_PASS_MAX) {
        return ESP_ERR_INVALID_ARG;
    }
    nvs_handle_t h;
    esp_err_t err = write_begin(&h);
    if (err != ESP_OK) return err;
    err = nvs_set_str(h, "wifi_ssid", ssid);
    if (err == ESP_OK) err = nvs_set_str(h, "wifi_pass", pass);
    return write_end(h, err);
}

bool storage_get_gateway(gateway_cfg_t *out)
{
    nvs_handle_t h;
    memset(out, 0, sizeof(*out));
    if (nvs_open(NS, NVS_READONLY, &h) != ESP_OK) {
        return false;
    }
    bool ok = get_str(h, "gw_url", out->url, sizeof(out->url)) && out->url[0] &&
              get_str(h, "gw_token", out->token, sizeof(out->token));
    uint8_t insecure = 0;
    nvs_get_u8(h, "gw_insecure", &insecure);
    out->allow_insecure = insecure != 0;
    nvs_close(h);
    return ok;
}

esp_err_t storage_set_gateway(const char *url, const char *token)
{
    if (!url || !token || strlen(url) >= STORAGE_URL_MAX || strlen(token) >= STORAGE_TOKEN_MAX) {
        return ESP_ERR_INVALID_ARG;
    }
    nvs_handle_t h;
    esp_err_t err = write_begin(&h);
    if (err != ESP_OK) return err;
    err = nvs_set_str(h, "gw_url", url);
    if (err == ESP_OK) err = nvs_set_str(h, "gw_token", token);
    return write_end(h, err);
}

esp_err_t storage_set_insecure(bool allow)
{
    nvs_handle_t h;
    esp_err_t err = write_begin(&h);
    if (err != ESP_OK) return err;
    return write_end(h, nvs_set_u8(h, "gw_insecure", allow ? 1 : 0));
}

char *storage_get_cert(void)
{
    nvs_handle_t h;
    if (nvs_open(NS, NVS_READONLY, &h) != ESP_OK) {
        return NULL;
    }
    size_t len = 0;
    char *pem = NULL;
    if (nvs_get_blob(h, "gw_cert", NULL, &len) == ESP_OK && len > 1) {
        pem = malloc(len + 1);
        if (pem && nvs_get_blob(h, "gw_cert", pem, &len) == ESP_OK) {
            pem[len] = '\0';
        } else {
            free(pem);
            pem = NULL;
        }
    }
    nvs_close(h);
    return pem;
}

bool storage_has_cert(void)
{
    char *pem = storage_get_cert();
    bool has = pem != NULL;
    free(pem);
    return has;
}

esp_err_t storage_set_cert(const char *pem)
{
    nvs_handle_t h;
    esp_err_t err = write_begin(&h);
    if (err != ESP_OK) return err;
    if (!pem || !pem[0]) {
        err = nvs_erase_key(h, "gw_cert");
        if (err == ESP_ERR_NVS_NOT_FOUND) err = ESP_OK;
    } else {
        size_t len = strlen(pem);
        err = len < STORAGE_CERT_MAX ? nvs_set_blob(h, "gw_cert", pem, len + 1) : ESP_ERR_INVALID_SIZE;
    }
    return write_end(h, err);
}

uint8_t storage_get_volume(uint8_t def)
{
    nvs_handle_t h;
    uint8_t v = def;
    if (nvs_open(NS, NVS_READONLY, &h) == ESP_OK) {
        nvs_get_u8(h, "volume", &v);
        nvs_close(h);
    }
    return v > 100 ? def : v;
}

esp_err_t storage_set_volume(uint8_t v)
{
    nvs_handle_t h;
    esp_err_t err = write_begin(&h);
    if (err != ESP_OK) return err;
    return write_end(h, nvs_set_u8(h, "volume", v));
}

bool storage_get_muted(void)
{
    nvs_handle_t h;
    uint8_t m = 0;
    if (nvs_open(NS, NVS_READONLY, &h) == ESP_OK) {
        nvs_get_u8(h, "mic_muted", &m);
        nvs_close(h);
    }
    return m != 0;
}

esp_err_t storage_set_muted(bool m)
{
    nvs_handle_t h;
    esp_err_t err = write_begin(&h);
    if (err != ESP_OK) return err;
    return write_end(h, nvs_set_u8(h, "mic_muted", m ? 1 : 0));
}

esp_err_t storage_factory_reset(void)
{
    nvs_handle_t h;
    esp_err_t err = write_begin(&h);
    if (err != ESP_OK) return err;
    ESP_LOGW(TAG, "factory reset: erasing stored credentials and settings");
    return write_end(h, nvs_erase_all(h));
}
