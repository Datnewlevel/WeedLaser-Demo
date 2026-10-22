# TEST 13 - KIEM CHUNG LENH 0xFD (quay N xung roi TU DUNG)  [ban CHAY TU THE SD]
#
# Chep thanh /sdcard/main.py, cam the vao K230, cap nguon. KHONG can IDE.
#   - Tien trinh hien LEN MAN HINH LCD (vi khong doc duoc console).
#   - Ket qua TX/RX ghi ra /sdcard/kq_lenh_xung.txt
#
# LY DO CAN BAI NAY
#   Vong bam dang dung 0xF6 (toc do khong doi) = bang-bang, KHONG CO PHANH.
#   13 FPS -> giua 2 khung hinh co 77ms MU ma motor van chay. O toc do 1
#   (~9.4 RPM) thi 77ms = ~4.3 do. Neu truc gan truc tiep, 4.3 do ~ 50px
#   tren anh, trong khi vung chet chi +-30px.
#   => Mot khung hinh du de NHAY XUYEN QUA vung chet, nen no "cui xuong
#      roi vuot qua mat vat the".
#   0xFD ra lenh "di dung N xung roi TU DUNG" -> het chay mu, het vuot.
#   Nhung 0xFD moi giai ma tu tai lieu, CHUA TUNG CHAY THAT. Xac minh truoc.
#
# AN TOAN CO KHI - da tinh cho cum DA LAP RAP
#   Buoc test co tinh NHO: PAN di xa nhat ~45 do, TILT ~20 do, roi quay
#   nguoc dung bay nhieu de ve cho cu. Neu cum cua ban con chat hon the,
#   TAT NGUON NGAY khi thay no tien gan diem cham.
#   Chan laser IO43 bi ep xuong muc thap ngay dong dau.

import time, sys

# ---- AN TOAN: ep chan laser xuong muc thap NGAY ----
try:
    from machine import FPIOA as _FP, Pin as _P
    _f0 = _FP()
    _f0.set_function(43, getattr(_FP, "GPIO43"))
    _P(43, _P.OUT).off()
except Exception as _e:
    print("!!! KHONG ep duoc chan laser:", _e)

from machine import UART, FPIOA
from media.display import *
from media.media import *
import image

LOG = "/sdcard/kq_lenh_xung.txt"

UART_ID, TX_PIN, RX_PIN, BAUD = 2, 11, 12, 115200
ADDR_PAN  = 0xE1        # trai/phai
ADDR_TILT = 0xE2        # len/xuong
XUNG_MOI_VONG = 3200    # Mstep 16 -> 3200
TOC_DO = 3

# Buoc test - GIU NHO vi cum da lap rap
BUOC_PAN,  LAN_PAN  = 50, 8     # 8 x 50 = 400 xung ~ 45 do
BUOC_TILT, LAN_TILT = 30, 6     # 6 x 30 = 180 xung ~ 20 do
BUOC_NHO = 20                   # ~2.25 do - co buoc luc bam sat tam

CMD_MOVE = 0xFD
CMD_STOP = 0xF7
CHO_XEM = 25            # giay: cho nguoi dung danh dau truc truoc khi chay

logf = None
uart = None
W, H = 640, 480


def ghi(s):
    print(s)
    if logf:
        try:
            logf.write(s + "\n")
            logf.flush()
        except Exception:
            pass


def man_hinh(dong, mau=(255, 255, 255)):
    """Ve tien trinh len LCD. dong = list cac chuoi. Dong 0 la tieu de."""
    try:
        img = image.Image(W, H, image.RGB565)
        img.clear()
        img.draw_rectangle(0, 0, W, H, color=(0, 0, 40), fill=True)
        y = 24
        for i, d in enumerate(dong):
            img.draw_string_advanced(16, y, 30 if i == 0 else 24, d,
                                     color=(255, 220, 0) if i == 0 else mau)
            y += 40 if i == 0 else 32
        Display.show_image(img)
        img = None
    except Exception:
        pass


def build(addr, *data):
    fr = [addr] + list(data)
    fr.append(sum(fr) & 0xFF)
    return bytes(fr)


def gui(addr, *data, cho_ms=400):
    fr = build(addr, *data)
    while uart.any():
        uart.read()
    uart.write(fr)
    time.sleep_ms(cho_ms)
    rx = uart.read() or b""
    ghi("   TX: %s   RX: %s" % (
        " ".join("%02X" % b for b in fr),
        " ".join("%02X" % b for b in rx) if rx else "(KHONG CO)"))
    return rx


def quay_xung(addr, chieu, toc_do, xung):
    val = ((1 if chieu else 0) << 7) | (toc_do & 0x7F)
    p = int(xung) & 0xFFFFFFFF
    return gui(addr, CMD_MOVE, val,
               (p >> 24) & 0xFF, (p >> 16) & 0xFF,
               (p >> 8) & 0xFF, p & 0xFF)


try:
    logf = open(LOG, "w")
except Exception as e:
    print("Khong mo duoc log:", e)

so_rx = [0, 0]      # [tong lenh gui, so lenh co phan hoi]

try:
    Display.init(Display.ST7701, width=W, height=H, to_ide=False)
    MediaManager.init()

    fp = FPIOA()
    fp.set_function(TX_PIN, FPIOA.UART2_TXD)
    fp.set_function(RX_PIN, FPIOA.UART2_RXD)
    uart = UART(UART_ID, baudrate=BAUD, bits=UART.EIGHTBITS,
                parity=UART.PARITY_NONE, stop=UART.STOPBITS_ONE)

    ghi("=" * 52)
    ghi("KIEM CHUNG 0xFD - quay N xung roi TU DUNG")
    ghi("Toc do %d, %d xung = 1 vong" % (TOC_DO, XUNG_MOI_VONG))
    ghi("PAN : %d x %d xung   TILT: %d x %d xung"
        % (LAN_PAN, BUOC_PAN, LAN_TILT, BUOC_TILT))
    ghi("=" * 52)

    for t in range(CHO_XEM, 0, -1):
        man_hinh(["TEST LENH XUNG 0xFD",
                  "",
                  "DANH DAU 2 TRUC BANG BUT",
                  "de sau con so sanh vi tri.",
                  "",
                  "Bat dau sau %d giay..." % t,
                  "",
                  "Cum se quay PAN ~45do, TILT ~20do",
                  "roi quay nguoc ve cho cu.",
                  "Sap cham co khi -> TAT NGUON."])
        time.sleep(1)

    for ten, addr, buoc, lan in (("PAN", ADDR_PAN, BUOC_PAN, LAN_PAN),
                                 ("TILT", ADDR_TILT, BUOC_TILT, LAN_TILT)):
        ghi("")
        ghi("#" * 52)
        ghi("# TRUC %s   dia chi 0x%02X" % (ten, addr))
        ghi("#" * 52)

        for chieu, ten_chieu in ((0, "THUAN"), (1, "NGUOC")):
            ghi("")
            ghi(">>> %s: %d lan x %d xung, chieu %s" % (ten, lan, buoc, ten_chieu))
            for i in range(lan):
                man_hinh(["TRUC %s - %s" % (ten, ten_chieu),
                          "",
                          "Buoc %d / %d   (%d xung)" % (i + 1, lan, buoc),
                          "",
                          "NHIN TRUC MOTOR:",
                          "no co TU DUNG han sau",
                          "moi buoc khong?"])
                ghi("  buoc %d/%d:" % (i + 1, lan))
                rx = quay_xung(addr, chieu, TOC_DO, buoc)
                so_rx[0] += 1
                if rx:
                    so_rx[1] += 1
                time.sleep(2)       # de mat kip thay no DUNG HAN

        ghi("")
        ghi(">>> %s: buoc RAT NHO %d xung (~%.1f do)"
            % (ten, BUOC_NHO, 360.0 * BUOC_NHO / XUNG_MOI_VONG))
        for chieu, ten_chieu in ((0, "THUAN"), (1, "NGUOC")):
            for i in range(4):
                man_hinh(["TRUC %s - BUOC NHO" % ten,
                          "",
                          "%s  %d xung  (%d/4)" % (ten_chieu, BUOC_NHO, i + 1),
                          "",
                          "Co NHUC NHICH thay ro khong?",
                          "Hay dung im hoan toan?"])
                ghi("  %s nho %d/4:" % (ten_chieu, i + 1))
                rx = quay_xung(addr, chieu, TOC_DO, BUOC_NHO)
                so_rx[0] += 1
                if rx:
                    so_rx[1] += 1
                time.sleep(1)

        gui(addr, CMD_STOP, cho_ms=150)
        time.sleep(1)

    ghi("")
    ghi("=" * 52)
    ghi("TONG KET: %d/%d lenh co phan hoi tu driver" % (so_rx[1], so_rx[0]))
    ghi("=" * 52)
    ghi("Tra loi 3 cau:")
    ghi("  1. Motor co TU DUNG sau moi lenh khong (hay chay tiep)?")
    ghi("  2. Sau khi quay nguoc, co ve DUNG cho danh dau khong?")
    ghi("  3. Buoc %d xung co nhuc nhich thay ro khong?" % BUOC_NHO)

    if logf:
        logf.close()
        logf = None

    while True:
        man_hinh(["XONG - %d/%d lenh co phan hoi" % (so_rx[1], so_rx[0]),
                  "",
                  "Ket qua ghi vao the:",
                  "  /sdcard/kq_lenh_xung.txt",
                  "",
                  "1. Motor co TU DUNG moi lenh?",
                  "2. Quay nguoc co VE DUNG CHO?",
                  "3. Buoc %d xung co nhuc nhich?" % BUOC_NHO,
                  "",
                  "Tat nguon khi xem xong."],
                 mau=(0, 255, 120))
        time.sleep(2)

except KeyboardInterrupt:
    pass
except BaseException as e:
    ghi("LOI:")
    try:
        if logf:
            sys.print_exception(e, logf)
            logf.flush()
    except Exception:
        pass
    sys.print_exception(e)
    try:
        man_hinh(["LOI - xem kq_lenh_xung.txt", "", str(e)],
                 mau=(255, 80, 80))
        time.sleep(30)
    except Exception:
        pass
finally:
    if uart is not None:
        try:
            for a in (ADDR_PAN, ADDR_TILT):
                uart.write(build(a, CMD_STOP))
                time.sleep_ms(50)
        except Exception:
            pass
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
