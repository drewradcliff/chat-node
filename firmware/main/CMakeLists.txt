# No REQUIRES list: the "main" component then sees every IDF component plus the
# managed components declared in idf_component.yml (esp_websocket_client, led_strip).
idf_component_register(
    SRCS
        "main.c"
        "app_state.c"
        "audio_in.c"
        "audio_out.c"
        "net.c"
        "ws_client.c"
        "protocol.c"
        "button.c"
        "led.c"
        "storage.c"
        "console_cmds.c"
    INCLUDE_DIRS ".")
