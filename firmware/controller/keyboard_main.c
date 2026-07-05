#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>
#include "pico/stdlib.h"
#include "bsp/board.h"
#include "tusb.h"

#define LED_PIN 25
#define RELAY_ACTIVE_HIGH 1

#define P1_RELAY_PIN 26
#define P2_RELAY_PIN 27
#define P1_RELAY_TRIGGER_GP 6
#define P2_RELAY_TRIGGER_GP 7

static const uint8_t key_pins[]  = {0,1,2,3,4,5,6,7,8,9};
static const uint8_t key_codes[] = {0x27,0x1e,0x1f,0x20,0x21,0x22,0x23,0x24,0x25,0x26};
#define NKEYS (sizeof(key_pins)/sizeof(key_pins[0]))

static char cmd_buf[160];
static int cmd_len = 0;
static uint32_t manual_p1_until = 0;
static uint32_t manual_p2_until = 0;
static int manual_p1_on = 0;
static int manual_p2_on = 0;

static void cdc_printf(const char *fmt, ...) {
  if (!tud_cdc_connected()) return;
  char buf[240];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(buf, sizeof(buf), fmt, ap);
  va_end(ap);
  tud_cdc_write_str(buf);
  tud_cdc_write_flush();
}

static int pressed(uint pin) {
  return gpio_get(pin) == 0;
}

static void relay_set(uint pin, int on) {
  gpio_put(pin, RELAY_ACTIVE_HIGH ? on : !on);
}

static void send_cfg(void) {
  cdc_printf("CFG,KEYBOARD,CONTROLLER,MAP,GP0=0,GP1=1,GP2=2,GP3=3,GP4=4,GP5=5,GP6=6,GP7=7,GP8=8,GP9=9,P1RELAY,%d,P2RELAY,%d,P1TRIG,%d,P2TRIG,%d,COIN,GP8,START,GP9\r\n",
    P1_RELAY_PIN, P2_RELAY_PIN, P1_RELAY_TRIGGER_GP, P2_RELAY_TRIGGER_GP);
}

static void handle_cmd(char *s) {
  if (strncmp(s, "HELLO", 5) == 0) {
    cdc_printf("HELLO,KEYBOARD,CONTROLLER,GT_V030\r\n");
  } else if (strncmp(s, "GET", 3) == 0) {
    send_cfg();
  } else if (strncmp(s, "RELAY,", 6) == 0) {
    int pl,on;
    if (sscanf(s+6, "%d,%d", &pl, &on) == 2) {
      uint32_t until = board_millis() + 5000;
      if (pl == 1) { manual_p1_on = on ? 1 : 0; manual_p1_until = on ? until : 0; relay_set(P1_RELAY_PIN, manual_p1_on); }
      if (pl == 2) { manual_p2_on = on ? 1 : 0; manual_p2_until = on ? until : 0; relay_set(P2_RELAY_PIN, manual_p2_on); }
      cdc_printf("OK,RELAY,%d,%d\r\n", pl, on ? 1 : 0);
    }
  } else if (strncmp(s, "FACTORY", 7) == 0) {
    cdc_printf("OK,FACTORY,NOFLASH,FIXED_MAP\r\n");
  } else if (strncmp(s, "SAVE", 4) == 0) {
    cdc_printf("OK,SAVE,NOFLASH,FIXED_MAP\r\n");
  }
}

static void cdc_task(void) {
  while (tud_cdc_available()) {
    char c = (char)tud_cdc_read_char();
    if (c == '\r') continue;
    if (c == '\n') {
      cmd_buf[cmd_len] = 0;
      if (cmd_len > 0) handle_cmd(cmd_buf);
      cmd_len = 0;
    } else if (cmd_len < (int)sizeof(cmd_buf)-1) {
      cmd_buf[cmd_len++] = c;
    }
  }
}

int main(void) {
  board_init();
  tusb_init();

  gpio_init(LED_PIN);
  gpio_set_dir(LED_PIN, GPIO_OUT);

  for(unsigned i=0; i<NKEYS; i++) {
    gpio_init(key_pins[i]);
    gpio_set_dir(key_pins[i], GPIO_IN);
    gpio_pull_up(key_pins[i]);
  }

  gpio_init(P1_RELAY_PIN);
  gpio_set_dir(P1_RELAY_PIN, GPIO_OUT);
  relay_set(P1_RELAY_PIN, 0);

  gpio_init(P2_RELAY_PIN);
  gpio_set_dir(P2_RELAY_PIN, GPIO_OUT);
  relay_set(P2_RELAY_PIN, 0);

  uint32_t last_key = 0, last_status = 0, last_led = 0;
  int led_state = 0;

  while(1) {
    tud_task();
    cdc_task();

    uint32_t now = board_millis();

    int p1_relay_on = pressed(P1_RELAY_TRIGGER_GP);
    int p2_relay_on = pressed(P2_RELAY_TRIGGER_GP);

    if (manual_p1_until && now < manual_p1_until) p1_relay_on = manual_p1_on;
    else manual_p1_until = 0;

    if (manual_p2_until && now < manual_p2_until) p2_relay_on = manual_p2_on;
    else manual_p2_until = 0;

    relay_set(P1_RELAY_PIN, p1_relay_on);
    relay_set(P2_RELAY_PIN, p2_relay_on);

    if(tud_hid_ready() && now - last_key >= 8) {
      uint8_t keycode[6] = {0};
      int k = 0;
      for(unsigned i=0; i<NKEYS && k<6; i++) {
        if(pressed(key_pins[i])) keycode[k++] = key_codes[i];
      }
      tud_hid_keyboard_report(1, 0, keycode);
      last_key = now;
    }

    if(now - last_status >= 100) {
      cdc_printf("STATUS,KEYBOARD,CONTROLLER,BTN");
      for(unsigned i=0;i<NKEYS;i++) cdc_printf(",%u,%d", key_pins[i], pressed(key_pins[i]));
      cdc_printf(",P1RELAY,%d,P2RELAY,%d\r\n", p1_relay_on, p2_relay_on);
      last_status = now;
    }

    if(now - last_led > 700) {
      led_state = !led_state;
      gpio_put(LED_PIN, led_state);
      last_led = now;
    }

    sleep_ms(1);
  }
}
