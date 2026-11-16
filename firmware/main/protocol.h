// JSON control messages (see PROTOCOL.md). Outbound helpers build a message
// and hand it to ws_client_send_json(); they never block.
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define PROTOCOL_VERSION 1

// Called from the WebSocket task with one complete text frame.
void protocol_handle_text(const char *txt, size_t len);

void protocol_send_hello(void);
void protocol_send_button(const char *event, uint32_t duration_ms);
void protocol_send_mic_mute(bool muted, const char *source);
void protocol_send_playback_done(void);
void protocol_send_ping(void);
void protocol_send_error(const char *code, const char *message);

const char *protocol_reset_reason(void);
