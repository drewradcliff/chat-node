// Every GPIO used by chat-node lives here; no other file names a pin number.
// Module: ESP32-S3-WROOM-1-N16R8. Pin map is final as of the routed PCB.
//
// Reserved, never use:
//   GPIO0      BOOT strapping button (chip's internal pull-up only, no external
//              resistor); firmware leaves it alone
//   GPIO19/20  native USB D-/D+: the only console and programming port
//   GPIO35-37  octal PSRAM
// UART0 (GPIO43/44) is not brought out on this board.
// Spare, unconnected: GPIO8, GPIO9, GPIO10, GPIO12, GPIO17, GPIO18.
#pragma once

#include "driver/gpio.h"
#include "driver/i2s_types.h"

// Microphone: TDK ICS-43434, I2S0 RX only, LR tied to GND -> data in LEFT slot.
#define MIC_I2S_PORT        I2S_NUM_0
#define PIN_MIC_SCK         GPIO_NUM_11
#define PIN_MIC_WS          GPIO_NUM_13
#define PIN_MIC_SD          GPIO_NUM_14

// Amplifier: MAX98357A, I2S1 TX only, no MCLK.
#define AMP_I2S_PORT        I2S_NUM_1
#define PIN_AMP_DIN         GPIO_NUM_5
#define PIN_AMP_BCLK        GPIO_NUM_6
#define PIN_AMP_LRCLK       GPIO_NUM_7
// High = amp on (left channel). Low/Hi-Z = shutdown (100k pull-down inside the
// amp keeps it off through boot).
#define PIN_AMP_SD_MODE     GPIO_NUM_4

// Main button: key switch to GND, active low, internal pull-up. RTC-capable.
#define PIN_BUTTON          GPIO_NUM_15

// Status LED: SK6812MINI-E through a non-inverting 74AHCT1G125 buffer.
#define PIN_LED_DATA        GPIO_NUM_16
