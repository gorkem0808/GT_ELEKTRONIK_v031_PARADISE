# -*- coding: utf-8 -*-
import os
import time
import queue
import threading
import subprocess
import configparser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import serial
    import serial.tools.list_ports
except Exception:
    serial = None

APP_TITLE = "GT ELEKTRONIK v030 - Paradise Lost / TeknoParrot PC Kalibrasyon Test"
BAUD = 115200
CFG_FILE = "gt_v030_config.ini"

KEY_PINS = list(range(10))
CORNER_NAMES = ["SOL ÜST", "SAĞ ÜST", "SAĞ ALT", "SOL ALT"]

class Device:
    def __init__(self, port):
        self.port = port
        self.ser = None
        self.running = False
        self.q = queue.Queue()
        self.kind = "UNKNOWN"
        self.player = ""
        self.last_line = ""
        self.raw_x = None
        self.raw_y = None
        self.hid_x = None
        self.hid_y = None
        self.active = None
        self.filter_shift = None
        self.invert_x = 0
        self.invert_y = 0
        self.cal = None
        self.buttons = {}
        self.relay1 = 0
        self.relay2 = 0

    def open(self):
        self.ser = serial.Serial(self.port, BAUD, timeout=0.04, write_timeout=0.2)
        try:
            self.ser.dtr = True
            self.ser.rts = True
        except Exception:
            pass
        self.running = True
        threading.Thread(target=self.reader, daemon=True).start()
        self.write("HELLO?")
        self.write("GET")

    def close(self):
        self.running = False
        try:
            if self.ser:
                self.ser.close()
        except Exception:
            pass

    def write(self, cmd):
        try:
            if self.ser and self.ser.is_open:
                self.ser.write((cmd.strip() + "\n").encode("ascii", "ignore"))
        except Exception as e:
            self.q.put("ERR," + str(e))

    def reader(self):
        while self.running:
            try:
                b = self.ser.readline()
                if not b:
                    continue
                line = b.decode("utf-8", "ignore").strip()
                if line:
                    self.last_line = line
                    self.parse(line)
                    self.q.put(line)
            except Exception as e:
                self.q.put("ERR," + str(e))
                time.sleep(0.2)

    def parse(self, line):
        parts = [p.strip() for p in line.split(",")]
        u = line.upper()

        if "MOUSE,P1" in u:
            self.kind = "MOUSE"; self.player = "P1"
        elif "MOUSE,P2" in u:
            self.kind = "MOUSE"; self.player = "P2"
        elif "KEYBOARD" in u or "CONTROLLER" in u:
            self.kind = "KEYBOARD"; self.player = "CONTROLLER"

        if "RAW" in parts and "HID" in parts:
            try:
                ri = parts.index("RAW")
                hi = parts.index("HID")
                self.raw_x = int(parts[ri+1])
                self.raw_y = int(parts[ri+2])
                self.hid_x = int(parts[hi+1])
                self.hid_y = int(parts[hi+2])
            except Exception:
                pass

        if "ACTIVE" in parts:
            try:
                self.active = int(parts[parts.index("ACTIVE")+1])
            except Exception:
                pass

        if "FILTER" in parts:
            try:
                self.filter_shift = int(parts[parts.index("FILTER")+1])
            except Exception:
                pass

        if "INVERT" in parts:
            try:
                ii = parts.index("INVERT")
                self.invert_x = int(parts[ii+1])
                self.invert_y = int(parts[ii+2])
            except Exception:
                pass

        if "CAL" in parts:
            try:
                ci = parts.index("CAL")
                self.cal = (int(parts[ci+1]), int(parts[ci+2]), int(parts[ci+3]), int(parts[ci+4]))
            except Exception:
                pass

        if "BTN" in parts:
            try:
                bi = parts.index("BTN") + 1
                while bi + 1 < len(parts):
                    try:
                        pin = int(parts[bi])
                        val = int(parts[bi+1])
                        self.buttons[pin] = val
                        bi += 2
                    except Exception:
                        bi += 1
            except Exception:
                pass

        if "P1RELAY" in parts:
            try:
                self.relay1 = int(parts[parts.index("P1RELAY")+1])
            except Exception:
                pass

        if "P2RELAY" in parts:
            try:
                self.relay2 = int(parts[parts.index("P2RELAY")+1])
            except Exception:
                pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1320x820")
        self.minsize(1100, 700)

        self.devices = []
        self.by_role = {"P1": None, "P2": None, "CONTROLLER": None}

        self.status = tk.StringVar(value="Hazır. 3 Pico'yu takıp CİHAZLARI TARA bas.")
        self.p1_info = tk.StringVar(value="P1 bekleniyor")
        self.p2_info = tk.StringVar(value="P2 bekleniyor")
        self.controller_info = tk.StringVar(value="Controller bekleniyor")
        self.button_info = tk.StringVar(value="Tuş testi bekleniyor")
        self.relay_info = tk.StringVar(value="Röle testi bekleniyor")
        self.cal_status = tk.StringVar(value="Kalibrasyon bekleniyor")
        self.tp_path = tk.StringVar(value="")
        self.game_path = tk.StringVar(value="")

        self.cal_player = tk.StringVar(value="P1")
        self.cal_confirm_gp = tk.IntVar(value=6)
        self.cal_points = []
        self.cal_running = False
        self.cal_last_pressed = 0
        self.cal_margin_percent = tk.IntVar(value=3)
        self.filter_var = tk.IntVar(value=2)
        self.inv_x = tk.BooleanVar(value=False)
        self.inv_y = tk.BooleanVar(value=False)

        self.cfg = configparser.ConfigParser()
        self.load_cfg()
        self.build_ui()
        self.after(100, self.tick)

    def build_ui(self):
        header = tk.Frame(self, bg="#111827")
        header.pack(fill="x")
        tk.Label(header, text=APP_TITLE, bg="#111827", fg="#38bdf8", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Label(header, text="Oyun modu: Controller klavye + Player1/Player2 ayrı mouse. PC program sadece test/kalibrasyon/başlatma içindir.", bg="#111827", fg="white").pack(anchor="w", padx=12, pady=(0, 10))

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_status = ttk.Frame(nb, padding=8)
        self.tab_cal = ttk.Frame(nb, padding=8)
        self.tab_game = ttk.Frame(nb, padding=8)
        self.tab_help = ttk.Frame(nb, padding=8)

        nb.add(self.tab_status, text="Cihaz / Tuş / Röle Test")
        nb.add(self.tab_cal, text="PC Kalibrasyon")
        nb.add(self.tab_game, text="Paradise Lost / TeknoParrot")
        nb.add(self.tab_help, text="Bağlantı ve Sistem")

        self.build_status_tab()
        self.build_cal_tab()
        self.build_game_tab()
        self.build_help_tab()

        bottom = ttk.Frame(self, padding=(8, 0, 8, 8))
        bottom.pack(fill="x")
        ttk.Label(bottom, textvariable=self.status, font=("Segoe UI", 10, "bold"), foreground="#0f766e").pack(anchor="w")

    def build_status_tab(self):
        top = ttk.Frame(self.tab_status)
        top.pack(fill="x")
        ttk.Button(top, text="CİHAZLARI TARA / YENİLE", command=self.scan).pack(side="left", padx=4)
        ttk.Button(top, text="HELLO / GET TEKRAR GÖNDER", command=self.poll).pack(side="left", padx=4)
        ttk.Button(top, text="NOT DEFTERİ AÇ", command=self.open_notepad).pack(side="left", padx=4)
        ttk.Button(top, text="TÜM PORTLARI KAPAT", command=self.close_devices).pack(side="left", padx=4)

        self.tree = ttk.Treeview(self.tab_status, columns=("port","type","role","last"), show="headings", height=7)
        for c,w in [("port",90),("type",110),("role",130),("last",900)]:
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=w)
        self.tree.pack(fill="x", pady=8)

        live = ttk.LabelFrame(self.tab_status, text="Canlı Durum", padding=8)
        live.pack(fill="x", pady=6)
        ttk.Label(live, textvariable=self.p1_info, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=2)
        ttk.Label(live, textvariable=self.p2_info, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=2)
        ttk.Label(live, textvariable=self.controller_info, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=2)
        ttk.Label(live, textvariable=self.button_info, font=("Segoe UI", 10, "bold"), foreground="#1d4ed8").pack(anchor="w", pady=2)
        ttk.Label(live, textvariable=self.relay_info, font=("Segoe UI", 10, "bold"), foreground="#7c2d12").pack(anchor="w", pady=2)

        gpbox = ttk.LabelFrame(self.tab_status, text="Controller GP0-GP9 Canlı Tuş Lambaları", padding=8)
        gpbox.pack(fill="x", pady=6)
        self.gp_lamps = {}
        for i in range(10):
            f = tk.Frame(gpbox, bg="#e5e7eb", width=115, height=55, relief="ridge", bd=1)
            f.pack(side="left", padx=3, pady=3)
            f.pack_propagate(False)
            tk.Label(f, text=f"GP{i} -> {i}", bg="#e5e7eb", font=("Segoe UI", 10, "bold")).pack(expand=True)
            self.gp_lamps[i] = f

        relay = ttk.LabelFrame(self.tab_status, text="Röle Test", padding=8)
        relay.pack(fill="x", pady=6)
        ttk.Button(relay, text="P1 Röle ÇEK", command=lambda:self.send_relay(1,1)).pack(side="left", padx=4)
        ttk.Button(relay, text="P1 Röle BIRAK", command=lambda:self.send_relay(1,0)).pack(side="left", padx=4)
        ttk.Button(relay, text="P2 Röle ÇEK", command=lambda:self.send_relay(2,1)).pack(side="left", padx=4)
        ttk.Button(relay, text="P2 Röle BIRAK", command=lambda:self.send_relay(2,0)).pack(side="left", padx=4)

        logbox = ttk.LabelFrame(self.tab_status, text="Ham Log", padding=6)
        logbox.pack(fill="both", expand=True, pady=6)
        self.log = tk.Text(logbox, height=12, wrap="word", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True)

    def build_cal_tab(self):
        row = ttk.Frame(self.tab_cal)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Kalibrasyon yapılacak oyuncu:").pack(side="left")
        ttk.Combobox(row, textvariable=self.cal_player, values=["P1","P2"], width=8, state="readonly").pack(side="left", padx=6)
        ttk.Label(row, text="Fiziksel onay GP:").pack(side="left", padx=(16, 0))
        ttk.Combobox(row, textvariable=self.cal_confirm_gp, values=list(range(10)), width=8, state="readonly").pack(side="left", padx=6)
        ttk.Label(row, text="Kenar payı %:").pack(side="left", padx=(16,0))
        ttk.Spinbox(row, from_=0, to=10, textvariable=self.cal_margin_percent, width=5).pack(side="left", padx=4)

        row2 = ttk.Frame(self.tab_cal)
        row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="Filtre:").pack(side="left")
        ttk.Spinbox(row2, from_=0, to=8, textvariable=self.filter_var, width=5).pack(side="left", padx=4)
        ttk.Checkbutton(row2, text="X ters çevir", variable=self.inv_x).pack(side="left", padx=10)
        ttk.Checkbutton(row2, text="Y ters çevir", variable=self.inv_y).pack(side="left", padx=10)
        ttk.Button(row2, text="FİLTRE / TERS AYARI KAYDET", command=self.save_filter_invert).pack(side="left", padx=8)
        ttk.Button(row2, text="FABRİKA SIFIRLA", command=self.factory_mouse).pack(side="left", padx=4)

        btns = ttk.Frame(self.tab_cal)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="PC KALİBRASYONU BAŞLAT", command=self.start_cal).pack(side="left", padx=4)
        ttk.Button(btns, text="KÖŞEYİ ŞİMDİ AL", command=self.capture_corner_gui).pack(side="left", padx=4)
        ttk.Button(btns, text="İPTAL", command=self.cancel_cal).pack(side="left", padx=4)

        ttk.Label(self.tab_cal, textvariable=self.cal_status, font=("Segoe UI", 12, "bold"), foreground="#b45309").pack(anchor="w", pady=6)

        self.cal_text = tk.Text(self.tab_cal, height=25, wrap="word", font=("Consolas", 10))
        self.cal_text.pack(fill="both", expand=True, pady=6)
        self.cal_text.insert("end", """PC Kalibrasyon:
1) Cihazları Tara / Yenile bas.
2) P1 ve P2 satırlarında RAW değeri görünmeli.
3) Oyuncu seç: P1 veya P2.
4) PC KALİBRASYONU BAŞLAT.
5) Silahı sırayla köşelere getir.
6) İstersen ekrandaki KÖŞEYİ ŞİMDİ AL butonuna bas.
   İstersen Controller üzerindeki seçili GP tuşuna bas.
7) 4 köşe alınca program CAL + SAVE gönderir ve Pico flash hafızaya kaydeder.

Not:
GP19 DIP kapalı olsa bile RAW gelir ve PC kalibrasyon yapılır.
GP19 sadece oyun mouse hareketini aktif/pasif yapar.
""")

    def build_game_tab(self):
        ttk.Label(self.tab_game, text="TeknoParrot / Paradise Lost başlatma", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=4)

        row = ttk.Frame(self.tab_game)
        row.pack(fill="x", pady=6)
        ttk.Label(row, text="TeknoParrot / Oyun EXE-BAT-LNK:", width=30).pack(side="left")
        ttk.Entry(row, textvariable=self.tp_path).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(row, text="Seç", command=self.pick_tp).pack(side="left")

        row2 = ttk.Frame(self.tab_game)
        row2.pack(fill="x", pady=6)
        ttk.Label(row2, text="İsteğe bağlı ikinci kısayol:", width=30).pack(side="left")
        ttk.Entry(row2, textvariable=self.game_path).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(row2, text="Seç", command=self.pick_game).pack(side="left")

        row3 = ttk.Frame(self.tab_game)
        row3.pack(fill="x", pady=8)
        ttk.Button(row3, text="AYARLARI KAYDET", command=self.save_cfg).pack(side="left", padx=4)
        ttk.Button(row3, text="BAŞLAT", command=self.launch_game).pack(side="left", padx=4)
        ttk.Button(row3, text="NOT DEFTERİ TUŞ TESTİ", command=self.open_notepad).pack(side="left", padx=4)

        t = tk.Text(self.tab_game, wrap="word", height=26)
        t.pack(fill="both", expand=True, pady=8)
        t.insert("end", """TeknoParrot içinde önerilen mapping:

Controller Pico:
GP6 = keyboard 6  -> P1 Trigger
GP7 = keyboard 7  -> P2 Trigger
GP8 = keyboard 8  -> Credit / Coin
GP9 = keyboard 9  -> Start

Mouse:
P1 için GT PARADISE PLAYER 1 MOUSE seç.
P2 için GT PARADISE PLAYER 2 MOUSE seç.

Önemli:
Windows masaüstünde 2 mouse tek imleci hareket ettirir. Bu normaldir.
TeknoParrot oyun içinde iki cihazı ayrı görüyorsa P1/P2 ayrı bağlanır.
Paradise Lost ayarında P2 ayrı mouse seçeneği yoksa P2 aynı Windows imlecine karışabilir; o durumda TeknoParrot RawInput / Multi Mouse ayarları kontrol edilir.
""")
        t.configure(state="disabled")

    def build_help_tab(self):
        t = tk.Text(self.tab_help, wrap="word", font=("Consolas", 10))
        t.pack(fill="both", expand=True)
        t.insert("end", """SİSTEM ÖZETİ

1) PLAYER 1 PICO
   USB cihaz: GT PARADISE PLAYER 1 MOUSE
   Görev: P1 nişangah / mouse hareketi
   GP26 = X pot
   GP27 = Y pot
   GP19 = DIP switch aktif/pasif
   GP18 = donanımsal kalibrasyon butonu

2) PLAYER 2 PICO
   USB cihaz: GT PARADISE PLAYER 2 MOUSE
   Görev: P2 nişangah / mouse hareketi
   GP26 = X pot
   GP27 = Y pot
   GP19 = DIP switch aktif/pasif
   GP18 = donanımsal kalibrasyon butonu

3) CONTROLLER PICO
   USB cihaz: GT PARADISE CONTROLLER KEYBOARD
   Görev: klavye tuşları + kredi + start + röle
   GP0 = keyboard 0
   GP1 = keyboard 1
   GP2 = keyboard 2
   GP3 = keyboard 3
   GP4 = keyboard 4
   GP5 = keyboard 5
   GP6 = keyboard 6 / P1 trigger / P1 röle tetik
   GP7 = keyboard 7 / P2 trigger / P2 röle tetik
   GP8 = keyboard 8 / kredi coin
   GP9 = keyboard 9 / start

RÖLE:
Controller GP26 = P1 röle çıkışı
Controller GP27 = P2 röle çıkışı

ÇALIŞMA ŞEKLİ:
- Oyun oynarken PC programı açık kalmak zorunda değil.
- PC programı sadece test, kalibrasyon ve TeknoParrot başlatma içindir.
- Kalibrasyon Pico flash hafızasına kaydedilir.
- PC kapanıp açılsa bile kalibrasyon kalır.

PC KALİBRASYON:
- Program P1/P2 Mouse Pico'dan RAW okur.
- 4 köşe alınır.
- Program Pico'ya CAL + SAVE gönderir.
- GP19 DIP pasif olsa bile RAW okuma devam eder.

DONANIMSAL KALİBRASYON:
- PC program olmadan P1/P2 üzerinde GP18'i 3 saniye basılı tut.
- LED hızlı yanıp söner.
- Sol üst, sağ üst, sağ alt, sol alt için GP18 kısa bas.
- 4. noktadan sonra flash'a kaydeder.

FABRİKA SIFIRLAMA:
- P1/P2 Pico'yu USB'ye takarken GP18 basılı tut.
- LED 12 kere yanıp söner ve kalibrasyon sıfırlanır.
""")
        t.configure(state="disabled")

    def log_line(self, s):
        try:
            self.log.insert("end", s + "\n")
            self.log.see("end")
        except Exception:
            pass

    def scan(self):
        self.close_devices()
        self.by_role = {"P1": None, "P2": None, "CONTROLLER": None}
        for item in self.tree.get_children():
            self.tree.delete(item)

        if serial is None:
            messagebox.showerror("PySerial yok", "PySerial kurulu değil. 02_GEREKIRSE_PYSERIAL_KUR.cmd çalıştır.")
            return

        ports = list(serial.tools.list_ports.comports())
        if not ports:
            self.status.set("COM port bulunamadı. Pico'ları tak.")
            return

        self.log_line("=== TARAMA BAŞLADI ===")
        opened = 0
        for p in ports:
            # COM1 çoğu bilgisayarda gerçek seri port; yine de deneriz.
            d = Device(p.device)
            try:
                d.open()
                self.devices.append(d)
                opened += 1
                self.tree.insert("", "end", iid=p.device, values=(p.device, "OKUNUYOR", "", "HELLO bekleniyor"))
                self.log_line(f"{p.device}: açıldı")
            except Exception as e:
                self.tree.insert("", "end", iid=p.device, values=(p.device, "AÇILAMADI", "", str(e)))
                self.log_line(f"{p.device}: AÇILAMADI -> {e}")

        self.status.set(f"{opened} COM port açıldı. 2 saniye bekle; P1/P2/Controller otomatik tanınır.")
        self.after(600, self.poll)
        self.after(1500, self.poll)

    def poll(self):
        for d in self.devices:
            d.write("HELLO?")
            d.write("GET")

    def close_devices(self):
        for d in self.devices:
            d.close()
        self.devices = []
        self.by_role = {"P1": None, "P2": None, "CONTROLLER": None}

    def update_roles(self):
        for d in self.devices:
            if d.player in self.by_role:
                self.by_role[d.player] = d
            if self.tree.exists(d.port):
                self.tree.item(d.port, values=(d.port, d.kind, d.player, d.last_line[-130:]))

    def tick(self):
        for d in self.devices:
            while True:
                try:
                    line = d.q.get_nowait()
                except queue.Empty:
                    break
                self.log_line(f"{d.port}: {line}")
        self.update_roles()
        self.update_live_status()
        self.handle_cal_button()
        self.after(120, self.tick)

    def update_live_status(self):
        p1 = self.by_role.get("P1")
        p2 = self.by_role.get("P2")
        ctl = self.by_role.get("CONTROLLER")

        def mouse_text(label, d):
            if not d:
                return f"{label}: YOK"
            active = "AKTİF" if d.active == 1 else ("PASİF/DIP KAPALI" if d.active == 0 else "BİLİNMİYOR")
            return f"{label}: {d.port} | RAW={d.raw_x},{d.raw_y} | HID={d.hid_x},{d.hid_y} | GP19={active} | FILTER={d.filter_shift} | INV={d.invert_x},{d.invert_y} | CAL={d.cal}"

        self.p1_info.set(mouse_text("P1 Mouse", p1))
        self.p2_info.set(mouse_text("P2 Mouse", p2))

        if ctl:
            pressed = [f"GP{i}->{i}" for i in KEY_PINS if ctl.buttons.get(i, 0)]
            self.controller_info.set(f"Controller: {ctl.port} | OK | {ctl.last_line[-100:]}")
            self.button_info.set("Basılı tuş: " + (", ".join(pressed) if pressed else "yok"))
            self.relay_info.set(f"Röle: P1={ctl.relay1} | P2={ctl.relay2}")
            for i, frame in self.gp_lamps.items():
                color = "#86efac" if ctl.buttons.get(i, 0) else "#e5e7eb"
                frame.configure(bg=color)
                for child in frame.winfo_children():
                    child.configure(bg=color)
        else:
            self.controller_info.set("Controller: YOK")
            self.button_info.set("Basılı tuş: Controller bekleniyor")
            self.relay_info.set("Röle: Controller bekleniyor")
            for frame in self.gp_lamps.values():
                frame.configure(bg="#e5e7eb")
                for child in frame.winfo_children():
                    child.configure(bg="#e5e7eb")

    def get_mouse(self, player=None):
        return self.by_role.get(player or self.cal_player.get())

    def start_cal(self):
        self.update_roles()
        player = self.cal_player.get()
        d = self.get_mouse(player)
        if not d:
            messagebox.showwarning("Mouse yok", f"{player} Mouse Pico bulunamadı. Cihazları Tara bas.")
            return
        if d.raw_x is None or d.raw_y is None:
            messagebox.showwarning("RAW yok", f"{player} RAW verisi henüz gelmiyor. 2 saniye bekle veya Tara/Yenile bas.")
            return

        self.cal_points = []
        self.cal_running = True
        self.cal_last_pressed = 0
        self.cal_status.set(f"{player} PC kalibrasyon başladı. {CORNER_NAMES[0]} köşeye getir, GP{self.cal_confirm_gp.get()} bas veya KÖŞEYİ ŞİMDİ AL.")
        self.cal_text.insert("end", f"\n--- {player} PC KALİBRASYON BAŞLADI ---\n")
        self.cal_text.insert("end", f"Onay tuşu: Controller GP{self.cal_confirm_gp.get()}\n")
        self.cal_text.see("end")

    def cancel_cal(self):
        self.cal_running = False
        self.cal_points = []
        self.cal_status.set("Kalibrasyon iptal edildi.")
        self.cal_text.insert("end", "\nKALİBRASYON İPTAL EDİLDİ\n")
        self.cal_text.see("end")

    def capture_corner_gui(self):
        if not self.cal_running:
            self.start_cal()
            return
        self.capture_corner("GUI")

    def handle_cal_button(self):
        if not self.cal_running:
            return
        ctl = self.by_role.get("CONTROLLER")
        if not ctl:
            return
        gp = int(self.cal_confirm_gp.get())
        pressed_now = 1 if ctl.buttons.get(gp, 0) else 0
        if pressed_now and not self.cal_last_pressed:
            self.capture_corner(f"GP{gp}")
        self.cal_last_pressed = pressed_now

    def capture_corner(self, source):
        player = self.cal_player.get()
        d = self.get_mouse(player)
        if not d or d.raw_x is None or d.raw_y is None:
            self.cal_status.set(f"{player}: RAW yok, köşe alınamadı.")
            return

        step = len(self.cal_points)
        if step >= 4:
            return

        self.cal_points.append((d.raw_x, d.raw_y))
        self.cal_text.insert("end", f"{CORNER_NAMES[step]} ONAYLANDI ({source}) RAW={d.raw_x},{d.raw_y}\n")
        self.cal_text.see("end")

        if len(self.cal_points) < 4:
            self.cal_status.set(f"{player}: {CORNER_NAMES[step]} alındı. Şimdi {CORNER_NAMES[len(self.cal_points)]} köşeye getir.")
            return

        xs = [p[0] for p in self.cal_points]
        ys = [p[1] for p in self.cal_points]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)

        if maxx <= minx + 40 or maxy <= miny + 40:
            self.cal_status.set("HATALI KALİBRASYON: X/Y aralığı çok dar. Tekrar dene.")
            self.cal_text.insert("end", "HATA: X/Y aralığı çok dar. Kayıt yapılmadı.\n")
            self.cal_running = False
            return

        margin = max(0, min(10, int(self.cal_margin_percent.get())))
        mx = (maxx - minx) * margin // 100
        my = (maxy - miny) * margin // 100

        cal_min_x = minx + mx
        cal_max_x = maxx - mx
        cal_min_y = miny + my
        cal_max_y = maxy - my

        d.write(f"CAL,{cal_min_x},{cal_max_x},{cal_min_y},{cal_max_y}")
        time.sleep(0.05)
        d.write(f"FILTER,{int(self.filter_var.get())}")
        time.sleep(0.05)
        d.write(f"INVERT,{1 if self.inv_x.get() else 0},{1 if self.inv_y.get() else 0}")
        time.sleep(0.05)
        d.write("SAVE")
        time.sleep(0.05)
        d.write("GET")

        self.cal_status.set(f"{player}: KALİBRASYON KAYDEDİLDİ / FLASH ONAYLANDI")
        self.cal_text.insert("end", f"CAL GÖNDERİLDİ: {cal_min_x},{cal_max_x},{cal_min_y},{cal_max_y}\n")
        self.cal_text.insert("end", "SAVE GÖNDERİLDİ: FLASH KAYIT\n")
        self.cal_text.see("end")
        self.cal_running = False

    def save_filter_invert(self):
        d = self.get_mouse()
        if not d:
            messagebox.showwarning("Mouse yok", "Önce P1/P2 seç ve cihazları tara.")
            return
        d.write(f"FILTER,{int(self.filter_var.get())}")
        d.write(f"INVERT,{1 if self.inv_x.get() else 0},{1 if self.inv_y.get() else 0}")
        d.write("SAVE")
        d.write("GET")
        self.cal_status.set(f"{self.cal_player.get()}: Filtre/ters ayarı kaydedildi.")

    def factory_mouse(self):
        d = self.get_mouse()
        if not d:
            messagebox.showwarning("Mouse yok", "Önce P1/P2 seç ve cihazları tara.")
            return
        if messagebox.askyesno("Fabrika sıfırla", f"{self.cal_player.get()} mouse kalibrasyonu sıfırlansın mı?"):
            d.write("FACTORY")
            d.write("GET")
            self.cal_status.set(f"{self.cal_player.get()}: fabrika ayarı gönderildi.")

    def send_relay(self, player, on):
        ctl = self.by_role.get("CONTROLLER")
        if not ctl:
            messagebox.showwarning("Controller yok", "Controller Pico bulunamadı.")
            return
        ctl.write(f"RELAY,{player},{on}")
        self.relay_info.set(f"P{player} Röle {'ÇEK' if on else 'BIRAK'} komutu gönderildi.")

    def pick_tp(self):
        p = filedialog.askopenfilename(title="TeknoParrot / oyun seç", filetypes=[("Program/Kısayol", "*.exe *.bat *.cmd *.lnk"), ("Tüm dosyalar", "*.*")])
        if p:
            self.tp_path.set(p)

    def pick_game(self):
        p = filedialog.askopenfilename(title="İkinci kısayol seç", filetypes=[("Program/Kısayol", "*.exe *.bat *.cmd *.lnk"), ("Tüm dosyalar", "*.*")])
        if p:
            self.game_path.set(p)

    def save_cfg(self):
        self.cfg["PATHS"] = {"teknoparrot": self.tp_path.get(), "game": self.game_path.get()}
        self.cfg["CAL"] = {"player": self.cal_player.get(), "confirm_gp": str(self.cal_confirm_gp.get())}
        with open(CFG_FILE, "w", encoding="utf-8") as f:
            self.cfg.write(f)
        self.status.set("Ayarlar kaydedildi.")

    def load_cfg(self):
        if os.path.exists(CFG_FILE):
            self.cfg.read(CFG_FILE, encoding="utf-8")
            self.tp_path.set(self.cfg.get("PATHS", "teknoparrot", fallback=""))
            self.game_path.set(self.cfg.get("PATHS", "game", fallback=""))
            self.cal_player.set(self.cfg.get("CAL", "player", fallback="P1"))
            try:
                self.cal_confirm_gp.set(self.cfg.getint("CAL", "confirm_gp", fallback=6))
            except Exception:
                self.cal_confirm_gp.set(6)

    def launch_game(self):
        self.save_cfg()
        target = self.game_path.get().strip() or self.tp_path.get().strip()
        if not target:
            messagebox.showwarning("Yol yok", "TeknoParrot veya oyun kısayolu seç.")
            return
        try:
            os.startfile(target)
            self.status.set("Başlatıldı: " + target)
        except Exception as e:
            messagebox.showerror("Başlatılamadı", str(e))

    def open_notepad(self):
        try:
            subprocess.Popen(["notepad.exe"])
            self.status.set("Not Defteri açıldı. Controller GP0-GP9 basınca 0-9 yazmalı.")
        except Exception as e:
            messagebox.showerror("Hata", str(e))

    def destroy(self):
        self.close_devices()
        super().destroy()

if __name__ == "__main__":
    App().mainloop()
