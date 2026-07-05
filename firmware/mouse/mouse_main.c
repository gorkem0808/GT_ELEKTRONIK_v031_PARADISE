#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>
#include "pico/stdlib.h"
#include "hardware/adc.h"
#include "hardware/flash.h"
#include "hardware/sync.h"
#include "bsp/board.h"
#include "tusb.h"

#ifndef PLAYER_ID
#define PLAYER_ID 1
#endif
#ifndef PIN_ENABLE
#define PIN_ENABLE 19
#endif
#ifndef PIN_CAL
#define PIN_CAL 18
#endif

#define ADC_X_PIN 26
#define ADC_Y_PIN 27
#define LED_PIN 25

#define GTM_MAGIC 0x47544D60u
#define GTM_VERSION 30u
#define FLASH_TARGET_OFFSET (PICO_FLASH_SIZE_BYTES - FLASH_SECTOR_SIZE)

typedef struct {
  uint32_t magic;
  uint32_t version;
  int32_t cal_min_x;
  int32_t cal_max_x;
  int32_t cal_min_y;
  int32_t cal_max_y;
  int32_t filter_shift;
  int32_t invert_x;
  int32_t invert_y;
  uint32_t crc;
} mouse_cfg_t;

static int cal_min_x = 120;
static int cal_max_x = 3970;
static int cal_min_y = 120;
static int cal_max_y = 3970;
static int filter_shift = 2;
static int invert_x = 0;
static int invert_y = 0;
static int fx = 0;
static int fy = 0;
static char cmd_buf[160];
static int cmd_len = 0;

static void cdc_printf(const char *fmt, ...) {
  if (!tud_cdc_connected()) return;
  char buf[220];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(buf, sizeof(buf), fmt, ap);
  va_end(ap);
  tud_cdc_write_str(buf);
  tud_cdc_write_flush();
}

static uint32_t cfg_crc(const mouse_cfg_t *c) {
  const uint32_t *p = (const uint32_t*)c;
  uint32_t x = 0xA5A55A5Au;
  for (unsigned i=0; i<(sizeof(mouse_cfg_t)/4)-1; i++) {
    x ^= p[i] + 0x9E3779B9u + (x<<6) + (x>>2);
  }
  return x;
}

static void defaults(void) {
  cal_min_x = 120; cal_max_x = 3970;
  cal_min_y = 120; cal_max_y = 3970;
  filter_shift = 2;
  invert_x = 0;
  invert_y = 0;
}

static void load_cfg(void) {
  const mouse_cfg_t *c = (const mouse_cfg_t *)(XIP_BASE + FLASH_TARGET_OFFSET);
  if (c->magic == GTM_MAGIC && c->version == GTM_VERSION && c->crc == cfg_crc(c)) {
    cal_min_x = c->cal_min_x;
    cal_max_x = c->cal_max_x;
    cal_min_y = c->cal_min_y;
    cal_max_y = c->cal_max_y;
    filter_shift = c->filter_shift;
    invert_x = c->invert_x ? 1 : 0;
    invert_y = c->invert_y ? 1 : 0;
    if (filter_shift < 0) filter_shift = 0;
    if (filter_shift > 8) filter_shift = 8;
    if (cal_max_x <= cal_min_x + 30) { cal_min_x = 120; cal_max_x = 3970; }
    if (cal_max_y <= cal_min_y + 30) { cal_min_y = 120; cal_max_y = 3970; }
  }
}

static void save_cfg(void) {
  mouse_cfg_t c;
  memset(&c, 0xff, sizeof(c));
  c.magic = GTM_MAGIC;
  c.version = GTM_VERSION;
  c.cal_min_x = cal_min_x;
  c.cal_max_x = cal_max_x;
  c.cal_min_y = cal_min_y;
  c.cal_max_y = cal_max_y;
  c.filter_shift = filter_shift;
  c.invert_x = invert_x;
  c.invert_y = invert_y;
  c.crc = cfg_crc(&c);

  static uint8_t sector[FLASH_SECTOR_SIZE];
  memset(sector, 0xff, sizeof(sector));
  memcpy(sector, &c, sizeof(c));

  uint32_t ints = save_and_disable_interrupts();
  flash_range_erase(FLASH_TARGET_OFFSET, FLASH_SECTOR_SIZE);
  flash_range_program(FLASH_TARGET_OFFSET, sector, FLASH_SECTOR_SIZE);
  restore_interrupts(ints);
}

static uint16_t map_hid(int v, int mn, int mx, int inv) {
  if (mx <= mn) mx = mn + 1;
  if (v < mn) v = mn;
  if (v > mx) v = mx;
  int64_t out = ((int64_t)(v - mn) * 32767) / (mx - mn);
  if (inv) out = 32767 - out;
  if (out < 0) out = 0;
  if (out > 32767) out = 32767;
  return (uint16_t)out;
}

static int pressed(uint pin) {
  return gpio_get(pin) == 0;
}

static void blink(int count, int ms) {
  for (int i=0; i<count; i++) {
    gpio_put(LED_PIN, 1); sleep_ms(ms);
    gpio_put(LED_PIN, 0); sleep_ms(ms);
  }
}

static void send_cfg(void) {
  cdc_printf("CFG,MOUSE,P%d,CAL,%d,%d,%d,%d,FILTER,%d,INVERT,%d,%d,SAVE,FLASH\r\n",
    PLAYER_ID, cal_min_x, cal_max_x, cal_min_y, cal_max_y, filter_shift, invert_x, invert_y);
}

static void handle_cmd(char *s) {
  if (strncmp(s, "HELLO", 5) == 0) {
    cdc_printf("HELLO,MOUSE,P%d,GT_V030\r\n", PLAYER_ID);
  } else if (strncmp(s, "GET", 3) == 0) {
    send_cfg();
  } else if (strncmp(s, "CAL,", 4) == 0) {
    int a,b,c,d;
    if (sscanf(s+4, "%d,%d,%d,%d", &a,&b,&c,&d) == 4) {
      if (b > a + 30 && d > c + 30) {
        cal_min_x = a; cal_max_x = b; cal_min_y = c; cal_max_y = d;
        cdc_printf("OK,CAL,%d,%d,%d,%d\r\n", cal_min_x, cal_max_x, cal_min_y, cal_max_y);
      } else {
        cdc_printf("ERR,CAL,RANGE\r\n");
      }
    }
  } else if (strncmp(s, "FILTER,", 7) == 0) {
    int v = atoi(s+7);
    if (v < 0) v = 0;
    if (v > 8) v = 8;
    filter_shift = v;
    cdc_printf("OK,FILTER,%d\r\n", filter_shift);
  } else if (strncmp(s, "INVERT,", 7) == 0) {
    int ix,iy;
    if (sscanf(s+7, "%d,%d", &ix,&iy) == 2) {
      invert_x = ix ? 1 : 0;
      invert_y = iy ? 1 : 0;
      cdc_printf("OK,INVERT,%d,%d\r\n", invert_x, invert_y);
    }
  } else if (strncmp(s, "SAVE", 4) == 0) {
    save_cfg();
    cdc_printf("OK,SAVE,FLASH\r\n");
    blink(5, 55);
  } else if (strncmp(s, "FACTORY", 7) == 0) {
    defaults();
    save_cfg();
    cdc_printf("OK,FACTORY,FLASH\r\n");
    blink(10, 55);
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

  adc_init();
  adc_gpio_init(ADC_X_PIN);
  adc_gpio_init(ADC_Y_PIN);

  gpio_init(LED_PIN);
  gpio_set_dir(LED_PIN, GPIO_OUT);

  gpio_init(PIN_ENABLE);
  gpio_set_dir(PIN_ENABLE, GPIO_IN);
  gpio_pull_up(PIN_ENABLE);

  gpio_init(PIN_CAL);
  gpio_set_dir(PIN_CAL, GPIO_IN);
  gpio_pull_up(PIN_CAL);

  if (pressed(PIN_CAL)) {
    defaults();
    save_cfg();
    blink(12, 60);
  } else {
    load_cfg();
  }

  tusb_init();
  blink(PLAYER_ID, 120);

  uint32_t last_hid = 0, last_status = 0, last_led = 0;
  int led_state = 0;

  int cal_mode = 0, cal_step = 0, wait_release_after_enter = 0;
  int sx[4] = {0,0,0,0}, sy[4] = {0,0,0,0};
  uint32_t down_start = 0;
  int was_down = 0;

  while (1) {
    tud_task();
    cdc_task();

    adc_select_input(0);
    int rawx = adc_read();
    adc_select_input(1);
    int rawy = adc_read();

    if (fx == 0 && fy == 0) { fx = rawx; fy = rawy; }
    if (filter_shift > 0) {
      fx += (rawx - fx) >> filter_shift;
      fy += (rawy - fy) >> filter_shift;
    } else {
      fx = rawx; fy = rawy;
    }

    uint16_t hidx = map_hid(fx, cal_min_x, cal_max_x, invert_x);
    uint16_t hidy = map_hid(fy, cal_min_y, cal_max_y, invert_y);
    uint32_t now = board_millis();
    int dip_active = pressed(PIN_ENABLE);

    int cal_down = pressed(PIN_CAL);
    if (cal_down && !was_down) down_start = now;

    if (cal_down && !cal_mode && (now - down_start > 3000)) {
      cal_mode = 1;
      cal_step = 0;
      wait_release_after_enter = 1;
      blink(6, 70);
    }

    if (!cal_down && was_down) {
      uint32_t held = now - down_start;
      if (cal_mode && wait_release_after_enter) {
        wait_release_after_enter = 0;
      } else if (cal_mode && held > 25 && held < 2500) {
        if (cal_step < 4) {
          sx[cal_step] = rawx; sy[cal_step] = rawy; cal_step++;
          blink(cal_step, 90);
        }
        if (cal_step >= 4) {
          int minx=sx[0], maxx=sx[0], miny=sy[0], maxy=sy[0];
          for (int i=1;i<4;i++) {
            if (sx[i] < minx) minx=sx[i];
            if (sx[i] > maxx) maxx=sx[i];
            if (sy[i] < miny) miny=sy[i];
            if (sy[i] > maxy) maxy=sy[i];
          }
          if (maxx > minx + 40 && maxy > miny + 40) {
            int margin_x = (maxx - minx) / 35;
            int margin_y = (maxy - miny) / 35;
            cal_min_x = minx + margin_x;
            cal_max_x = maxx - margin_x;
            cal_min_y = miny + margin_y;
            cal_max_y = maxy - margin_y;
            save_cfg();
            blink(10, 55);
          } else {
            blink(4, 300);
          }
          cal_mode = 0; cal_step = 0; wait_release_after_enter = 0;
        }
      }
    }
    was_down = cal_down;

    if (cal_mode) {
      if (now - last_led > 130) { led_state = !led_state; gpio_put(LED_PIN, led_state); last_led = now; }
    } else if (dip_active) {
      if (now - last_led > 700) { led_state = !led_state; gpio_put(LED_PIN, led_state); last_led = now; }
    } else {
      gpio_put(LED_PIN, 0);
    }

    if (dip_active && tud_hid_ready() && now - last_hid >= 5) {
      uint8_t rpt[5];
      rpt[0] = 0;
      rpt[1] = hidx & 0xff; rpt[2] = hidx >> 8;
      rpt[3] = hidy & 0xff; rpt[4] = hidy >> 8;
      tud_hid_report(1, rpt, sizeof(rpt));
      last_hid = now;
    }

    if (now - last_status >= 100) {
      cdc_printf("STATUS,MOUSE,P%d,RAW,%d,%d,HID,%u,%u,ACTIVE,%d,FILTER,%d,INVERT,%d,%d,CAL,%d,%d,%d,%d\r\n",
        PLAYER_ID, rawx, rawy, hidx, hidy, dip_active, filter_shift, invert_x, invert_y,
        cal_min_x, cal_max_x, cal_min_y, cal_max_y);
      last_status = now;
    }

    sleep_ms(1);
  }
}
