# TEST 18 - KIEM CHUNG LENH VI TRI 0xFD  [chay tu THE SD]
#
# Chep thanh /sdcard/main.py, cam the, cap nguon. KHONG can IDE.
#   Tien trinh hien len LCD, ket qua ghi ra /sdcard/kq_vi_tri.txt
#
# ==========================================================
#  MUC DICH
# ==========================================================
# Nguoi dung muon "quay MOT LAN den noi roi chinh nho", thay vi bo tung nac
# nhu hien nay. Do chinh la che do VI TRI: ra lenh "di dung N xung roi TU
# DUNG", driver tu sinh doc gia toc/giam toc ben trong.
#
# Va tham so ACC cua driver CHI co tac dung voi lenh vi tri - da do thuc te
# 10/09: bat ACC 538 khong lam doi gi o che do toc do 0xF6 (quang duong troi
# 16.0 -> 15.7 px/nac, khong doi).
#
# Nhung 0xFD CHUA TUNG CHAY tren phan cung nay. Bai 13 chet vi loi
# parity=None truoc khi kip gui lenh nao.
#
# ==========================================================
#  DINH DANG KHUNG - DA XAC NHAN, KHONG PHAI DOAN
# ==========================================================
#   [addr][FD][dir<<7 | speed][xung 4 byte BE][checksum]   = 8 byte
#
# Doi chieu vi du chinh thuc trong manual (muc 6.4):
#   E0 FD 02 00 00 0C 80 6B
#   -> addr E0, chieu 0, toc do 2, 3200 xung, checksum 6B (tinh lai KHOP)
#
# ==========================================================
#  RUI RO PHAI DE PHONG
# ==========================================================
# Bai 14 da chung minh: lenh doc encoder tra ve khung 8 byte, khung do DOI
# NGUOC tren bus chung, driver nghe lai chinh minh, tuong la lenh gui cho
# no -> lech pha -> PAN quay mat kiem soat.
#
# KHONG BIET 0xFD tra ve khung dai bao nhieu. Neu dai thi rui ro y het.
# Nen bai nay:
#   1. CHI dung PAN (680 do, chay lac cung khong sao). TILT chi nhan F6-0.
#   2. Buoc nho: 1000 xung = 28 do truc motor = ~4.5 do goc that.
#   3. Sau MOI lenh, gui F6-toc-do-0 cho ca hai truc de huy bo.
#   4. Nghi 3 giay giua cac buoc, co dem so tren man de kip tat nguon.
#   5. Chi 6 lenh: 3 thuan + 3 nguoc -> ve dung cho cu.
#   6. GHI LAI DO DAI RX - do la thu quyet dinh co dung duoc 0xFD hay khong.
#
# ==========================================================
#  CAN QUAN SAT
# ==========================================================
#   * Motor co quay dung mot doan roi TU DUNG khong (hay chay tiep)?
#   * Chuyen dong co MUOT co doc gia toc khong, hay giat cuc nhu bay gio?
#     -> day la cau tra loi cho "ACC co tac dung voi lenh vi tri khong"
#   * Sau 3 thuan + 3 nguoc co ve DUNG cho danh dau khong?
#   * Co truc nao quay ngoai y muon khong?

import time, sys
from machine import UART, FPIOA

LOG = "/sdcard/kq_vi_tri.txt"

UART_ID, TX_PIN, RX_PIN, BAUD = 2, 11, 12, 115200
ADDR_PAN  = 0xE1        # 680 do - chi thu nghiem tren truc nay
ADDR_TILT = 0xE2        # chi nhan F6-toc-do-0

CMD_ENABLE = 0xF3
CMD_SPEED  = 0xF6       # lenh DA kiem chung 500+ giay chay that
CMD_MOVE   = 0xFD       # lenh DANG kiem chung

MSTEP = 64
XUNG_VONG = MSTEP * 200         # 12800 xung / vong truc motor
XUNG = 1000                     # 1000 xung = 28.1 do truc motor
NAC  = 6
SO_BUOC = 3                     # 3 thuan roi 3 nguoc -> ve cho cu
NGHI = 3.0
CHO_XEM = 12

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


# Mo UART va dung ca hai truc TRUOC man hinh.
# parity PHAI la UART.PARITY_NONE (hang so int) - dat parity=None se nem
# TypeError va script chet truoc khi kip lam gi (da mat mot buoi vi loi nay).
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


def man_chu(dong, mau=(255, 255, 255)):
    try:
        img = image.Image(W, H, image.RGB888)
        img.clear()
        img.draw_rectangle(0, 0, W, H, color=(0, 0, 40), fill=True)
        y = 16
        for i, d in enumerate(dong):
            img.draw_string_advanced(14, y, 28 if i == 0 else 22, d,
                                     color=(255, 220, 0) if i == 0 else mau)
            y += 38 if i == 0 else 29
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


def di_xung(chieu, xung, nac):
    """Gui 0xFD. Tra ve (bytes RX, giay cho)."""
    val = ((1 if chieu else 0) << 7) | (nac & 0x7F)
    p = int(xung) & 0xFFFFFFFF
    fr = khung(ADDR_PAN, CMD_MOVE, val,
               (p >> 24) & 0xFF, (p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF)
    try:
        while uart.any():
            uart.read()
    except Exception:
        pass
    t0 = time.ticks_ms()
    uart.write(fr)
    time.sleep_ms(600)
    rx = b""
    try:
        rx = uart.read() or b""
    except Exception:
        pass
    ghi("   TX (%d byte): %s" % (len(fr), " ".join("%02X" % b for b in fr)))
    ghi("   RX (%d byte): %s"
        % (len(rx), " ".join("%02X" % b for b in rx) if rx else "(KHONG CO)"))
    return rx, time.ticks_diff(time.ticks_ms(), t0) / 1000.0


try:
    logf = open(LOG, "w")
except Exception as e:
    print("Khong mo duoc log:", e)

so_gui = 0
so_tra_loi = 0
do_dai = []

try:
    if uart is None:
        raise RuntimeError("UART khong mo duoc")

    Display.init(Display.ST7701, width=W, height=H, to_ide=False)
    MediaManager.init()

    rpm = NAC * 30000.0 / (MSTEP * 200)
    xung_giay = rpm / 60 * XUNG_VONG
    ghi("=" * 56)
    ghi("KIEM CHUNG LENH VI TRI 0xFD - CHI TREN PAN (0x%02X)" % ADDR_PAN)
    ghi("=" * 56)
    ghi("Khung: [addr][FD][dir<<7|speed][xung 4 byte BE][checksum] = 8 byte")
    ghi("Da doi chieu vi du manual E0 FD 02 00 00 0C 80 6B -> checksum KHOP")
    ghi("")
    ghi("Moi buoc %d xung = %.1f do truc motor (~%.1f do goc that o ti so 6.3)"
        % (XUNG, 360.0 * XUNG / XUNG_VONG, 360.0 * XUNG / XUNG_VONG / 6.3))
    ghi("Toc do nac %d = %.2f RPM = %.0f xung/giay -> du kien %.2f giay/buoc"
        % (NAC, rpm, xung_giay, XUNG / xung_giay))
    ghi("%d buoc THUAN roi %d buoc NGUOC -> ve dung cho cu" % (SO_BUOC, SO_BUOC))
    ghi("TILT khong nhan lenh nao ngoai F6-toc-do-0.")
    ghi("")

    for t in range(CHO_XEM, 0, -1):
        man_chu(["KIEM CHUNG LENH VI TRI 0xFD",
                 "",
                 "DANH DAU vi tri PAN bay gio.",
                 "",
                 "Moi buoc ~%.0f do truc motor." % (360.0 * XUNG / XUNG_VONG),
                 "CHI PAN quay. TILT dung yen.",
                 "",
                 "Thay truc nao quay bat thuong",
                 "-> TAT NGUON NGAY.",
                 "",
                 "Bat dau sau %d giay..." % t])
        time.sleep(1)

    for chieu, ten_chieu in ((0, "THUAN"), (1, "NGUOC")):
        ghi("")
        ghi("#" * 56)
        ghi("# %d buoc chieu %s" % (SO_BUOC, ten_chieu))
        ghi("#" * 56)
        for i in range(SO_BUOC):
            man_chu(["LENH VI TRI - %s" % ten_chieu,
                     "",
                     "Buoc %d / %d   (%d xung)" % (i + 1, SO_BUOC, XUNG),
                     "",
                     "NHIN TRUC PAN:",
                     "  co TU DUNG sau moi buoc?",
                     "  chuyen dong co MUOT khong",
                     "  hay giat cuc?",
                     "",
                     "TAT NGUON neu thay bat thuong."],
                    mau=(0, 255, 120))
            ghi("")
            ghi("[%s buoc %d]" % (ten_chieu, i + 1))
            rx, _ = di_xung(chieu, XUNG, NAC)
            so_gui += 1
            if rx:
                so_tra_loi += 1
                do_dai.append(len(rx))
            # HUY BO moi chuyen dong ngoai y muon
            dung_het()
            ghi("   -> da gui F6-toc-do-0 cho ca 2 truc")
            time.sleep(NGHI)

    ghi("")
    ghi("=" * 56)
    ghi("TONG KET: %d/%d lenh 0xFD co phan hoi" % (so_tra_loi, so_gui))
    if do_dai:
        ghi("Do dai RX: %s" % sorted(set(do_dai)))
        if max(do_dai) <= 4:
            ghi("  -> RX NGAN (<=4 byte), giong lenh F6 da chay 500+ giay an toan.")
            ghi("     Dung 0xFD trong vong bam duoc.")
        else:
            ghi("  -> RX DAI (%d byte). RUI RO doi bus giong lenh doc encoder:" % max(do_dai))
            ghi("     driver nghe lai phan hoi cua chinh no -> lech pha -> chay loan.")
            ghi("     CAN NHAC KY truoc khi dung trong vong bam.")
    else:
        ghi("Khong co phan hoi nao -> 0xFD khong sinh khung tra ve.")
        ghi("  -> AN TOAN nhat cho bus chung. Dung duoc.")
    ghi("=" * 56)
    ghi("Ba cau can tra loi bang MAT:")
    ghi("  1. Motor co TU DUNG sau moi buoc khong?")
    ghi("  2. Chuyen dong MUOT (co doc gia toc) hay GIAT CUC?")
    ghi("  3. Sau 3 thuan + 3 nguoc co ve DUNG cho danh dau khong?")

    if logf:
        logf.close()
        logf = None

    while True:
        man_chu(["XONG - %d/%d lenh co phan hoi" % (so_tra_loi, so_gui),
                 "",
                 "Do dai RX: %s" % (sorted(set(do_dai)) if do_dai else "khong co"),
                 "",
                 "Ket qua: /sdcard/kq_vi_tri.txt",
                 "",
                 "1. Co TU DUNG moi buoc?",
                 "2. MUOT hay GIAT CUC?",
                 "3. Co ve DUNG cho danh dau?",
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
        man_chu(["LOI - xem kq_vi_tri.txt", "", str(e)], mau=(255, 80, 80))
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
