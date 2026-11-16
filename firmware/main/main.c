#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_app_desc.h"
#include "sdkconfig.h"
#include "app.h"
#include "app_state.h"
#include "audio_in.h"
#include "audio_out.h"
#include "button.h"
#include "console_cmds.h"
#include "led.h"
#include "net.h"
#include "protocol.h"
#include "storage.h"
#include "ws_client.h"

static const char *TAG = "main";

void app_set_mic_muted(bool muted, const char *source)
{
    app_state_set_muted(muted);     // first: stops audio leaving at once
    ESP_LOGI(TAG, "mic %s (%s)", muted ? "MUTED" : "unmuted", source);
    protocol_send_mic_mute(muted, source);
    storage_set_muted(muted);
}

void app_factory_reset(void)
{
    storage_factory_reset();
    vTaskDelay(pdMS_TO_TICKS(200));
    esp_restart();
}

static void on_button(button_event_t ev, uint32_t duration_ms)
{
    static const char *const names[] = {
        [BUTTON_PRESS] = "press", [BUTTON_RELEASE] = "release", [BUTTON_LONG_PRESS] = "long_press",
        [BUTTON_DOUBLE_PRESS] = "double_press", [BUTTON_RESET_WARNING] = "reset_warning",
        [BUTTON_RESET_CANCEL] = "reset_cancel", [BUTTON_FACTORY_RESET] = "factory_reset",
    };
    ESP_LOGI(TAG, "button %s %u ms", names[ev], (unsigned)duration_ms);
    switch (ev) {
    case BUTTON_PRESS:
        protocol_send_button("press", 0);
        break;
    case BUTTON_RELEASE:
        protocol_send_button("release", duration_ms);
        break;
    case BUTTON_DOUBLE_PRESS:
        protocol_send_button("double_press", 0);
        break;
    case BUTTON_LONG_PRESS:
        app_set_mic_muted(!app_state_muted(), "button");
        protocol_send_button("long_press", duration_ms);
        break;
    case BUTTON_RESET_WARNING:
        ESP_LOGW(TAG, "keep holding to factory-reset stored credentials");
        app_state_set_reset_warning(true);
        break;
    case BUTTON_RESET_CANCEL:
        app_state_set_reset_warning(false);
        break;
    case BUTTON_FACTORY_RESET:
        app_factory_reset();
        break;
    }
}

static void on_playback_done(void)
{
    protocol_send_playback_done();
}

void app_main(void)
{
    const bool brownout = esp_reset_reason() == ESP_RST_BROWNOUT;
    ESP_LOGI(TAG, "chat-node %s, reset reason: %s", esp_app_get_description()->version, protocol_reset_reason());

    ESP_ERROR_CHECK(storage_init());
#if CONFIG_CHAT_NODE_FULL_DUPLEX
    const bool full_duplex = true;
#else
    const bool full_duplex = false;     // bool Kconfig symbols are undefined when "n"
#endif
    app_state_init(storage_get_muted(), full_duplex, CONFIG_CHAT_NODE_SAMPLE_RATE);
    ESP_LOGI(TAG, "device id %s", storage_device_id());

    // Amp pin is driven low inside audio_out_init before anything else plays.
    ESP_ERROR_CHECK(audio_out_init(brownout));
    audio_out_set_volume(storage_get_volume(CONFIG_CHAT_NODE_DEFAULT_VOLUME), false);
    audio_out_set_done_cb(on_playback_done);

    if (led_init() != ESP_OK) {
        ESP_LOGE(TAG, "LED unavailable, continuing without it");
    }
    ESP_ERROR_CHECK(audio_in_init());
    ESP_ERROR_CHECK(button_init(on_button));
    ESP_ERROR_CHECK(net_init());
    ESP_ERROR_CHECK(ws_client_start());
    if (console_start() != ESP_OK) {
        ESP_LOGE(TAG, "console unavailable");   // keep running: the device still works
    }

    if (net_wifi_start() == ESP_ERR_NOT_FOUND) {
        ESP_LOGW(TAG, "provisioning needed: type `help` on this console");
    }
    if (brownout) {
        ESP_LOGW(TAG, "previous reset was a brown-out: check the USB supply (needs 5 V / 500 mA+)");
    }
}
