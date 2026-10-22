# TEST 16 - DO GOC CHAM CU CUA TILT  [chay tu THE SD]
#
# Chep thanh /sdcard/main.py, cam the, cap nguon. KHONG can IDE.
#   Goc cong don hien SO TO tren LCD, dong thoi ghi ra /sdcard/kq_goc_tilt.txt
#
# CACH DUNG
#   TILT quay tung buoc nho, moi buoc nghi mot chut va hien goc da quay.
#   Nhin cum: THAY CHAM CU thi RUT DAY NGUON va nho con so tren man hinh.
#   Do la gioi han cua phia do, tinh tu zero.
#
# ==========================================================
#  DON VI: DO O TRUC MOTOR - CO Y KHONG QUY RA GOC THAT
# ==========================================================
# Ta chua biet ti so truyen. Nhung KHONG CAN biet:
#   - bai nay do gioi han bang DO O TRUC MOTOR
#   - code cong don goc trong main.py cung tinh bang DO O TRUC MOTOR
#   => ti so truyen trieu tieu o ca hai ve, khong anh huong gi
# No chi can neu muon hien goc that ra ngoai, ma viec do khong quan trong.
#
#   nac 1 @ Mstep 64 = 2.3438 RPM = 14.06 do/giay  o TRUC MOTOR
#
# ==========================================================
#  CHUAN BI
# ==========================================================
#   * TILT phai da duoc Set 0 + NearMode, va zero dat o GIUA tam.
#     Script cho CHO_VE_ZERO giay dau de NearMode dua no ve zero xong han.
#   * Cam dien de cho de rut. Rut la mat dien ca cum - motor het cung truc,
#     dau tilt co the tu roi, nen giu tay do lay cum truoc khi rut.
#
# ==========================================================
#  AN TOAN
# ==========================================================
#   * Quay TUNG BUOC 0.4 giay roi nghi 0.8 giay -> moi buoc 5.6 do truc motor.
#     Nghi giua cac buoc de kip doc so va kip phan ung.
#   * MKS la vong kin: cham cu no se co day manh hon de bu sai so. Buoc chi
#     0.4 giay nen moi lan ti vao cu la rat ngan.
#   * Tu dong dung khi cham TRAN_DO - phong truong hop khong ai de y.
#   * KHONG doc encoder (bai 14: phan hoi 8 byte doi nguoc bus -> lech pha).
#   * PAN khong nhan lenh nao ngoai F6-toc-do-0.
#   * Chan laser IO43 ep xuong muc thap ngay dong dau.

import time, sys
from machine import UART, FPIOA

LOG = "/sdcard/kq_goc_tilt.txt"

UART_ID, TX_PIN, RX_PIN, BAUD = 2, 11, 12, 115200
ADDR_PAN  = 0xE1
ADDR_TILT = 0xE2

CMD_ENABLE = 0xF3
CMD_SPEED  = 0xF6

# ---------- CHIEU ----------
# main_autorun_full.py dung: motors.speed(ADDR_TILT, 1 if ema_y > 0 else 0, ...)
# ema_y > 0 nghia la muc tieu o DUOI tam anh -> can cui XUONG -> chieu 1.
# Vay chieu 0 = LEN, chieu 1 = XUONG.
# Buoc dau tien la buoc THU: quay ngan roi nghi lau de xac nhan dung chieu.
# Neu no di NGUOC voi mong doi -> tat nguon, doi so nay.
CHIEU = 1               # 0 = LEN, 1 = XUONG
# KET QUA DA DO: chieu LEN (CHIEU = 0) cham cu o 141 do truc motor.
# Gio do chieu XUONG.
TEN_CHIEU = "LEN" if CHIEU == 0 else "XUONG"

MSTEP = 64
NAC   = 1
DO_MOI_GIAY = (30000.0 / (MSTEP * 200)) * NAC * 6      # 14.06 do/giay

BUOC_GIAY   = 0.4       # moi buoc quay bao lau -> 5.6 do truc motor
NGHI_GIAY   = 0.8       # nghi giua hai buoc de kip doc va phan ung
THU_GIAY    = 0.3       # buoc THU dau tien, ngan hon
THU_NGHI    = 5.0       # nghi lau sau buoc thu de xac nhan chieu
TRAN_DO     = 400.0     # tu dong dung khi cong don vuot muc nay

CHO_VE_ZERO = 15        # cho NearMode dua TILT ve zero xong han
CHO_XEM     = 10

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
    """Hien goc bang SO THAT TO de doc duoc tu xa."""
    try:
        img = image.Image(W, H, image.RGB888)
        img.clear()
        img.draw_rectangle(0, 0, W, H, color=(0, 0, 40), fill=True)
        img.draw_string_advanced(14, 10, 26, "TILT quay %s" % TEN_CHIEU,
                                 color=(255, 220, 0))
        img.draw_string_advanced(30, 110, 96, "%.1f" % goc, color=mau)
        img.draw_string_advanced(340, 175, 30, "do", color=mau)
        y = 260
        for d in phu:
            img.draw_string_advanced(14, y, 24, d, color=(255, 255, 255))
            y += 32
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
    """Quay TILT dung `giay` giay roi dung. Cong vao tong_do."""
    global tong_do
    uart.write(khung(ADDR_TILT, CMD_SPEED, ((1 if CHIEU else 0) << 7) | NAC))
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
    ghi("DO GOC CHAM CU CUA TILT - chieu %s" % TEN_CHIEU)
    ghi("=" * 56)
    ghi("Don vi: DO O TRUC MOTOR (khong quy ra goc that - khong can ti so)")
    ghi("nac %d @ Mstep %d = %.2f do/giay" % (NAC, MSTEP, DO_MOI_GIAY))
    ghi("Moi buoc %.1f giay = %.1f do, nghi %.1f giay"
        % (BUOC_GIAY, DO_MOI_GIAY * BUOC_GIAY, NGHI_GIAY))
    ghi("Tu dong dung khi vuot %.0f do" % TRAN_DO)
    ghi("")

    for t in range(CHO_VE_ZERO, 0, -1):
        man_chu(["CHO TILT VE ZERO",
                 "",
                 "NearMode dang dua TILT ve zero.",
                 "Cho no dung han roi moi ra lenh.",
                 "",
                 "Con %d giay..." % t])
        time.sleep(1)
    ghi("Da cho %d giay cho NearMode ve zero." % CHO_VE_ZERO)

    for t in range(CHO_XEM, 0, -1):
        man_chu(["DO GOC CHAM CU - TILT %s" % TEN_CHIEU,
                 "",
                 "Giu tay do lay cum.",
                 "Thay CHAM CU -> RUT DAY NGUON",
                 "va nho con so tren man hinh.",
                 "",
                 "Cam dien de cho de rut.",
                 "",
                 "Bat dau sau %d giay..." % t])
        time.sleep(1)

    # ---- Buoc THU: xac nhan dung chieu truoc khi di tiep ----
    ghi(">>> Buoc THU %.1f giay de xac nhan chieu" % THU_GIAY)
    mot_buoc(THU_GIAY)
    ghi("   tong = %.1f do" % tong_do)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) / 1000.0 < THU_NGHI:
        man_so(tong_do,
               ["No vua di %s dung khong?" % TEN_CHIEU,
                "SAI CHIEU -> tat nguon ngay,",
                "doi CHIEU o dau file.",
                "",
                "Di tiep sau %.0f giay..."
                % (THU_NGHI - time.ticks_diff(time.ticks_ms(), t0) / 1000.0)],
               mau=(255, 220, 0))
        time.sleep_ms(200)

    # ---- Quay tung buoc cho den khi nguoi dung rut dien ----
    ghi(">>> Bat dau quay tung buoc")
    buoc = 0
    while tong_do < TRAN_DO:
        buoc += 1
        mot_buoc(BUOC_GIAY)
        ghi("   buoc %d: tong = %.1f do" % (buoc, tong_do))
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) / 1000.0 < NGHI_GIAY:
            man_so(tong_do,
                   ["buoc %d - dang quay %s" % (buoc, TEN_CHIEU),
                    "",
                    "CHAM CU -> RUT DIEN NGAY",
                    "va nho con so nay."])
            time.sleep_ms(100)

    dung_het()
    ghi("")
    ghi("!!! Da cham tran %.0f do ma chua thay rut dien." % TRAN_DO)
    ghi("    Tu dong dung. Co the chieu bi sai, hoac ti so truyen lon.")

    if logf:
        logf.close()
        logf = None

    while True:
        man_so(tong_do,
               ["DA TU DUNG o tran %.0f do." % TRAN_DO,
                "Chua thay cham cu.",
                "",
                "Kiem tra lai CHIEU, hoac",
                "tang TRAN_DO roi chay lai."],
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
        man_chu(["LOI - xem kq_goc_tilt.txt", "", str(e)], mau=(255, 80, 80))
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
