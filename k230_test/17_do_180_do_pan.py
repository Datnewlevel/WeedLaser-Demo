# TEST 17 - DO 180 DO CUA PAN RA DO TRUC MOTOR  [chay tu THE SD]
#
# Chep thanh /sdcard/main.py, cam the, cap nguon. KHONG can IDE.
#   Goc cong don hien SO TO tren LCD, dong thoi ghi ra /sdcard/kq_goc_pan.txt
#
# ==========================================================
#  MUC DICH
# ==========================================================
# Nguoi dung muon gioi han PAN o +-180 do GOC THAT.
# Nhung code cong don goc lam viec bang DO O TRUC MOTOR.
# Quy doi thi can ti so truyen cua PAN - ma ta MOI DO TI SO CUA TILT (~4:1),
# CHUA DO PAN, va hai truc co the khac nhau.
#
# Doan la nguy hiem: neu PAN gan truc tiep ma lay 4:1 thi 180 do that se
# thanh 720 do truc motor - vuot xa gioi han xoan day 340 do.
#
# Nen dung lai dung cach da hieu qua voi TILT: DO THANG 180 do ra do truc
# motor, khoi can ti so truyen. Ti so trieu tieu vi ca do lan cong don deu
# cung mot don vi.
#
# ==========================================================
#  CACH DUNG
# ==========================================================
#   1. Danh dau huong cum dang chi (bang but / bang dinh / vat moc tren san)
#   2. Chay script. PAN quay tung buoc, goc cong don hien so to tren man hinh
#   3. Khi cum da quay DUNG NUA VONG (180 do - quay lung lai huong ban dau),
#      RUT DAY NGUON va nho con so tren man hinh
#   4. Con so do chinh la PAN_GIOI_HAN, dien thang vao main.py
#
# 180 do de uoc luong bang mat: cum quay lung lai dung huong ban dau.
# Khong can chinh xac tuyet doi - sai vai do khong anh huong gi.
#
# ==========================================================
#  AN TOAN
# ==========================================================
#   * PAN co ~340 do moi phia truoc khi xoan day, do 180 do la con nhieu du.
#   * TILT khong nhan lenh nao ngoai F6-toc-do-0.
#   * KHONG doc encoder (bai 14: phan hoi 8 byte doi nguoc bus -> lech pha).
#   * Tu dong dung khi cong don vuot TRAN_DO - phong khi khong ai de y.
#   * Chan laser IO43 ep xuong muc thap ngay dong dau.

import time, sys
from machine import UART, FPIOA

LOG = "/sdcard/kq_goc_pan.txt"

UART_ID, TX_PIN, RX_PIN, BAUD = 2, 11, 12, 115200
ADDR_PAN  = 0xE1
ADDR_TILT = 0xE2

CMD_ENABLE = 0xF3
CMD_SPEED  = 0xF6

# Chieu 0 hay 1 deu duoc - co khi PAN doi xung. Buoc THU dau tien de xac nhan.
CHIEU = 0
TEN_CHIEU = "chieu 0" if CHIEU == 0 else "chieu 1"

MSTEP = 64
NAC   = 2               # nhanh hon TILT mot chut vi PAN phai di xa hon nhieu
DO_MOI_GIAY = (30000.0 / (MSTEP * 200)) * NAC * 6      # 28.1 do/giay o nac 2

BUOC_GIAY   = 0.5       # moi buoc -> 14.1 do truc motor
NGHI_GIAY   = 0.6
THU_GIAY    = 0.4
THU_NGHI    = 5.0
TRAN_DO     = 2000.0    # tu dong dung - du cho ca truong hop giam toc 10:1

CHO_XEM = 12

W, H = 640, 480
logf = None
uart = None
tong_do = 0.0


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


# Mo UART va dung ca hai truc TRUOC man hinh.
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
    print("UART mo OK, da dung ca 2 truc.")
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
            logf.flush()      # flush MOI dong: nguoi dung se RUT DIEN dot ngot
        except Exception:
            pass


def man_so(goc, phu, mau=(0, 255, 120)):
    try:
        img = image.Image(W, H, image.RGB888)
        img.clear()
        img.draw_rectangle(0, 0, W, H, color=(0, 0, 40), fill=True)
        img.draw_string_advanced(14, 10, 26, "PAN quay %s" % TEN_CHIEU,
                                 color=(255, 220, 0))
        img.draw_string_advanced(30, 105, 96, "%.0f" % goc, color=mau)
        img.draw_string_advanced(360, 170, 30, "do", color=mau)
        y = 255
        for d in phu:
            img.draw_string_advanced(14, y, 23, d, color=(255, 255, 255))
            y += 30
        Display.show_image(img)
        img = None
    except Exception:
        pass


def man_chu(dong, mau=(255, 255, 255)):
    try:
        img = image.Image(W, H, image.RGB888)
        img.clear()
        img.draw_rectangle(0, 0, W, H, color=(0, 0, 40), fill=True)
        y = 16
        for i, d in enumerate(dong):
            img.draw_string_advanced(14, y, 30 if i == 0 else 22, d,
                                     color=(255, 220, 0) if i == 0 else mau)
            y += 40 if i == 0 else 29
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


def mot_buoc(giay):
    global tong_do
    uart.write(khung(ADDR_PAN, CMD_SPEED, ((1 if CHIEU else 0) << 7) | NAC))
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) / 1000.0 < giay:
        time.sleep_ms(20)
    dung_het()
    that = time.ticks_diff(time.ticks_ms(), t0) / 1000.0
    tong_do += DO_MOI_GIAY * that
    return that


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
    ghi("DO 180 DO CUA PAN RA DO TRUC MOTOR - %s" % TEN_CHIEU)
    ghi("=" * 56)
    ghi("Don vi: DO O TRUC MOTOR (khong can biet ti so truyen)")
    ghi("nac %d @ Mstep %d = %.2f do/giay" % (NAC, MSTEP, DO_MOI_GIAY))
    ghi("Moi buoc %.1f giay = %.1f do, nghi %.1f giay"
        % (BUOC_GIAY, DO_MOI_GIAY * BUOC_GIAY, NGHI_GIAY))
    ghi("Tu dong dung khi vuot %.0f do" % TRAN_DO)
    ghi("")
    ghi("RUT DIEN khi cum da quay DUNG NUA VONG, nho so tren man hinh.")

    for t in range(CHO_XEM, 0, -1):
        man_chu(["DO 180 DO CUA PAN",
                 "",
                 "DANH DAU huong cum dang chi",
                 "NGAY BAY GIO.",
                 "",
                 "Quay du NUA VONG -> RUT DIEN",
                 "va nho so tren man hinh.",
                 "",
                 "Bat dau sau %d giay..." % t])
        time.sleep(1)

    # ---- Buoc THU: xac nhan chieu ----
    ghi(">>> Buoc THU %.1f giay" % THU_GIAY)
    mot_buoc(THU_GIAY)
    ghi("   tong = %.1f do" % tong_do)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) / 1000.0 < THU_NGHI:
        man_so(tong_do,
               ["PAN vua nhuc nhich dung khong?",
                "Muon doi chieu -> tat nguon,",
                "doi CHIEU o dau file.",
                "",
                "Di tiep sau %.0f giay..."
                % (THU_NGHI - time.ticks_diff(time.ticks_ms(), t0) / 1000.0)],
               mau=(255, 220, 0))
        time.sleep_ms(200)

    ghi(">>> Bat dau quay tung buoc")
    buoc = 0
    while tong_do < TRAN_DO:
        buoc += 1
        mot_buoc(BUOC_GIAY)
        ghi("   buoc %d: tong = %.1f do" % (buoc, tong_do))
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) / 1000.0 < NGHI_GIAY:
            man_so(tong_do,
                   ["buoc %d" % buoc,
                    "",
                    "Du NUA VONG -> RUT DIEN NGAY",
                    "va nho con so nay."])
            time.sleep_ms(100)

    dung_het()
    ghi("")
    ghi("!!! Da cham tran %.0f do ma chua thay rut dien." % TRAN_DO)

    if logf:
        logf.close()
        logf = None

    while True:
        man_so(tong_do,
               ["DA TU DUNG o tran %.0f do." % TRAN_DO,
                "Chua du nua vong?",
                "",
                "Tang TRAN_DO roi chay lai."],
               mau=(255, 140, 0))
        time.sleep(2)

except KeyboardInterrupt:
    pass
except BaseException as e:
    # KHONG dung sys.print_exception(e, file) - ban MicroPython nay khong
    # nhan tham so file, no nem loi roi mat sach traceback.
    ghi("LOI: %s: %s" % (type(e).__name__, e))
    ghi("   tong da quay = %.1f do" % tong_do)
    sys.print_exception(e)
    try:
        man_chu(["LOI - xem kq_goc_pan.txt", "", str(e)], mau=(255, 80, 80))
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
