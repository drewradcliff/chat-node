#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdatomic.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/event_groups.h"
#include "esp_websocket_client.h"
#include "esp_crt_bundle.h"
#include "esp_app_desc.h"
#include "esp_log.h"
#include "esp_task_wdt.h"
#include "esp_timer.h"
#include "sdkconfig.h"
#include "app_state.h"
#include "audio_in.h"
#include "audio_out.h"
#include "net.h"
#include "protocol.h"
#include "storage.h"
#include "ws_client.h"

static const char *TAG = "ws";

#define BIT_CONNECTED       BIT0
#define BIT_DISCONNECTED    BIT1
#define BIT_RECONFIG        BIT2

#define CONNECT_TIMEOUT_MS  15000
#define READY_TIMEOUT_MS    10000
#define SEND_TIMEOUT_MS     250
#define LOCK_WAIT_MS        50
#define RX_TEXT_MAX         2048

typedef struct {
    uint16_t len;
    char data[WS_CTRL_MAX];
} ctrl_msg_t;

static QueueHandle_t s_ctrl_q;
static EventGroupHandle_t s_ev;
static SemaphoreHandle_t s_client_lock;     // guards s_client against destroy
static esp_websocket_client_handle_t s_client;
static atomic_bool s_connected, s_ready;
static _Atomic uint32_t s_last_rx_ms;
static atomic_int s_last_http_status;

// Text reassembly; touched only by the esp_websocket_client task.
static char s_rx_text[RX_TEXT_MAX];
static size_t s_rx_len;
static bool s_rx_overflow;
static uint8_t s_last_op;

static inline uint32_t now_ms(void) { return (uint32_t)(esp_timer_get_time() / 1000); }

bool ws_client_connected(void) { return atomic_load(&s_connected); }
void ws_client_mark_ready(void) { atomic_store(&s_ready, true); }
void ws_client_reconfigure(void) { xEventGroupSetBits(s_ev, BIT_RECONFIG); }

bool ws_client_send_json(const char *json)
{
    if (!atomic_load(&s_connected)) {
        return false;
    }
    ctrl_msg_t m;
    size_t len = strlen(json);
    if (len >= WS_CTRL_MAX) {
        return false;
    }
    m.len = (uint16_t)len;
    memcpy(m.data, json, len + 1);
    return xQueueSend(s_ctrl_q, &m, 0) == pdTRUE;
}

static void handle_data(const esp_websocket_event_data_t *ev)
{
    uint8_t op = ev->op_code;
    if (op == 0x0) {
        op = s_last_op;                 // continuation frame
    } else if (op == 0x1 || op == 0x2) {
        s_last_op = op;
    } else {
        return;                         // ping/pong/close are handled by the client
    }
    atomic_store(&s_last_rx_ms, now_ms());

    if (op == 0x2) {
        if (ev->data_len > 0) {
            audio_out_write(ev->data_ptr, (size_t)ev->data_len, pdMS_TO_TICKS(500));
        }
        return;
    }
    // Text: one message per frame (fragmented text is not supported, see
    // PROTOCOL.md); the frame may still arrive in several chunks.
    if (ev->payload_offset == 0) {
        s_rx_len = 0;
        s_rx_overflow = false;
    }
    if (ev->data_len > 0) {
        if (s_rx_len + (size_t)ev->data_len < sizeof(s_rx_text)) {
            memcpy(s_rx_text + s_rx_len, ev->data_ptr, (size_t)ev->data_len);
            s_rx_len += (size_t)ev->data_len;
        } else {
            s_rx_overflow = true;
        }
    }
    if (ev->payload_offset + ev->data_len >= ev->payload_len) {
        if (s_rx_overflow) {
            ESP_LOGW(TAG, "text message too long (%d bytes), ignored", ev->payload_len);
        } else if (s_rx_len > 0) {
            protocol_handle_text(s_rx_text, s_rx_len);
        }
        s_rx_len = 0;
    }
}

static void on_ws_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    const esp_websocket_event_data_t *ev = data;
    switch (id) {
    case WEBSOCKET_EVENT_CONNECTED:
        ESP_LOGI(TAG, "connected");
        xQueueReset(s_ctrl_q);
        s_rx_len = 0;
        s_last_op = 0;
        atomic_store(&s_last_rx_ms, now_ms());
        atomic_store(&s_connected, true);
        protocol_send_hello();
        xEventGroupSetBits(s_ev, BIT_CONNECTED);
        break;
    case WEBSOCKET_EVENT_DISCONNECTED:
    case WEBSOCKET_EVENT_CLOSED:
        ESP_LOGW(TAG, "disconnected");
        atomic_store(&s_connected, false);
        atomic_store(&s_ready, false);
        audio_out_clear();      // nobody to finish the reply for: flush, amp goes off
        xEventGroupSetBits(s_ev, BIT_DISCONNECTED);
        break;
    case WEBSOCKET_EVENT_ERROR:
        if (ev && ev->error_handle.error_type == WEBSOCKET_ERROR_TYPE_HANDSHAKE) {
            int code = ev->error_handle.esp_ws_handshake_status_code;
            atomic_store(&s_last_http_status, code);
            ESP_LOGE(TAG, "handshake rejected: HTTP %d", code);
            if (code == 401 || code == 403) {
                app_state_set_fault(true);
            }
        } else {
            ESP_LOGE(TAG, "transport error");
        }
        break;
    case WEBSOCKET_EVENT_DATA:
        if (ev) {
            handle_data(ev);
        }
        break;
    default:
        break;
    }
}

static void ws_tx_task(void *arg)
{
    static ctrl_msg_t msg;
    static mic_frame_t frame;
    MessageBufferHandle_t mb = audio_in_frames();
    uint32_t fail_log_ms = 0;
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));

    for (;;) {
        esp_task_wdt_reset();
        // The lock is only held long by a teardown (destroy can wait for a hung
        // socket), so give up quickly and drop: this task is on the watchdog.
        while (xQueueReceive(s_ctrl_q, &msg, 0) == pdTRUE) {
            if (xSemaphoreTake(s_client_lock, pdMS_TO_TICKS(LOCK_WAIT_MS)) != pdTRUE) {
                continue;
            }
            if (s_client && atomic_load(&s_connected)) {
                esp_websocket_client_send_text(s_client, msg.data, msg.len, pdMS_TO_TICKS(SEND_TIMEOUT_MS));
            }
            xSemaphoreGive(s_client_lock);
        }

        size_t n = xMessageBufferReceive(mb, &frame, sizeof(frame), pdMS_TO_TICKS(10));
        if (n <= sizeof(uint32_t)) {
            continue;
        }
        // Mute is checked again here so frames queued before a mute never leave.
        if (!atomic_load(&s_ready) || app_state_muted() || frame.epoch != app_state_mic_epoch()) {
            continue;
        }
        if (xSemaphoreTake(s_client_lock, pdMS_TO_TICKS(LOCK_WAIT_MS)) != pdTRUE) {
            continue;
        }
        int sent = -1;
        if (s_client && atomic_load(&s_connected)) {
            sent = esp_websocket_client_send_bin(s_client, (const char *)frame.pcm,
                                                 (int)(n - sizeof(uint32_t)), pdMS_TO_TICKS(SEND_TIMEOUT_MS));
        }
        xSemaphoreGive(s_client_lock);
        if (sent < 0 && now_ms() - fail_log_ms > 2000) {
            fail_log_ms = now_ms();
            ESP_LOGW(TAG, "mic frame send failed");
        }
    }
}

static void teardown(bool wait_for_task_exit)
{
    atomic_store(&s_connected, false);
    atomic_store(&s_ready, false);
    if (wait_for_task_exit) {
        // With auto-reconnect off, the client task exits by itself after a
        // disconnect; give it time to finish before freeing it.
        vTaskDelay(pdMS_TO_TICKS(200));
    }
    xSemaphoreTake(s_client_lock, portMAX_DELAY);
    if (s_client) {
        esp_websocket_client_destroy(s_client);
        s_client = NULL;
    }
    xSemaphoreGive(s_client_lock);
    audio_out_clear();
    if (app_state_link() == LINK_READY || app_state_link() == LINK_GATEWAY_CONNECTING) {
        app_state_set_link(net_wifi_is_up() ? LINK_GATEWAY_CONNECTING : LINK_WIFI_CONNECTING);
    }
}

static bool url_allowed(const gateway_cfg_t *gw)
{
    if (strncmp(gw->url, "wss://", 6) == 0) {
        return true;
    }
    if (strncmp(gw->url, "ws://", 5) == 0) {
        if (gw->allow_insecure) {
            ESP_LOGW(TAG, "using unencrypted ws:// (development only)");
            return true;
        }
        ESP_LOGE(TAG, "ws:// refused; use wss:// or `gateway insecure on` for development");
        return false;
    }
    ESP_LOGE(TAG, "gateway URL must start with wss:// or ws://");
    return false;
}

static void ws_sup_task(void *arg)
{
    static gateway_cfg_t gw;
    static char headers[STORAGE_TOKEN_MAX + 96];
    static char user_agent[48];
    uint32_t backoff = 0;

    snprintf(user_agent, sizeof(user_agent), "chat-node/%s", esp_app_get_description()->version);

    for (;;) {
        xEventGroupClearBits(s_ev, BIT_RECONFIG);
        net_wifi_wait(portMAX_DELAY);

        if (!storage_get_gateway(&gw) || !url_allowed(&gw)) {
            ESP_LOGW(TAG, "no usable gateway: `gateway set <wss://host:port/path> <token>`");
            app_state_set_link(LINK_NEEDS_PROVISIONING);
            xEventGroupWaitBits(s_ev, BIT_RECONFIG, pdTRUE, pdFALSE, portMAX_DELAY);
            if (net_wifi_is_up()) app_state_set_link(LINK_GATEWAY_CONNECTING);
            continue;
        }

        char *cert = storage_get_cert();
        snprintf(headers, sizeof(headers), "Authorization: Bearer %s\r\nX-Chat-Node-Id: %s\r\n",
                 gw.token, storage_device_id());

        esp_websocket_client_config_t cfg = {
            .uri = gw.url,
            .headers = headers,
            .user_agent = user_agent,
            .disable_auto_reconnect = true,     // we do backoff with jitter ourselves
            .buffer_size = 4096,
            .task_prio = 12,
            .task_stack = 6144,
            .network_timeout_ms = 10000,
            .ping_interval_sec = 5,
            .pingpong_timeout_sec = 20,
        };
        if (cert) {
            cfg.cert_pem = cert;                // pinned gateway cert or its CA
            cfg.cert_len = 0;                   // NUL-terminated
        } else if (strncmp(gw.url, "wss://", 6) == 0) {
            ESP_LOGW(TAG, "no pinned certificate; verifying against the public CA bundle");
            cfg.crt_bundle_attach = esp_crt_bundle_attach;
        }

        app_state_set_link(LINK_GATEWAY_CONNECTING);
        xEventGroupClearBits(s_ev, BIT_CONNECTED | BIT_DISCONNECTED);
        atomic_store(&s_last_http_status, 0);
        ESP_LOGI(TAG, "connecting to %s", gw.url);

        xSemaphoreTake(s_client_lock, portMAX_DELAY);
        s_client = esp_websocket_client_init(&cfg);
        if (s_client) {
            esp_websocket_register_events(s_client, WEBSOCKET_EVENT_ANY, on_ws_event, NULL);
            if (esp_websocket_client_start(s_client) != ESP_OK) {
                esp_websocket_client_destroy(s_client);
                s_client = NULL;
            }
        }
        xSemaphoreGive(s_client_lock);

        bool was_ready = false;
        bool reconfig = false;
        bool ended_by_event = false;
        if (s_client) {
            EventBits_t b = xEventGroupWaitBits(s_ev, BIT_CONNECTED | BIT_DISCONNECTED | BIT_RECONFIG,
                                                pdFALSE, pdFALSE, pdMS_TO_TICKS(CONNECT_TIMEOUT_MS));
            if ((b & BIT_CONNECTED) && !(b & BIT_DISCONNECTED)) {
                uint32_t connected_at = now_ms();
                uint32_t last_ping = now_ms();
                for (;;) {
                    b = xEventGroupWaitBits(s_ev, BIT_DISCONNECTED | BIT_RECONFIG, pdFALSE, pdFALSE,
                                            pdMS_TO_TICKS(1000));
                    if (b & BIT_DISCONNECTED) { ended_by_event = true; break; }
                    if (b & BIT_RECONFIG) break;
                    if (!net_wifi_is_up()) { ESP_LOGW(TAG, "Wi-Fi lost"); break; }
                    uint32_t now = now_ms();
                    if (atomic_load(&s_ready)) {
                        was_ready = true;
                    } else if (now - connected_at > READY_TIMEOUT_MS) {
                        ESP_LOGW(TAG, "no welcome from gateway"); break;
                    }
                    if (now - last_ping >= CONFIG_CHAT_NODE_KEEPALIVE_S * 1000u) {
                        last_ping = now;
                        protocol_send_ping();
                    }
                    if (now - atomic_load(&s_last_rx_ms) > 3u * CONFIG_CHAT_NODE_KEEPALIVE_S * 1000u) {
                        ESP_LOGW(TAG, "gateway silent, reconnecting"); break;
                    }
                }
            } else {
                ended_by_event = (b & BIT_DISCONNECTED) != 0;
                if (!(b & (BIT_CONNECTED | BIT_DISCONNECTED | BIT_RECONFIG))) {
                    ESP_LOGW(TAG, "connect timed out");
                }
            }
            reconfig = (xEventGroupGetBits(s_ev) & BIT_RECONFIG) != 0;
        }

        teardown(ended_by_event);
        free(cert);

        if (was_ready) {
            backoff = 0;
        }
        if (reconfig) {
            continue;
        }
        uint32_t delay = net_backoff_next(&backoff);
        int status = atomic_load(&s_last_http_status);
        ESP_LOGI(TAG, "reconnecting in %u ms%s", (unsigned)delay,
                 (status == 401 || status == 403) ? " (token rejected)" : "");
        xEventGroupWaitBits(s_ev, BIT_RECONFIG, pdFALSE, pdFALSE, pdMS_TO_TICKS(delay));
    }
}

esp_err_t ws_client_start(void)
{
    s_ctrl_q = xQueueCreate(16, sizeof(ctrl_msg_t));
    s_ev = xEventGroupCreate();
    s_client_lock = xSemaphoreCreateMutex();
    if (!s_ctrl_q || !s_ev || !s_client_lock) {
        return ESP_ERR_NO_MEM;
    }
    if (xTaskCreatePinnedToCore(ws_tx_task, "ws_tx", 4096, NULL, 10, NULL, 0) != pdPASS ||
        xTaskCreatePinnedToCore(ws_sup_task, "ws_sup", 6144, NULL, 5, NULL, 0) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}
