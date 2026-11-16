#include <string.h>
#include "cJSON.h"
#include "esp_log.h"
#include "esp_app_desc.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "app_state.h"
#include "audio_in.h"
#include "audio_out.h"
#include "led.h"
#include "storage.h"
#include "ws_client.h"
#include "protocol.h"

static const char *TAG = "protocol";
static uint32_t s_ping_id;

const char *protocol_reset_reason(void)
{
    switch (esp_reset_reason()) {
    case ESP_RST_POWERON:   return "poweron";
    case ESP_RST_SW:        return "software";
    case ESP_RST_PANIC:     return "panic";
    case ESP_RST_INT_WDT:
    case ESP_RST_TASK_WDT:
    case ESP_RST_WDT:       return "watchdog";
    case ESP_RST_BROWNOUT:  return "brownout";
    case ESP_RST_DEEPSLEEP: return "deepsleep";
    case ESP_RST_EXT:       return "external";
    case ESP_RST_USB:       return "usb";
    default:                return "other";
    }
}

static cJSON *msg_new(const char *type)
{
    cJSON *m = cJSON_CreateObject();
    if (m) {
        cJSON_AddStringToObject(m, "type", type);
    }
    return m;
}

static void msg_send(cJSON *m)
{
    if (!m) {
        return;
    }
    char buf[WS_CTRL_MAX];
    if (cJSON_PrintPreallocated(m, buf, sizeof(buf), false)) {
        ws_client_send_json(buf);
    } else {
        ESP_LOGE(TAG, "message too large");
    }
    cJSON_Delete(m);
}

void protocol_send_hello(void)
{
    cJSON *m = msg_new("hello");
    if (!m) return;
    cJSON_AddNumberToObject(m, "protocol", PROTOCOL_VERSION);
    cJSON_AddStringToObject(m, "device_id", storage_device_id());
    cJSON_AddStringToObject(m, "fw", esp_app_get_description()->version);
    cJSON_AddNumberToObject(m, "sample_rate", app_state_sample_rate());
    cJSON *audio = cJSON_AddObjectToObject(m, "audio");
    if (audio) {
        cJSON_AddStringToObject(audio, "format", "pcm_s16le");
        cJSON_AddNumberToObject(audio, "channels", 1);
        cJSON_AddNumberToObject(audio, "frame_ms", 20);
        const int rates[] = { 16000, 24000, 48000 };
        cJSON_AddItemToObject(audio, "rates", cJSON_CreateIntArray(rates, 3));
    }
    const char *caps[] = { "mic", "speaker", "button", "led", "mic_mute", "volume", "full_duplex" };
    cJSON_AddItemToObject(m, "caps", cJSON_CreateStringArray(caps, sizeof(caps) / sizeof(caps[0])));
    cJSON_AddBoolToObject(m, "muted", app_state_muted());
    cJSON_AddNumberToObject(m, "volume", audio_out_volume());
    cJSON_AddBoolToObject(m, "full_duplex", app_state_full_duplex());
    cJSON_AddStringToObject(m, "reset_reason", protocol_reset_reason());
    msg_send(m);
}

void protocol_send_button(const char *event, uint32_t duration_ms)
{
    cJSON *m = msg_new("button");
    if (!m) return;
    cJSON_AddStringToObject(m, "event", event);
    if (duration_ms) {
        cJSON_AddNumberToObject(m, "duration_ms", duration_ms);
    }
    msg_send(m);
}

void protocol_send_mic_mute(bool muted, const char *source)
{
    cJSON *m = msg_new("mic_mute");
    if (!m) return;
    cJSON_AddBoolToObject(m, "muted", muted);
    cJSON_AddStringToObject(m, "source", source);
    msg_send(m);
}

void protocol_send_playback_done(void)
{
    cJSON *m = msg_new("playback_done");
    if (!m) return;
    cJSON_AddNumberToObject(m, "underruns", audio_out_underruns());
    msg_send(m);
}

void protocol_send_ping(void)
{
    cJSON *m = msg_new("ping");
    if (!m) return;
    cJSON_AddNumberToObject(m, "id", ++s_ping_id);
    msg_send(m);
}

void protocol_send_error(const char *code, const char *message)
{
    cJSON *m = msg_new("error");
    if (!m) return;
    cJSON_AddStringToObject(m, "code", code);
    cJSON_AddStringToObject(m, "message", message);
    msg_send(m);
}

static void send_config_ack(void)
{
    cJSON *m = msg_new("config_ack");
    if (!m) return;
    cJSON_AddNumberToObject(m, "sample_rate", app_state_sample_rate());
    cJSON_AddNumberToObject(m, "jitter_ms", audio_out_jitter_ms());
    cJSON_AddBoolToObject(m, "full_duplex", app_state_full_duplex());
    cJSON_AddNumberToObject(m, "led_brightness", led_brightness());
    cJSON_AddNumberToObject(m, "mic_gain_shift", audio_in_gain_shift());
    msg_send(m);
}

static void apply_config(const cJSON *cfg)
{
    const cJSON *v;
    v = cJSON_GetObjectItemCaseSensitive(cfg, "sample_rate");
    if (cJSON_IsNumber(v)) {
        uint32_t rate = (uint32_t)v->valuedouble;
        if (!app_state_rate_supported(rate)) {
            protocol_send_error("unsupported_rate", "sample_rate must be 16000, 24000 or 48000");
        } else if (rate != app_state_sample_rate()) {
            // Anything buffered was for the old rate. The clear is recorded at
            // the writer position, so audio sent after this message survives.
            audio_out_clear();
            app_state_set_sample_rate(rate);
        }
    }
    v = cJSON_GetObjectItemCaseSensitive(cfg, "jitter_ms");
    if (cJSON_IsNumber(v)) audio_out_set_jitter_ms((uint32_t)v->valuedouble);
    v = cJSON_GetObjectItemCaseSensitive(cfg, "full_duplex");
    if (cJSON_IsBool(v)) app_state_set_full_duplex(cJSON_IsTrue(v));
    v = cJSON_GetObjectItemCaseSensitive(cfg, "led_brightness");
    if (cJSON_IsNumber(v) && v->valuedouble >= 0 && v->valuedouble <= 255) led_set_brightness((uint8_t)v->valuedouble);
    v = cJSON_GetObjectItemCaseSensitive(cfg, "mic_gain_shift");
    if (cJSON_IsNumber(v) && v->valuedouble >= 0 && v->valuedouble <= 8) audio_in_set_gain_shift((uint8_t)v->valuedouble);
    send_config_ack();
}

static void apply_volume(const cJSON *root)
{
    uint8_t level = audio_out_volume();
    bool muted = audio_out_speaker_muted();
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(root, "level");
    if (cJSON_IsNumber(v) && v->valuedouble >= 0 && v->valuedouble <= 100) level = (uint8_t)v->valuedouble;
    v = cJSON_GetObjectItemCaseSensitive(root, "muted");
    if (cJSON_IsBool(v)) muted = cJSON_IsTrue(v);
    audio_out_set_volume(level, muted);
}

void protocol_handle_text(const char *txt, size_t len)
{
    cJSON *root = cJSON_ParseWithLength(txt, len);
    const cJSON *type = root ? cJSON_GetObjectItemCaseSensitive(root, "type") : NULL;
    if (!cJSON_IsString(type)) {
        ESP_LOGW(TAG, "bad control message: %.*s", (int)(len > 120 ? 120 : len), txt);
        protocol_send_error("bad_message", "expected a JSON object with a string \"type\"");
        cJSON_Delete(root);
        return;
    }
    const char *t = type->valuestring;

    // Audio markers first: they are the latency-critical ones.
    if (strcmp(t, "audio_clear") == 0) {
        audio_out_clear();
    } else if (strcmp(t, "audio_start") == 0) {
        audio_out_start();
    } else if (strcmp(t, "audio_end") == 0) {
        audio_out_end();
    } else if (strcmp(t, "state") == 0) {
        const cJSON *s = cJSON_GetObjectItemCaseSensitive(root, "state");
        conv_state_t cs;
        if (cJSON_IsString(s) && app_state_conv_from_name(s->valuestring, &cs)) {
            ESP_LOGI(TAG, "state -> %s", s->valuestring);
            app_state_set_conv(cs);
            app_state_set_fault(false);
        } else {
            protocol_send_error("bad_state", "unknown state");
        }
    } else if (strcmp(t, "welcome") == 0) {
        const cJSON *cfg = cJSON_GetObjectItemCaseSensitive(root, "config");
        if (cJSON_IsObject(cfg)) {
            apply_config(cfg);
        }
        app_state_set_fault(false);
        app_state_set_link(LINK_READY);
        ws_client_mark_ready();
        ESP_LOGI(TAG, "gateway ready");
    } else if (strcmp(t, "config") == 0) {
        apply_config(root);
    } else if (strcmp(t, "volume") == 0) {
        apply_volume(root);
    } else if (strcmp(t, "ping") == 0) {
        cJSON *m = msg_new("pong");
        const cJSON *id = cJSON_GetObjectItemCaseSensitive(root, "id");
        if (m && cJSON_IsNumber(id)) cJSON_AddNumberToObject(m, "id", id->valuedouble);
        msg_send(m);
    } else if (strcmp(t, "pong") == 0) {
        // Any received frame refreshes the liveness timer in ws_client.
    } else if (strcmp(t, "error") == 0) {
        const cJSON *c = cJSON_GetObjectItemCaseSensitive(root, "code");
        const cJSON *msg = cJSON_GetObjectItemCaseSensitive(root, "message");
        ESP_LOGE(TAG, "gateway error %s: %s", cJSON_IsString(c) ? c->valuestring : "?",
                 cJSON_IsString(msg) ? msg->valuestring : "");
        app_state_set_fault(true);
    } else {
        ESP_LOGW(TAG, "unknown message type \"%s\"", t);
    }
    cJSON_Delete(root);
}
