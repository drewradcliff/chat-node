cmake_minimum_required(VERSION 3.16)

# Reported to the gateway in the hello message (esp_app_get_description()->version).
set(PROJECT_VER "0.1.0")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(chat-node)
