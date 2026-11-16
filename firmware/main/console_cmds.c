#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_console.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_app_desc.h"
#include "app.h"
#include "app_state.h"
#include "audio_common.h"
#include "audio_in.h"
#include "audio_out.h"
#include "net.h"
#include "protocol.h"
#include "storage.h"
#include "ws_client.h"
#include "console_cmds.h"

static const char *TAG = "console";

static bool parse_on_off(const char *s, bool *out)
{
    if (strcmp(s, "on") == 0 || strcmp(s, "1") == 0) { *out = true; return true; }
    if (strcmp(s, "off") == 0 || strcmp(s, "0") == 0) { *out = false; return true; }
    return false;
}

static bool token_ok(const char *t)
{
    if (!*t) return false;
    for (; *t; t++) {
        if (!isgraph((unsigned char)*t)) return false;   // no spaces, CR or LF (header injection)
    }
    return true;
}

// ---- provisioning ----------------------------------------------------------

static int cmd_wifi(int argc, char **argv)
{
    if (argc == 4 && strcmp(argv[1], "set") == 0) {
        esp_err_t err = storage_set_wifi(argv[2], argv[3]);
        if (err != ESP_OK) {
            printf("error: %s (SSID 1-32 chars, password up to 64)\n", esp_err_to_name(err));
            return 1;
        }
        printf("Wi-Fi credentials saved; connecting.\n");
        net_wifi_start();
        return 0;
    }
    if (argc == 3 && strcmp(argv[1], "set") == 0) {
        printf("for an open network use: wifi set \"%s\" \"\"\n", argv[2]);
        return 1;
    }
    printf("usage: wifi set <ssid> <password>   (quote values with spaces)\n");
    return 1;
}

static int read_pem_from_console(void)
{
    const size_t cap = STORAGE_CERT_MAX;
    char *pem = calloc(1, cap);
    char line[160];
    size_t len = 0;
    bool seen_begin = false;
    if (!pem) {
        printf("out of memory\n");
        return 1;
    }
    printf("Paste the PEM certificate (gateway cert or its CA), then an empty line:\n");
    while (fgets(line, sizeof(line), stdin)) {
        size_t l = strcspn(line, "\r\n");
        line[l] = '\0';
        if (l == 0) {
            if (seen_begin) break;
            continue;
        }
        if (strstr(line, "-----BEGIN")) seen_begin = true;
        if (len + l + 2 >= cap) {
            printf("certificate too large (max %u bytes)\n", (unsigned)cap);
            free(pem);
            return 1;
        }
        memcpy(pem + len, line, l);
        len += l;
        pem[len++] = '\n';
    }
    pem[len] = '\0';
    if (!strstr(pem, "-----BEGIN CERTIFICATE-----") || !strstr(pem, "-----END CERTIFICATE-----")) {
        printf("that does not look like a PEM certificate; nothing saved\n");
        free(pem);
        return 1;
    }
    esp_err_t err = storage_set_cert(pem);
    free(pem);
    if (err != ESP_OK) {
        printf("save failed: %s\n", esp_err_to_name(err));
        return 1;
    }
    printf("certificate saved (%u bytes); reconnecting.\n", (unsigned)len);
    ws_client_reconfigure();
    return 0;
}

static int cmd_gateway(int argc, char **argv)
{
    if (argc == 4 && strcmp(argv[1], "set") == 0) {
        const char *url = argv[2], *token = argv[3];
        if (strncmp(url, "wss://", 6) != 0 && strncmp(url, "ws://", 5) != 0) {
            printf("URL must start with wss:// (or ws:// with `gateway insecure on`)\n");
            return 1;
        }
        if (!token_ok(token)) {
            printf("token must be printable with no spaces\n");
            return 1;
        }
        if (storage_set_gateway(url, token) != ESP_OK) {
            printf("save failed (URL < %d chars, token < %d chars)\n", STORAGE_URL_MAX, STORAGE_TOKEN_MAX);
            return 1;
        }
        printf("gateway saved; reconnecting.\n");
        if (strncmp(url, "ws://", 5) == 0) {
            printf("note: ws:// is refused unless `gateway insecure on` is set.\n");
        }
        ws_client_reconfigure();
        return 0;
    }
    if (argc >= 2 && strcmp(argv[1], "cert") == 0) {
        if (argc == 3 && strcmp(argv[2], "clear") == 0) {
            storage_set_cert(NULL);
            printf("certificate removed; reconnecting.\n");
            ws_client_reconfigure();
            return 0;
        }
        return read_pem_from_console();
    }
    bool on;
    if (argc == 3 && strcmp(argv[1], "insecure") == 0 && parse_on_off(argv[2], &on)) {
        storage_set_insecure(on);
        printf("ws:// is now %s.\n", on ? "ALLOWED (development only)" : "refused");
        ws_client_reconfigure();
        return 0;
    }
    printf("usage:\n  gateway set <wss://host:port/path> <token>\n  gateway cert        (paste PEM)\n"
           "  gateway cert clear\n  gateway insecure on|off\n");
    return 1;
}

static int cmd_status(int argc, char **argv)
{
    wifi_creds_t wifi;
    gateway_cfg_t gw;
    char ip[20];
    bool have_wifi = storage_get_wifi(&wifi);
    bool have_gw = storage_get_gateway(&gw);
    net_ip_str(ip, sizeof(ip));

    printf("firmware      %s\n", esp_app_get_description()->version);
    printf("device id     %s\n", storage_device_id());
    printf("uptime        %u s, last reset: %s\n", (unsigned)(esp_timer_get_time() / 1000000), protocol_reset_reason());
    printf("link          %s\n", app_state_link_name(app_state_link()));
    printf("conversation  %s%s\n", app_state_conv_name(app_state_conv()), app_state_fault() ? " (fault)" : "");
    printf("mic           %s, gain shift %u, dropped frames %u\n", app_state_muted() ? "MUTED" : "live",
           audio_in_gain_shift(), (unsigned)audio_in_dropped_frames());
    printf("speaker       volume %u%s, ceiling %d dBFS, amp %s\n", audio_out_volume(),
           audio_out_speaker_muted() ? " (muted by gateway)" : "", audio_out_ceiling_db(),
           audio_out_amp_on() ? "on" : "off");
    printf("playback      jitter %u ms, buffered %u ms, underruns %u, overflow %u B\n",
           (unsigned)audio_out_jitter_ms(), (unsigned)audio_out_buffered_ms(),
           (unsigned)audio_out_underruns(), (unsigned)audio_out_overflow_bytes());
    printf("audio         %u Hz, full duplex %s\n", (unsigned)app_state_sample_rate(),
           app_state_full_duplex() ? "on" : "off");
    printf("wifi          %s, ip %s, rssi %d\n", have_wifi ? wifi.ssid : "(not set)", ip, net_wifi_rssi());
    printf("gateway       %s, token %s, cert %s, ws:// %s, socket %s\n",
           have_gw ? gw.url : "(not set)", have_gw && gw.token[0] ? "set" : "not set",
           storage_has_cert() ? "pinned" : "none", have_gw && gw.allow_insecure ? "allowed" : "refused",
           ws_client_connected() ? "open" : "closed");
    printf("heap          internal %u B free, psram %u B free\n",
           (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
           (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    return 0;
}

static int cmd_factory_reset(int argc, char **argv)
{
    if (argc != 2 || strcmp(argv[1], "yes") != 0) {
        printf("erases Wi-Fi, gateway, token, certificate and settings. Run `factory-reset yes`.\n");
        return 1;
    }
    app_factory_reset();
    return 0;
}

static int cmd_volume(int argc, char **argv)
{
    if (argc == 2) {
        int v = atoi(argv[1]);
        if (v < 0 || v > 100) {
            printf("volume is 0-100\n");
            return 1;
        }
        audio_out_set_volume((uint8_t)v, audio_out_speaker_muted());
        storage_set_volume((uint8_t)v);
    }
    printf("volume %u\n", audio_out_volume());
    return 0;
}

static int cmd_mute(int argc, char **argv)
{
    bool on;
    if (argc == 2 && parse_on_off(argv[1], &on)) {
        app_set_mic_muted(on, "console");
    }
    printf("mic %s\n", app_state_muted() ? "MUTED" : "live");
    return 0;
}

static int cmd_duplex(int argc, char **argv)
{
    bool on;
    if (argc == 2 && parse_on_off(argv[1], &on)) {
        app_state_set_full_duplex(on);
    }
    printf("full duplex %s (not persisted)\n", app_state_full_duplex() ? "on" : "off");
    return 0;
}

static int cmd_reboot(int argc, char **argv)
{
    printf("rebooting\n");
    fflush(stdout);
    vTaskDelay(pdMS_TO_TICKS(100));
    esp_restart();
    return 0;
}

// ---- bring-up tests (local only, no network) -------------------------------

static int cmd_tone(int argc, char **argv)
{
    if (argc != 3) {
        printf("usage: tone <hz> <ms>\n");
        return 1;
    }
    int hz = atoi(argv[1]), ms = atoi(argv[2]);
    const uint32_t rate = app_state_sample_rate();
    if (hz < 20 || hz > (int)rate / 2 || ms < 10 || ms > 10000) {
        printf("hz 20..%u, ms 10..10000\n", (unsigned)(rate / 2));
        return 1;
    }
    static int16_t buf[AUDIO_MAX_FRAME_SAMPLES];
    const uint32_t fs = audio_frame_samples(rate);
    const uint32_t total = rate * (uint32_t)ms / 1000u;
    const uint32_t ramp = rate / 200u;   // 5 ms in/out
    const float step = 2.0f * (float)M_PI * (float)hz / (float)rate;
    float phase = 0;
    audio_out_start();
    for (uint32_t pos = 0; pos < total; pos += fs) {
        uint32_t n = (total - pos) < fs ? (total - pos) : fs;
        for (uint32_t i = 0; i < n; i++) {
            uint32_t k = pos + i;
            float env = 1.0f;
            if (k < ramp) env = (float)k / (float)ramp;
            else if (total - k < ramp) env = (float)(total - k) / (float)ramp;
            buf[i] = (int16_t)(16384.0f * env * sinf(phase));   // -6 dBFS before volume
            phase += step;
            if (phase > 2.0f * (float)M_PI) phase -= 2.0f * (float)M_PI;
        }
        audio_out_write(buf, n * sizeof(int16_t), portMAX_DELAY);
    }
    audio_out_end();
    printf("tone %d Hz for %d ms at volume %u\n", hz, ms, audio_out_volume());
    return 0;
}

static int cmd_miclevel(int argc, char **argv)
{
    int secs = argc == 2 ? atoi(argv[1]) : 5;
    if (secs < 1 || secs > 60) secs = 5;
    printf("mic level for %d s (%s; local only)\n", secs, app_state_muted() ? "muted for the network" : "live");
    for (int i = 0; i < secs * 10; i++) {
        uint32_t rms, peak;
        audio_in_level(&rms, &peak);
        float rms_db = rms ? 20.0f * log10f((float)rms / 32768.0f) : -96.0f;
        float peak_db = peak ? 20.0f * log10f((float)peak / 32768.0f) : -96.0f;
        int bars = (int)((rms_db + 80.0f) / 2.0f);
        if (bars < 0) bars = 0;
        if (bars > 40) bars = 40;
        printf("rms %6.1f dBFS  peak %6.1f dBFS  |%.*s%*s|\n", (double)rms_db, (double)peak_db,
               bars, "########################################", 40 - bars, "");
        vTaskDelay(pdMS_TO_TICKS(100));
    }
    return 0;
}

static int cmd_loopback(int argc, char **argv)
{
    int secs = argc == 2 ? atoi(argv[1]) : 0;
    if (secs < 1 || secs > 10) {
        printf("usage: loopback <seconds 1-10>\n");
        return 1;
    }
    const uint32_t rate = app_state_sample_rate();
    const size_t samples = (size_t)rate * (size_t)secs;
    int16_t *buf = heap_caps_malloc(samples * sizeof(int16_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!buf) {
        printf("out of memory\n");
        return 1;
    }
    printf("recording %d s... speak now\n", secs);
    if (!audio_in_capture(buf, samples, pdMS_TO_TICKS(secs * 1000 + 2000))) {
        printf("capture failed\n");
        free(buf);
        return 1;
    }
    printf("playing back\n");
    audio_out_start();
    audio_out_write(buf, samples * sizeof(int16_t), portMAX_DELAY);
    audio_out_end();
    free(buf);      // the ring buffer holds its own copy
    vTaskDelay(pdMS_TO_TICKS(secs * 1000 + 200));
    printf("done\n");
    return 0;
}

// ----------------------------------------------------------------------------

static void reg(const char *cmd, const char *help, const char *hint, esp_console_cmd_func_t fn)
{
    const esp_console_cmd_t c = { .command = cmd, .help = help, .hint = hint, .func = fn };
    ESP_ERROR_CHECK(esp_console_cmd_register(&c));
}

esp_err_t console_start(void)
{
    esp_console_repl_t *repl = NULL;
    esp_console_repl_config_t repl_cfg = ESP_CONSOLE_REPL_CONFIG_DEFAULT();
    repl_cfg.prompt = "chat-node>";
    repl_cfg.max_cmdline_length = 1024;
    repl_cfg.task_stack_size = 8192;
    esp_console_dev_usb_serial_jtag_config_t hw_cfg = ESP_CONSOLE_DEV_USB_SERIAL_JTAG_CONFIG_DEFAULT();
    esp_err_t err = esp_console_new_repl_usb_serial_jtag(&hw_cfg, &repl_cfg, &repl);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "console init failed: %s", esp_err_to_name(err));
        return err;
    }

    reg("wifi", "Store Wi-Fi credentials and connect", "set <ssid> <password>", cmd_wifi);
    reg("gateway", "Gateway URL/token, pinned certificate, ws:// permission",
        "set <url> <token> | cert [clear] | insecure on|off", cmd_gateway);
    reg("status", "Show device, network and audio status", NULL, cmd_status);
    reg("factory-reset", "Erase stored credentials and settings, reboot", "yes", cmd_factory_reset);
    reg("volume", "Show or set speaker volume (0-100, saved)", "[0-100]", cmd_volume);
    reg("mute", "Show or set local mic mute", "[on|off]", cmd_mute);
    reg("duplex", "Show or set full-duplex mic streaming (experimental)", "[on|off]", cmd_duplex);
    reg("reboot", "Restart the device", NULL, cmd_reboot);
    reg("tone", "Speaker test: play a sine tone", "<hz> <ms>", cmd_tone);
    reg("miclevel", "Print mic RMS/peak every 100 ms", "[seconds]", cmd_miclevel);
    reg("loopback", "Record, then play back locally (no network)", "<seconds>", cmd_loopback);

    return esp_console_start_repl(repl);
}
