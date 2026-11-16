// The one WebSocket to the gateway. Owns two tasks:
//   ws_sup : connects, keeps alive, tears down and reconnects with backoff
//   ws_tx  : the only sender; drains the control queue and the mic buffer
// Received frames are handled in the esp_websocket_client task: binary goes
// straight to audio_out, text to protocol_handle_text().
#pragma once

#include <stdbool.h>
#include "esp_err.h"

#define WS_CTRL_MAX 384

esp_err_t ws_client_start(void);
// Gateway URL, token or certificate changed: drop the socket and reconnect now.
void ws_client_reconfigure(void);
// Queue a text message. Non-blocking; false if not connected or queue full.
bool ws_client_send_json(const char *json);
void ws_client_mark_ready(void);
bool ws_client_connected(void);
