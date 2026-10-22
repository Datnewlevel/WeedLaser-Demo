# TEST 15 - DO TI SO TRUYEN CA HAI TRUC  [chay tu THE SD]
#
# Chep thanh /sdcard/main.py, cam the, cap nguon. KHONG can IDE.
#   Tien trinh hien len LCD, ket qua ghi ra /sdcard/kq_ti_so.txt
#
# ==========================================================
#  VI SAO CAN SO NAY
# ==========================================================
# TILT da co moc tuyet doi (Set 0 + NearMode chay tot, dat duoc ngay trong
# che do CR_UART nen KHONG phai doi Mode). PAN thi khong dung duoc vi tam
# quay 680 do vuot ranh gioi mot vong -> NearMode chon nham zero tuong duong.
#
# De lam GIOI HAN MEM cho TILT phai cong don goc, ma cong don goc can biet:
#   "mot nac toc do trong mot giay thi CUM quay bao nhieu do"
#
#   nac 1 @ Mstep 64 = 2.3438 RPM = 14.06 do/giay  o TRUC MOTOR
#   goc cum = 14.06 / ti_so_truyen
#
# Ti so truyen hien VAN DANG UOC LUONG (~1:1 suy tu PX_MOI_NAC), chua do
# lan nao. Sai o day di thang vao gioi han mem - ma gioi han mem sai thi
# TILT lai cham cu.
#
# ==========================================================
#  CACH DO
# ==========================================================
# PAN  : chay nac 1 trong 10 giay  -> truc motor quay 140.6 do
# TILT : chay nac 1 trong 1.5 giay -> truc motor quay 21.1 do, roi QUAY NGUOC
#        dung bay nhieu de ve lai cho cu
#
#   ti so truyen = goc_truc_motor / goc_cum_do_duoc
#   ~1 la gan truc tiep;  ~5 la co hop giam toc 5:1
#
# CHUAN BI TRUOC KHI CHAY
#   PAN : danh dau vi tri hien tai bang but hoac bang dinh
#   TILT: dat dien thoai (app thuoc do goc) len mat tilt, ghi so truoc/sau
#
# ==========================================================
#  AN TOAN
# ==========================================================
#   * TILT chi chay 1.5 giay: xau nhat (ti so 1:1) la 21.1 do, tu giua tam
#     con du 24 do truoc khi cham cu. Chay xong tu quay nguoc ve cho cu.
#   * KHONG doc encoder. Bai 14 da chung minh: phan hoi 8 byte doi nguoc lai
#     bus lam driver nghe chinh minh -> lech pha -> quay mat kiem soat.
#     Bai nay CHI GUI, khong doc byte nao.
#   * Cho 20 giay dau de driver tu chay ve zero (NearMode) xong han roi moi
#     bat dau - khong ra lenh chong len chuyen dong do.
#   * Chan laser IO43 ep xuong muc thap ngay dong dau.

import time, sys
from machine import UART, FPIOA

LOG = "/sdcard/kq_ti_so.txt"

UART_ID, TX_PIN, RX_PIN, BAUD = 2, 11, 12, 115200
ADDR_PAN  = 0xE1
ADDR_TILT = 0xE2

CMD_ENABLE = 0xF3
CMD_SPEED  = 0xF6

MSTEP = 64
NAC   = 1
RPM_MOI_NAC = 30000.0 / (MSTEP * 200)      # 2.3438
DO_MOI_GIAY = RPM_MOI_NAC * NAC * 6        # 14.06 do/giay o truc motor

PAN_GIAY  = 10.0        # 140.6 do truc motor - PAN co 680 do, thoai mai
TILT_GIAY = 1.5         # 21.1 do truc motor - tu giua tam con du 24 do

CHO_VE_ZERO = 20        # giay: cho NearMode chay ve zero xong han
CHO_XEM     = 15        # giay: dem nguoc de kip chuan bi do

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


# Mo UART va dung ca hai truc TRUOC man hinh: man hinh hong thi motor van
# da duoc dung. parity PHAI la UART.PARITY_NONE (hang so int) - dat
# parity=None se nem TypeError va script chet truoc khi kip lam gi.
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
            logf.flush()
        except Exception:
            pass


def man_hinh(dong, mau=(255, 255, 255)):
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


def chay(addr, chieu, giay, tieu_de, ghi_chu):
    """Quay mot truc dung `giay` giay o nac NAC roi dung. Tra ve giay thuc te."""
    uart.write(khung(addr, CMD_SPEED, ((1 if chieu else 0) << 7) | NAC))
    t0 = time.ticks_ms()
    while True:
        troi = time.ticks_diff(time.ticks_ms(), t0) / 1000.0
        if troi >= giay:
            break
        man_hinh([tieu_de,
                  "",
                  "%.1f / %.1f giay" % (troi, giay),
                  "",
                  ghi_chu,
                  "",
                  "TAT NGUON neu thay bat thuong."],
                 mau=(0, 255, 120))
        time.sleep_ms(150)
    dung_het()
    return time.ticks_diff(time.ticks_ms(), t0) / 1000.0


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
    ghi("DO TI SO TRUYEN CA HAI TRUC")
    ghi("=" * 56)
    ghi("Mstep %d -> nac 1 = %.4f RPM = %.2f do/giay (TRUC MOTOR)"
        % (MSTEP, RPM_MOI_NAC, DO_MOI_GIAY))
    ghi("PAN : nac %d trong %.1f giay -> %.1f do truc motor"
        % (NAC, PAN_GIAY, DO_MOI_GIAY * PAN_GIAY))
    ghi("TILT: nac %d trong %.1f giay -> %.1f do truc motor (roi quay nguoc ve)"
        % (NAC, TILT_GIAY, DO_MOI_GIAY * TILT_GIAY))
    ghi("KHONG doc encoder.")
    ghi("")

    # ---- Cho NearMode chay ve zero xong han ----
    for t in range(CHO_VE_ZERO, 0, -1):
        man_hinh(["CHO TILT VE ZERO",
                  "",
                  "NearMode dang dua TILT ve zero.",
                  "Cho no dung han roi moi ra lenh,",
                  "de khong chong len chuyen dong do.",
                  "",
                  "Con %d giay..." % t])
        time.sleep(1)
    ghi("Da cho %d giay cho NearMode ve zero." % CHO_VE_ZERO)

    # ---- Chuan bi do ----
    for t in range(CHO_XEM, 0, -1):
        man_hinh(["CHUAN BI DO",
                  "",
                  "PAN : danh dau vi tri hien tai",
                  "TILT: dat dien thoai len mat tilt,",
                  "      ghi lai so goc BAY GIO",
                  "",
                  "Bat dau sau %d giay..." % t])
        time.sleep(1)

    # ---- PAN ----
    ghi("")
    ghi("### PAN")
    tt = chay(ADDR_PAN, 0, PAN_GIAY, "PAN DANG QUAY",
              "PAN co thuc su quay khong?")
    goc_motor = DO_MOI_GIAY * tt
    ghi("   chay %.2f giay -> truc motor quay %.1f do" % (tt, goc_motor))
    ghi("   ti so truyen PAN = %.1f / goc_cum_do_duoc" % goc_motor)
    pan_goc = goc_motor
    time.sleep(2)

    # ---- TILT: di roi ve ----
    ghi("")
    ghi("### TILT")
    man_hinh(["TILT - GHI SO GOC TRUOC",
              "",
              "Ghi lai so tren dien thoai",
              "NGAY BAY GIO.",
              "",
              "TILT se quay sau 8 giay."],
             mau=(255, 220, 0))
    time.sleep(8)

    tt = chay(ADDR_TILT, 1, TILT_GIAY, "TILT DANG QUAY (chieu 1)",
              "Quay xong hay ghi so goc moi.")
    goc_motor = DO_MOI_GIAY * tt
    ghi("   chay %.2f giay -> truc motor quay %.1f do" % (tt, goc_motor))
    ghi("   ti so truyen TILT = %.1f / (goc_sau - goc_truoc)" % goc_motor)
    tilt_goc = goc_motor

    man_hinh(["TILT - GHI SO GOC SAU",
              "",
              "Ghi lai so tren dien thoai.",
              "",
              "Sau 10 giay TILT se quay",
              "NGUOC ve dung cho cu."],
             mau=(255, 220, 0))
    time.sleep(10)

    tt = chay(ADDR_TILT, 0, TILT_GIAY, "TILT QUAY NGUOC VE CHO CU", "")
    ghi("   da quay nguoc %.2f giay de ve cho cu" % tt)

    ghi("")
    ghi("=" * 56)
    ghi("CACH TINH")
    ghi("  ti so PAN  = %.1f / goc_cum_PAN_do_duoc" % pan_goc)
    ghi("  ti so TILT = %.1f / (goc_sau - goc_truoc)" % tilt_goc)
    ghi("  ~1 la gan truc tiep;  ~5 la hop giam toc 5:1")
    ghi("=" * 56)

    if logf:
        logf.close()
        logf = None

    while True:
        man_hinh(["XONG - TINH TI SO",
                  "",
                  "ti so PAN  = %.0f / goc_PAN_do_duoc" % pan_goc,
                  "ti so TILT = %.0f / (sau - truoc)" % tilt_goc,
                  "",
                  "Ket qua ghi vao the:",
                  "  /sdcard/kq_ti_so.txt",
                  "",
                  "Tat nguon khi xem xong."],
                 mau=(0, 255, 120))
        time.sleep(2)

except KeyboardInterrupt:
    pass
except BaseException as e:
    # KHONG dung sys.print_exception(e, file) - ban MicroPython nay khong
    # nhan tham so file, no nem loi roi mat sach traceback.
    ghi("LOI: %s: %s" % (type(e).__name__, e))
    sys.print_exception(e)
    try:
        man_hinh(["LOI - xem kq_ti_so.txt", "", str(e)], mau=(255, 80, 80))
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
