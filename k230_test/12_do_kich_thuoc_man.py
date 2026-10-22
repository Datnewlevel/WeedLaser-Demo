# TEST 12 - DO KICH THUOC THAT CUA PANEL LCD  (ban CHAY TU THE SD)
#
# Chep file nay thanh /sdcard/main.py roi cam the vao K230, cap nguon.
# KHONG can CanMV IDE.
#
# Vi chay tu the nen lam duoc thu ma paste vao IDE khong lam duoc:
# GHI KET QUA RA FILE  ->  /sdcard/kq_do_man.txt
#
# Script lam 2 viec:
#
#  PHAN 1 - DO TU DONG
#    Thu init + show_image o nhieu kich thuoc khac nhau, ghi OK/FAIL tung
#    cai vao /sdcard/kq_do_man.txt (flush ngay sau moi dong, nen treo giua
#    chung van con log). Day moi la cach BIET CHAC panel rong bao nhieu,
#    thay vi doan. Da biet truoc: 800 se FAIL o show_image.
#
#  PHAN 2 - VE KHUNG 640x480 va giu nguyen tren man
#    Nen xanh duong, vien DO day 4px sat 4 canh, 2 duong cheo XANH LA,
#    va thuoc do vach trang moi 50px doc canh duoi + canh phai.
#
# DOC KET QUA tren MAN HINH THAT:
#   A. Du 4 canh vien do, 2 cheo cat nhau giua man, het dai trang
#      -> panel dung 640x480. Dai trang truoc day la do ANH WEBCAM khong
#         lap day khung, phai sua cho khac.
#   B. Chi thay 3 canh vien do, canh con lai la dai trang/den
#      -> panel that su to hon. Dem so vach thuoc trong phan dai trang
#         (moi vach 50px) roi bao lai.
#
# XONG ROI KHOI PHUC:  doi ten /sdcard/main_tracking.py  ->  main.py

import time, sys

# ---- AN TOAN: ep chan laser xuong muc THAP NGAY LAP TUC ----
# Da xac nhan bang thuc nghiem: chan tha noi = laser BAN. Bai test nay
# khong dung gi den laser, nen phai tu tay dua chan ve muc an toan thay
# vi trong cho mot minh dien tro keo xuong tren mach.
try:
    from machine import FPIOA, Pin
    _f = FPIOA()
    _f.set_function(43, getattr(FPIOA, "GPIO43"))
    Pin(43, Pin.OUT).off()
    print("Da ep chan laser IO43 xuong muc thap.")
except Exception as _e:
    print("!!! KHONG ep duoc chan laser:", _e)

LOG = "/sdcard/kq_do_man.txt"
CAC_KICH_THUOC = [
    (640, 480),
    (720, 480),
    (800, 480),
    (1024, 600),
]

logf = None


def ghi(s):
    print(s)
    if logf:
        try:
            logf.write(s + "\n")
            logf.flush()
        except Exception:
            pass


try:
    logf = open(LOG, "w")
except Exception as e:
    print("Khong mo duoc log:", e)

from media.display import *
from media.media import *
import image


def ve_khung(w, h):
    img = image.Image(w, h, image.RGB565)
    img.clear()
    img.draw_rectangle(0, 0, w, h, color=(0, 0, 200), fill=True)
    for i in range(4):
        img.draw_rectangle(i, i, w - 2 * i, h - 2 * i,
                           color=(255, 0, 0), fill=False)
    img.draw_line(0, 0, w - 1, h - 1, color=(0, 255, 0), thickness=3)
    img.draw_line(w - 1, 0, 0, h - 1, color=(0, 255, 0), thickness=3)
    # Thuoc do: vach trang moi 50px doc canh duoi va canh phai
    x = 0
    while x < w:
        img.draw_line(x, h - 20, x, h - 1, color=(255, 255, 255), thickness=2)
        x += 50
    y = 0
    while y < h:
        img.draw_line(w - 20, y, w - 1, y, color=(255, 255, 255), thickness=2)
        y += 50
    img.draw_string_advanced(12, 10, 28, "%dx%d" % (w, h), color=(255, 255, 0))
    img.draw_string_advanced(12, 46, 22, "GOC TREN TRAI", color=(255, 255, 0))
    img.draw_string_advanced(max(0, w - 210), h - 44, 22, "GOC DUOI PHAI",
                             color=(255, 255, 0))
    return img


ghi("=" * 46)
ghi("DO KICH THUOC PANEL - %s" % time.time())
ghi("=" * 46)

# ---------------- PHAN 1: do tu dong ----------------
ket_qua = []
for (w, h) in CAC_KICH_THUOC:
    ghi("")
    ghi(">>> Thu %dx%d" % (w, h))
    trang_thai = "?"
    try:
        Display.init(Display.ST7701, width=w, height=h, to_ide=False)
        MediaManager.init()
        ghi("    init      : OK")
        try:
            img = ve_khung(w, h)
            Display.show_image(img)
            ghi("    show_image: OK")
            trang_thai = "OK"
            time.sleep(2)          # de mat kip nhin
        except Exception as e:
            ghi("    show_image: FAIL -> %s" % e)
            trang_thai = "FAIL show_image"
        img = None
    except Exception as e:
        ghi("    init      : FAIL -> %s" % e)
        trang_thai = "FAIL init"

    ket_qua.append((w, h, trang_thai))
    try:
        Display.deinit()
    except Exception:
        pass
    time.sleep_ms(200)
    try:
        MediaManager.deinit()
    except Exception:
        pass
    time.sleep_ms(300)

ghi("")
ghi("=" * 46)
ghi("TONG KET")
for (w, h, t) in ket_qua:
    ghi("  %4dx%-4d : %s" % (w, h, t))
ghi("=" * 46)
ghi("Kich thuoc LON NHAT co trang thai OK chinh la panel that.")

# ---------------- PHAN 2: giu khung 640x480 tren man ----------------
ghi("")
ghi("Gio ve khung 640x480 va giu nguyen. Nhin MAN HINH THAT:")
ghi("  du 4 canh vien do  -> panel dung 640")
ghi("  thieu 1 canh       -> panel to hon, dem vach thuoc (50px/vach)")

try:
    Display.init(Display.ST7701, width=640, height=480, to_ide=False)
    MediaManager.init()
    img = ve_khung(640, 480)
    Display.show_image(img)
    ghi("Da ve. Tat nguon khi xem xong.")
    if logf:
        logf.close()
        logf = None
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
except BaseException as e:
    ghi("LOI phan 2:")
    try:
        if logf:
            sys.print_exception(e, logf)
            logf.flush()
    except Exception:
        pass
    sys.print_exception(e)
finally:
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
