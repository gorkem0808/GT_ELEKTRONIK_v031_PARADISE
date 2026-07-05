cmake_minimum_required(VERSION 3.13)

if(NOT DEFINED PICO_SDK_PATH)
  if(DEFINED ENV{PICO_SDK_PATH})
    set(PICO_SDK_PATH $ENV{PICO_SDK_PATH})
  else()
    message(FATAL_ERROR "PICO_SDK_PATH is not set")
  endif()
endif()
include(${PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(gt_elektronik_v030_paradise_full_system C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(player1_mouse firmware/mouse/mouse_main.c firmware/mouse/mouse_usb_descriptors.c)
target_include_directories(player1_mouse PRIVATE firmware/mouse)
target_compile_definitions(player1_mouse PRIVATE PLAYER_ID=1 PIN_ENABLE=19 PIN_CAL=18)
target_link_libraries(player1_mouse PRIVATE pico_stdlib hardware_adc hardware_flash hardware_sync tinyusb_device tinyusb_board)
pico_add_extra_outputs(player1_mouse)

add_executable(player2_mouse firmware/mouse/mouse_main.c firmware/mouse/mouse_usb_descriptors.c)
target_include_directories(player2_mouse PRIVATE firmware/mouse)
target_compile_definitions(player2_mouse PRIVATE PLAYER_ID=2 PIN_ENABLE=19 PIN_CAL=18)
target_link_libraries(player2_mouse PRIVATE pico_stdlib hardware_adc hardware_flash hardware_sync tinyusb_device tinyusb_board)
pico_add_extra_outputs(player2_mouse)

add_executable(controller firmware/controller/keyboard_main.c firmware/controller/keyboard_usb_descriptors.c)
target_include_directories(controller PRIVATE firmware/controller)
target_link_libraries(controller PRIVATE pico_stdlib tinyusb_device tinyusb_board)
pico_add_extra_outputs(controller)
