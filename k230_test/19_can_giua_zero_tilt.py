# TEST 19 - CAN GIUA LAI ZERO CUA TILT  [chay tu THE SD]
#
# Chep thanh /sdcard/main.py, cam the, cap nguon. KHONG can IDE.
#
# ==========================================================
#  VAN DE
# ==========================================================
# Nguoi dung phat hien: mat dien khi TILT dang o CU DUOI thi luc cap nguon
# lai NearMode KHONG keo nguoc ve, ma DI THEM VAO CU.
#
# KHONG phai bug driver. NearMode lam dung dinh nghia "duong ngan nhat",
# va encoder tuyet doi trong MOT vong = 360 do:
#
#   zero hien tai: cu tren +141 do, cu duoi -203 do  (tong tam 344 do)
#
#   tu cu TREN (+141): di thang 141 | di vong 360-141 = 219  -> chon 141 DUNG
#   tu cu DUOI (-203): di thang 203 | di vong 360-203 = 157  -> chon 157 SAI
#
# 157 < 203 nen no thay huong AM ngan hon -> di THEM vao cu duoi.
#
# Goc re: ZERO DAT LECH. Cach cu duoi 203 do, VUOT 180 do.
#
# ==========================================================
#  CACH SUA
# ==========================================================
# Dat lai zero o GIUA tam: 344/2 = 172 do moi phia.
# Ca hai cu deu cach zero 172 < 180 -> NearMode LUON chon dung huong.
# Bien du an toan: 180 - 172 = 8 do.
#
# Zero hien tai lech 31 do ve phia cu TREN, nen phai dich zero XUONG 31 do:
#     31 do x 35.56 xung/do (Mstep 64) = 1102 xung
#
# ==========================================================
#  TRINH TU
# ==========================================================
#   1. Cap nguon voi 0_Mode = NearMode nhu binh thuong.
#      -> driver tu dua TILT ve zero CU. Cho no dung han.
#   2. Script nay dich TILT XUONG dung 1102 xung bang lenh 0xFD
#      (lenh da kiem chung 10/09, bai 18).
#   3. Man hinh bao "SET 0 BAY GIO". Vao menu driver TILT bam Set 0.
#   4. Tat bat nguon, kiem tra no ve dung vi tri giua.
#   5. Cap nhat main.py:  TILT_CU_LEN = 172.0   TILT_CU_XUONG = -172.0
#
# ==========================================================
#  AN TOAN
# ==========================================================
#   31 do truc motor = ~7.8 do goc that (ti so 4:1). Rat nho, va di tu
#   GIUA tam nen con 141 do du ve phia duoi. PAN khong nhan lenh nao
#   ngoai F6-toc-do-0. Chan laser IO43 ep xuong muc thap ngay dong dau.

import time, sys
from machine import UART, FPIOA

LOG = "/sdcard/kq_can_giua.txt"

UART_ID, TX_PIN, RX_PIN, BAUD = 2, 11, 12, 115200
ADDR_PAN  = 0xE1
ADDR_TILT = 0xE2

CMD_ENABLE = 0xF3
CMD_SPEED  = 0xF6
CMD_MOVE   = 0xFD

MSTEP = 64
XUNG_MOI_DO = (MSTEP * 200) / 360.0        # 35.56

# Do thuc te 10/09 bang 16_do_goc_cham_cu_tilt.py
CU_LEN, CU_XUONG = 141.0, -203.0
TONG = CU_LEN - CU_XUONG                   # 344
GIUA = TONG / 2                            # 172
LECH = CU_LEN - GIUA                       # 31 - zero dang lech ve phia cu tren
XUNG_DICH = int(LECH * XUNG_MOI_DO)        # 1102
CHIEU_XUONG = 1                            # chieu 1 = XUONG (theo main.py)
NAC = 4

CHO_VE_ZERO = 25        # cho NearMode dua TILT ve zero CU xong han
CHO_XEM = 10

W, H = 640, 480
logf = None
uart = None


# ---- AN TOAN: ep chan laser xuong muc thap NGAY ----
try:
    from machine import Pin as _P
    _f0 = FPIOA()
    _f0.set_function(43, getattr(FPIOA, "GPIO43"))
    _P(43, _P.OUT).off()
except Exception as _e:
    print("!!! KHONG ep duoc chan laser:", _e)


def khung(addr, *data):
    fr = [addr] + list(data)
    fr.append(sum(fr) & 0xFF)
    return bytes(fr)


# parity PHAI la UART.PARITY_NONE (hang so int) - dat parity=None se nem
# TypeError va script chet truoc khi kip lam gi.
try:
    _fp = FPIOA()
    _fp.set_function(TX_PIN, FPIOA.UART2_TXD)
    _fp.set_function(RX_PIN, FPIOA.UART2_RXD)
    uart = UART(UART_ID, baudrate=BAUD, bits=UART.EIGHTBITS,
                parity=UART.PARITY_NONE, stop=UART.STOPBITS_ONE)
    for _a in (ADDR_PAN, ADDR_TILT):
        uart.write(khung(_a, CMD_ENABLE, 0x01))
        time.sleep_ms(30)
        uart.write(khung(_a, CMD_SPEED, 0x00))
        time.sleep_ms(30)
    print("UART mo OK.")
except Exception as _e:
    print("!!! KHONG MO DUOC UART:", _e)
    uart = None

from media.display import *
from media.media import *
import image


def ghi(s):
    print(s)
    if logf:
        try:
            logf.write(s + "\n")
            logf.flush()
        except Exception:
            pass


def man(dong, mau=(255, 255, 255)):
    try:
        img = image.Image(W, H, image.RGB888)
        img.clear()
        img.draw_rectangle(0, 0, W, H, color=(0, 0, 40), fill=True)
        y = 14
        for i, d in enumerate(dong):
            img.draw_string_advanced(14, y, 30 if i == 0 else 22, d,
                                     color=(255, 220, 0) if i == 0 else mau)
            y += 40 if i == 0 else 28
        Display.show_image(img)
        img = None
    except Exception:
        pass


def dung_het():
    if uart is None:
        return
    try:
        for a in (ADDR_PAN, ADDR_TILT):
            uart.write(khung(a, CMD_SPEED, 0x00))
            time.sleep_ms(20)
    except Exception:
        pass


try:
    logf = open(LOG, "w")
except Exception as e:
    print("Khong mo duoc log:", e)

try:
    if uart is None:
        raise RuntimeError("UART khong mo duoc")

    Display.init(Display.ST7701, width=W, height=H, to_ide=False)
    MediaManager.init()

    ghi("=" * 56)
    ghi("CAN GIUA LAI ZERO CUA TILT")
    ghi("=" * 56)
    ghi("Zero hien tai: cu tren +%.0f, cu duoi %.0f (tong %.0f do)"
        % (CU_LEN, CU_XUONG, TONG))
    ghi("Van de: cu duoi cach zero %.0f do > 180 -> NearMode di vong"
        % abs(CU_XUONG))
    ghi("        (360 - %.0f = %.0f < %.0f nen no chon huong AM)"
        % (abs(CU_XUONG), 360 - abs(CU_XUONG), abs(CU_XUONG)))
    ghi("")
    ghi("Sua: dich zero XUONG %.0f do = %d xung" % (LECH, XUNG_DICH))
    ghi("Sau khi sua: ca hai cu cach zero %.0f do < 180, du bien %.0f do"
        % (GIUA, 180 - GIUA))
    ghi("")

    for t in range(CHO_VE_ZERO, 0, -1):
        man(["CHO TILT VE ZERO CU",
             "",
             "NearMode dang dua TILT ve zero cu.",
             "Cho no dung HAN roi moi dich.",
             "",
             "Con %d giay..." % t])
        time.sleep(1)

    for t in range(CHO_XEM, 0, -1):
        man(["CAN GIUA ZERO TILT",
             "",
             "Sap dich TILT XUONG %.0f do" % LECH,
             "(%d xung, ~%.1f do goc that)" % (XUNG_DICH, LECH / 4.0),
             "",
             "Bat dau sau %d giay..." % t,
             "",
             "TAT NGUON neu thay bat thuong."])
        time.sleep(1)

    ghi(">>> Dich XUONG %d xung o nac %d" % (XUNG_DICH, NAC))
    val = (CHIEU_XUONG << 7) | NAC
    p = XUNG_DICH
    fr = khung(ADDR_TILT, CMD_MOVE, val,
               (p >> 24) & 0xFF, (p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF)
    try:
        while uart.any():
            uart.read()
    except Exception:
        pass
    uart.write(fr)
    ghi("   TX: %s" % " ".join("%02X" % b for b in fr))

    rpm = NAC * 30000.0 / (MSTEP * 200)
    giay = XUNG_DICH / (rpm / 60 * MSTEP * 200)
    ghi("   du kien %.2f giay" % giay)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) / 1000.0 < giay + 1.5:
        man(["DANG DICH...",
             "",
             "%.1f / %.1f giay"
             % (time.ticks_diff(time.ticks_ms(), t0) / 1000.0, giay)],
            mau=(0, 255, 120))
        time.sleep_ms(150)
    dung_het()
    rx = b""
    try:
        rx = uart.read() or b""
    except Exception:
        pass
    ghi("   RX: %s" % (" ".join("%02X" % b for b in rx) if rx else "(khong co)"))
    ghi(">>> DA DICH XONG. Bay gio vao menu driver TILT bam Set 0.")

    if logf:
        logf.close()
        logf = None

    while True:
        man(["SET 0 BAY GIO",
             "",
             "TILT dang o GIUA tam.",
             "Vao menu driver TILT -> Set 0.",
             "",
             "Sau do tat bat nguon, kiem tra",
             "no ve dung vi tri nay.",
             "",
             "Roi bao toi cap nhat main.py:",
             "  TILT_CU_LEN   = 172",
             "  TILT_CU_XUONG = -172"],
            mau=(255, 220, 0))
        time.sleep(2)

except KeyboardInterrupt:
    pass
except BaseException as e:
    # KHONG dung sys.print_exception(e, file) - ban MicroPython nay khong
    # nhan tham so file.
    ghi("LOI: %s: %s" % (type(e).__name__, e))
    sys.print_exception(e)
    try:
        man(["LOI - xem kq_can_giua.txt", "", str(e)], mau=(255, 80, 80))
        time.sleep(30)
    except Exception:
        pass
finally:
    dung_het()
    if uart is not None:
        try:
            uart.deinit()
        except Exception:
            pass
    if logf:
        try:
            logf.close()
        except Exception:
            pass
    try:
        Display.deinit()
    except Exception:
        pass
    time.sleep_ms(100)
    try:
        MediaManager.deinit()
    except Exception:
        pass
