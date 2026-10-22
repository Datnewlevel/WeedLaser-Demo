# TEST 9 - QUET UART: tim driver dang o baud nao, dia chi nao
#
# PASTE THANG VAO CANMV IDE - khong import gi tu the SD.
#
# Chay 2 phan:
#   PHAN A - loopback: noi tat IO11 <-> IO12 bang day jumper.
#            Xac nhan UART cua K230 hoat dong, TRUOC khi do loi cho driver.
#   PHAN B - quet: thu tat ca baud x tat ca dia chi 0xE0..0xE9.
#            Khong can biet truoc driver dang cau hinh gi.
#
# DOI CHE DO o bien MODE ben duoi.

MODE = "scan"          # <<< "loopback" hoac "scan"

import time
from machine import UART, FPIOA

TX_PIN, RX_PIN = 11, 12
BAUDS = [115200, 38400, 57600, 25000, 19200, 9600]
ADDRS = [0xE0, 0xE1, 0xE2, 0xE3, 0xE4]

fpioa = FPIOA()
fpioa.set_function(TX_PIN, FPIOA.UART2_TXD)
fpioa.set_function(RX_PIN, FPIOA.UART2_RXD)


def open_uart(baud):
    return UART(UART.UART2, baudrate=baud, bits=UART.EIGHTBITS,
                parity=UART.PARITY_NONE, stop=UART.STOPBITS_ONE)


def hexs(b):
    return " ".join("%02x" % x for x in b) if b else "(rong)"


# =====================================================
if MODE == "loopback":
    print("=" * 52)
    print("PHAN A - LOOPBACK")
    print("Noi tat IO11 <-> IO12 bang 1 day jumper roi chay lai.")
    print("=" * 52)
    for baud in (115200, 38400):
        u = open_uart(baud)
        time.sleep_ms(50)
        try:
            u.read()                       # xoa bo dem
        except Exception:
            pass
        payload = bytes([0xE1, 0x3E, 0x1F])
        u.write(payload)
        time.sleep_ms(100)
        got = None
        try:
            got = u.read()
        except Exception:
            pass
        ok = got is not None and bytes(got) == payload
        print("  baud %-7d gui %s  nhan %s  -> %s"
              % (baud, hexs(payload), hexs(got), "PASS" if ok else "FAIL"))
        u.deinit()
        time.sleep_ms(100)
    print()
    print("PASS -> UART cua K230 tot, loi nam o driver/day noi driver.")
    print("FAIL -> chua noi jumper, hoac sai chan/FPIOA.")

# =====================================================
else:
    print("=" * 52)
    print("PHAN B - QUET BAUD x DIA CHI")
    print("Noi day thang toi driver (KHONG jumper loopback).")
    print("=" * 52)
    found = []
    for baud in BAUDS:
        u = open_uart(baud)
        time.sleep_ms(80)
        for addr in ADDRS:
            try:
                u.read()
            except Exception:
                pass
            # lenh 0x3E = doc trang thai bao ve, khung ngan, an toan
            frame = [addr, 0x3E]
            frame.append(sum(frame) & 0xFF)
            u.write(bytes(frame))
            time.sleep_ms(60)
            r = None
            try:
                r = u.read()
            except Exception:
                pass
            if r and len(r) >= 2 and r[0] == addr:
                print("  *** TIM THAY: baud %d, dia chi 0x%02X  <- %s"
                      % (baud, addr, hexs(r)))
                found.append((baud, addr))
            elif r:
                print("      baud %-7d addr 0x%02X  co du lieu la: %s"
                      % (baud, addr, hexs(r)))
        u.deinit()
        time.sleep_ms(120)
        print("  -- xong baud %d" % baud)

    print()
    print("=" * 52)
    if found:
        print("KET QUA:")
        for baud, addr in found:
            print("   driver o baud %d, dia chi 0x%02X" % (baud, addr))
        print()
        print("Sua BAUD/ADDR trong mks_servo.py cho khop.")
    else:
        print("KHONG THAY DRIVER NAO o bat ky baud/dia chi nao.")
        print()
        print("Kiem tra theo thu tu:")
        print("  1. Chay lai file nay voi MODE = 'loopback' (noi jumper IO11-IO12)")
        print("     -> loai tru loi phia K230 truoc")
        print("  2. Driver co dien 12V khong (man OLED sang khong)")
        print("  3. GND chung giua K230 va driver")
        print("  4. TX2(IO11) -> RX driver, RX2(IO12) -> TX driver (CHEO nhau)")
        print("  5. Menu OLED: Mode = CR_UART")
    print("=" * 52)
