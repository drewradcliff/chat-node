#pragma once

#include "esp_err.h"

// Starts the esp_console REPL on the USB-Serial-JTAG port.
esp_err_t console_start(void);
