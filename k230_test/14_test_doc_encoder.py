# TEST 14 - K230 CO DOC DUOC PHAN HOI TU DRIVER KHONG?   [chay tu THE SD]
#
# Chep thanh /sdcard/main.py, cam the, cap nguon. KHONG can IDE.
#   Tien trinh hien len LCD, ket qua ghi ra /sdcard/kq_encoder.txt
#
# ==========================================================
#  LICH SU - VI SAO BAN NAY RAT DE DAT
# ==========================================================
# Ban truoc lam TILT quay xuong cham cu. Da xac dinh duoc thoi diem:
#   - TILT chay SAU dem nguoc, DUNG LUC dang doc encoder
#   - Khong cam the (khong chay code) thi TILT nam yen
#   => CHINH LENH DOC (0x30 / 0x3E) lam motor quay.
#
# Co che (nhat ky du an da ghi tu hom go loi checksum):
#   "thieu byte != sai byte. Driver van DANG CHO byte cuoi nen chua coi la
#    khung hoan chinh -> lenh gui tiep theo bi nuot lam byte cuoi cua khung
#    cu -> lech pha vinh vien"
# Neu 0x30 can nhieu byte hon 3 byte ta gui (E1 30 11), driver treo cho,
# roi nuot byte cua khung sau -> sinh khung RAC -> rac do co the la lenh quay.
#
# Hai gia thuyet TRUOC DO cua toi DEU SAI, ghi lai de khong lap:
#   - "F7 buong mo-men"   -> sai, F7 bi nghi oan
#   - "thieu lenh Enable" -> sai, motor quay CHU DONG nghia la da co dong;
#                            driver co muc En trong menu, dat luon bat
#
# ==========================================================
#  NGUYEN TAC AN TOAN CUA BAN NAY
# ==========================================================
#   1. TUYET DOI KHONG gui lenh doc cho TILT. Truc do chi co 90 do.
#      TILT chi nhan F6-toc-do-0, la lenh DA CHAY THAT 529 giay.
#   2. Thu doc tren PAN thoi - PAN co 680 do, chay lac cung khong sao.
#   3. Sau MOI lan doc, gui ngay F6-toc-do-0 cho CA HAI truc de huy bo
#      moi chuyen dong ngoai y muon.
#   4. Chi doc 3 lan, moi lan cach nhau 3 giay, co dem so tren man hinh
#      de kip tat nguon.
#   5. KHONG quay motor de do gi ca. Bai nay tra loi DUNG MOT cau:
#      "gui lenh doc thi co byte nao quay ve khong, va co gay quay khong".

import time, sys
from machine import UART, FPIOA

LOG = "/sdcard/kq_encoder.txt"

UART_ID, TX_PIN, RX_PIN, BAUD = 2, 11, 12, 115200
ADDR_PAN  = 0xE1        # 680 do - duoc phep thu nghiem tren truc nay
ADDR_TILT = 0xE2        # CHI 90 do - KHONG BAO GIO gui lenh doc

CMD_ENABLE  = 0xF3
CMD_SPEED   = 0xF6      # lenh DUY NHAT da duoc kiem chung (529 giay chay that)
CMD_ENCODER = 0x30
CMD_PROT    = 0x3E

SO_LAN_DOC = 3
CHO_GIUA   = 3          # giay nghi giua 2 lan doc
CHO_XEM    = 12         # giay dem nguoc truoc khi bat dau

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


# ==========================================================
#  MO UART VA DUNG CA HAI TRUC - TRUOC MOI THU KHAC
# ==========================================================
# Mo truoc man hinh: neu man hinh hong thi motor van da duoc dung.
# parity PHAI la UART.PARITY_NONE (hang so int). Dat parity=None (None cua
# Python) -> TypeError: can't convert NoneType to int, va script chet TRUOC
# khi kip lam gi - da mat mot buoi vi loi nay.
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
    print("UART mo OK, da enable va dung ca 2 truc.")
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
        y = 20
        for i, d in enumerate(dong):
            img.draw_string_advanced(14, y, 28 if i == 0 else 22, d,
                                     color=(255, 220, 0) if i == 0 else mau)
            y += 38 if i == 0 else 30
        Display.show_image(img)
        img = None
    except Exception:
        pass


def dung_het():
    """F6 toc do 0 cho ca hai truc. Lenh nay da chay that 529 giay."""
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

so_hoi = 0
so_tra_loi = 0

try:
    if uart is None:
        raise RuntimeError("UART khong mo duoc")

    Display.init(Display.ST7701, width=W, height=H, to_ide=False)
    MediaManager.init()

    ghi("=" * 56)
    ghi("THU LENH DOC - CHI TREN TRUC PAN (0x%02X)" % ADDR_PAN)
    ghi("UART%d  TX IO%d  RX IO%d  %d baud" % (UART_ID, TX_PIN, RX_PIN, BAUD))
    ghi("TILT (0x%02X) KHONG nhan lenh doc nao." % ADDR_TILT)
    ghi("=" * 56)
    ghi("Da gui: F3 01 (enable) + F6 00 (dung) cho ca 2 truc.")

    for t in range(CHO_XEM, 0, -1):
        man_hinh(["THU LENH DOC ENCODER",
                  "",
                  "CHI thu tren truc PAN.",
                  "TILT khong nhan lenh doc nao.",
                  "",
                  "Khong quay motor de do.",
                  "Neu THAY BAT KY TRUC NAO QUAY",
                  "-> TAT NGUON NGAY.",
                  "",
                  "Bat dau sau %d giay..." % t])
        time.sleep(1)

    for lan in range(SO_LAN_DOC):
        for ten_lenh, ma in (("0x30 doc encoder", CMD_ENCODER),
                             ("0x3E trang thai bao ve", CMD_PROT)):
            man_hinh(["DANG THU: %s" % ten_lenh,
                      "",
                      "Lan %d / %d   truc PAN" % (lan + 1, SO_LAN_DOC),
                      "",
                      "NHIN CA HAI TRUC.",
                      "Co truc nao nhuc nhich khong?",
                      "",
                      "TAT NGUON neu thay quay."])
            fr = khung(ADDR_PAN, ma)
            try:
                while uart.any():
                    uart.read()
            except Exception:
                pass
            uart.write(fr)
            so_hoi += 1
            time.sleep_ms(300)
            rx = b""
            try:
                rx = uart.read() or b""
            except Exception:
                pass
            if rx:
                so_tra_loi += 1
            ghi("")
            ghi("[lan %d] %s" % (lan + 1, ten_lenh))
            ghi("   TX (%d byte): %s"
                % (len(fr), " ".join("%02X" % b for b in fr)))
            ghi("   RX (%d byte): %s"
                % (len(rx), " ".join("%02X" % b for b in rx) if rx else "(KHONG CO)"))

            # HUY BO moi chuyen dong ngoai y muon, ngay lap tuc
            dung_het()
            ghi("   -> da gui F6-toc-do-0 cho ca 2 truc")
            time.sleep(CHO_GIUA)

    ghi("")
    ghi("=" * 56)
    ghi("TONG KET: %d/%d lenh doc co phan hoi" % (so_tra_loi, so_hoi))
    ghi("=" * 56)
    if so_tra_loi == 0:
        ghi("KHONG co byte nao quay ve.")
        ghi("  -> duong RX driver -> K230 khong thong, HOAC")
        ghi("     0x30/0x3E khong phai lenh doc cua firmware nay.")
        ghi("  Motor van quay duoc vi do chi can chieu TX.")
        ghi("  => BO huong doc encoder. Dung Set 0 cua driver + cong don goc.")
    else:
        ghi("CO byte quay ve. Xem do dai RX:")
        ghi("  - dung 9 byte  -> khop gia thiet [addr][30][carry x4][value x2][ck]")
        ghi("  - do dai khac  -> dinh dang khac, PHAI giai ma lai truoc khi")
        ghi("    dung. Gui thieu byte la driver treo cho va lech pha.")

    if logf:
        logf.close()
        logf = None

    while True:
        man_hinh(["XONG - %d/%d lenh co phan hoi" % (so_tra_loi, so_hoi),
                  "",
                  "Ket qua ghi vao the:",
                  "  /sdcard/kq_encoder.txt",
                  "",
                  "Cau hoi can tra loi:",
                  "co truc nao QUAY trong luc thu?",
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
        man_hinh(["LOI - xem kq_encoder.txt", "", str(e)], mau=(255, 80, 80))
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
