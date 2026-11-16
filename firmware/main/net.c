#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_random.h"
#include "sdkconfig.h"
#include "app_state.h"
#include "storage.h"
#include "net.h"

static const char *TAG = "net";

#define WIFI_UP_BIT BIT0

static EventGroupHandle_t s_ev;
static esp_netif_t *s_netif;
static esp_timer_handle_t s_retry_timer;
static uint32_t s_backoff_ms;
static bool s_started;

uint32_t net_backoff_next(uint32_t *state_ms)
{
    uint32_t cur = *state_ms < CONFIG_CHAT_NODE_BACKOFF_MIN_MS ? CONFIG_CHAT_NODE_BACKOFF_MIN_MS : *state_ms;
    uint32_t delay = cur / 2 + esp_random() % (cur / 2 + 1);
    uint32_t next = cur * 2;
    *state_ms = next > CONFIG_CHAT_NODE_BACKOFF_MAX_MS ? CONFIG_CHAT_NODE_BACKOFF_MAX_MS : next;
    return delay;
}

bool net_wifi_wait(TickType_t timeout)
{
    return (xEventGroupWaitBits(s_ev, WIFI_UP_BIT, pdFALSE, pdTRUE, timeout) & WIFI_UP_BIT) != 0;
}

bool net_wifi_is_up(void) { return (xEventGroupGetBits(s_ev) & WIFI_UP_BIT) != 0; }

int net_wifi_rssi(void)
{
    wifi_ap_record_t ap;
    return (net_wifi_is_up() && esp_wifi_sta_get_ap_info(&ap) == ESP_OK) ? ap.rssi : 0;
}

void net_ip_str(char *out, size_t len)
{
    esp_netif_ip_info_t ip;
    if (s_netif && net_wifi_is_up() && esp_netif_get_ip_info(s_netif, &ip) == ESP_OK) {
        snprintf(out, len, IPSTR, IP2STR(&ip.ip));
    } else {
        snprintf(out, len, "-");
    }
}

static void retry_cb(void *arg)
{
    esp_wifi_connect();
}

static void on_wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        app_state_set_link(LINK_WIFI_CONNECTING);
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        wifi_event_sta_disconnected_t *d = data;
        xEventGroupClearBits(s_ev, WIFI_UP_BIT);
        app_state_set_link(LINK_WIFI_CONNECTING);
        uint32_t delay = net_backoff_next(&s_backoff_ms);
        ESP_LOGW(TAG, "Wi-Fi disconnected (reason %d), retry in %u ms", d ? d->reason : -1, (unsigned)delay);
        esp_timer_stop(s_retry_timer);   // ESP_ERR_INVALID_STATE if not running: fine
        esp_timer_start_once(s_retry_timer, (uint64_t)delay * 1000);
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *e = data;
        ESP_LOGI(TAG, "got IP " IPSTR, IP2STR(&e->ip_info.ip));
        s_backoff_ms = 0;
        // The WebSocket supervisor moves the link state on from here.
        static gateway_cfg_t gw;    // too big for the event task stack
        app_state_set_link(storage_get_gateway(&gw) ? LINK_GATEWAY_CONNECTING : LINK_NEEDS_PROVISIONING);
        xEventGroupSetBits(s_ev, WIFI_UP_BIT);
    }
}

esp_err_t net_init(void)
{
    s_ev = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    s_netif = esp_netif_create_default_wifi_sta();
    esp_netif_set_hostname(s_netif, storage_device_id());

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    // Credentials are kept in our own namespace, not the Wi-Fi driver's.
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, on_wifi_event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, on_wifi_event, NULL));

    const esp_timer_create_args_t targs = { .callback = retry_cb, .name = "wifi_retry" };
    ESP_ERROR_CHECK(esp_timer_create(&targs, &s_retry_timer));
    return ESP_OK;
}

esp_err_t net_wifi_start(void)
{
    wifi_creds_t creds;
    if (!storage_get_wifi(&creds)) {
        ESP_LOGW(TAG, "no Wi-Fi credentials: use `wifi set <ssid> <pass>` on the console");
        app_state_set_link(LINK_NEEDS_PROVISIONING);
        return ESP_ERR_NOT_FOUND;
    }
    wifi_config_t wc = {0};
    memcpy(wc.sta.ssid, creds.ssid, strnlen(creds.ssid, sizeof(wc.sta.ssid)));
    memcpy(wc.sta.password, creds.pass, strnlen(creds.pass, sizeof(wc.sta.password)));
    wc.sta.threshold.authmode = creds.pass[0] ? WIFI_AUTH_WPA2_PSK : WIFI_AUTH_OPEN;
    wc.sta.sae_pwe_h2e = WPA3_SAE_PWE_BOTH;

    s_backoff_ms = 0;
    if (s_started) {
        // Reconnect with the new credentials; the disconnect event retries.
        esp_wifi_disconnect();
        esp_err_t err = esp_wifi_set_config(WIFI_IF_STA, &wc);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "set_config: %s (reboot to apply)", esp_err_to_name(err));
        }
        return err;
    }
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wc));
    ESP_ERROR_CHECK(esp_wifi_start());
#if CONFIG_CHAT_NODE_WIFI_PS_MIN_MODEM
    esp_wifi_set_ps(WIFI_PS_MIN_MODEM);
#else
    esp_wifi_set_ps(WIFI_PS_NONE);  // modem sleep adds 100+ ms of latency jitter
#endif
    s_started = true;
    ESP_LOGI(TAG, "connecting to \"%s\"", creds.ssid);
    return ESP_OK;
}
