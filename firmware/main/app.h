// Device-level actions shared by the button handler and the console.
#pragma once

#include <stdbool.h>

// Mutes/unmutes the mic locally (immediate), persists it, tells the gateway.
void app_set_mic_muted(bool muted, const char *source);
// Erases stored credentials and settings, then reboots. Does not return.
void app_factory_reset(void);
