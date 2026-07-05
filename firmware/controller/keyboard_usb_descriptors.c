#include <string.h>
#include "tusb.h"

#define USBD_VID 0xCafe
#define USBD_PID 0x6030
#define USBD_BCD 0x0300

enum { ITF_NUM_CDC=0, ITF_NUM_CDC_DATA, ITF_NUM_HID, ITF_NUM_TOTAL };
#define CONFIG_TOTAL_LEN (TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN + TUD_HID_DESC_LEN)

uint8_t const desc_hid_report[] = {
  TUD_HID_REPORT_DESC_KEYBOARD(HID_REPORT_ID(1))
};

uint8_t const * tud_hid_descriptor_report_cb(uint8_t instance) {
  (void) instance;
  return desc_hid_report;
}

uint8_t const desc_device[] = {
  18, TUSB_DESC_DEVICE, 0x00, 0x02,
  TUSB_CLASS_MISC, MISC_SUBCLASS_COMMON, MISC_PROTOCOL_IAD, 64,
  (uint8_t)USBD_VID, (uint8_t)(USBD_VID>>8),
  (uint8_t)USBD_PID, (uint8_t)(USBD_PID>>8),
  (uint8_t)USBD_BCD, (uint8_t)(USBD_BCD>>8),
  0x01, 0x02, 0x03, 0x01
};

uint8_t const * tud_descriptor_device_cb(void) {
  return desc_device;
}

uint8_t const desc_configuration[] = {
  TUD_CONFIG_DESCRIPTOR(1, ITF_NUM_TOTAL, 0, CONFIG_TOTAL_LEN, 0, 100),
  TUD_CDC_DESCRIPTOR(ITF_NUM_CDC, 4, 0x81, 8, 0x02, 0x82, 64),
  TUD_HID_DESCRIPTOR(ITF_NUM_HID, 5, HID_ITF_PROTOCOL_KEYBOARD, sizeof(desc_hid_report), 0x83, 16, 1)
};

uint8_t const * tud_descriptor_configuration_cb(uint8_t index) {
  (void) index;
  return desc_configuration;
}

char const *string_desc_arr[] = {
  (const char[]){0x09,0x04},
  "GT ELEKTRONIK",
  "GT PARADISE CONTROLLER KEYBOARD",
  "GT-PARADISE-CONTROLLER-v030",
  "GT CONFIG SERIAL",
  "GT KEYBOARD"
};

static uint16_t _desc_str[64];

uint16_t const* tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
  (void) langid;
  uint8_t chr_count;
  if(index == 0) {
    memcpy(&_desc_str[1], string_desc_arr[0], 2);
    chr_count = 1;
  } else {
    if(index >= sizeof(string_desc_arr)/sizeof(string_desc_arr[0])) return NULL;
    const char* str = string_desc_arr[index];
    chr_count = strlen(str);
    if(chr_count > 63) chr_count = 63;
    for(uint8_t i=0; i<chr_count; i++) _desc_str[1+i] = str[i];
  }
  _desc_str[0] = (TUSB_DESC_STRING << 8) | (2*chr_count + 2);
  return _desc_str;
}

uint16_t tud_hid_get_report_cb(uint8_t instance, uint8_t report_id, hid_report_type_t report_type,
                               uint8_t* buffer, uint16_t reqlen) {
  (void)instance; (void)report_id; (void)report_type; (void)buffer; (void)reqlen;
  return 0;
}

void tud_hid_set_report_cb(uint8_t instance, uint8_t report_id, hid_report_type_t report_type,
                           uint8_t const* buffer, uint16_t bufsize) {
  (void)instance; (void)report_id; (void)report_type; (void)buffer; (void)bufsize;
}
