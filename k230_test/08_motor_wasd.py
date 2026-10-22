# TEST 8 - Dieu khien 2 motor bang phim W/A/S/D tu CanMV IDE
#
# CHUA CO CAMERA, CHUA CO LASER - chi motor. Muc dich: cam nhan truc tiep
# huong quay, toc do, do tre truoc khi ghep vao vong bam muc tieu.
#
# AN TOAN:
#   - Motor de ROI hoac cum pan/tilt da lap nhung LASER THAO RA
#   - Da do dien ap IO cua K230 truoc khi noi vao driver
#   - Tro noi tiep 220 ohm tren TX va RX
#
# PHIM:
#   A / D   quay PAN  trai / phai
#   W / S   quay TILT len / xuong
#   SPACE   dung ca 2 truc ngay
#   + / -   tang / giam toc do
#   H       ve giua (chi dung, K230 khong biet vi tri tuyet doi)
#   Q       thoat
#
# GIU PHIM de quay lien tuc: terminal tu lap lai ky tu khi giu phim,
# moi ky tu lam moi bo dem. Tha phim -> het ky tu -> tu dung sau HOLD_TIMEOUT.
# Day dung co che ma tracking.py tren Pi dung voi cv2.waitKey().

import sys, time
import select

from mks_servo import (MksServoBus, ADDR_PAN, ADDR_TILT,
                       MAX_SPEED_PAN, MAX_SPEED_TILT)

HOLD_TIMEOUT_MS = 250       # tha phim bao lau thi dung
STATUS_EVERY_MS = 500       # chu ky in trang thai


def make_reader():
    """Tra ve ham doc 1 ky tu khong chan, hoac None neu khong ho tro."""
    try:
        poller = select.poll()
        poller.register(sys.stdin, select.POLLIN)

        def read_key():
            if poller.poll(0):
                try:
                    return sys.stdin.read(1)
                except Exception:
                    return None
            return None

        return read_key
    except Exception:
        return None


bus = None
try:
    read_key = make_reader()
    if read_key is None:
        print("!" * 56)
        print("IDE/firmware nay KHONG doc duoc phim tu terminal.")
        print("Dung 07_motor_k230_test.py (chay tu dong) thay the,")
        print("hoac noi 1 module USB-serial vao UART1 de nhan phim.")
        print("!" * 56)
        raise SystemExit

    bus = MksServoBus(read_reply=True)

    print("=" * 56)
    print("  DIEU KHIEN MOTOR BANG PHIM")
    print("=" * 56)
    print("  A/D = PAN trai/phai   |  W/S = TILT len/xuong")
    print("  SPACE = dung ngay     |  +/- = doi toc do")
    print("  Q = thoat")
    print("=" * 56)

    # Kiem tra 2 driver truoc khi cho phep dieu khien
    for addr, ten in ((ADDR_PAN, "PAN  (E1)"), (ADDR_TILT, "TILT (E2)")):
        r = bus.read_protection(addr)
        if r is None or len(r) < 2:
            print("!!! %s KHONG TRA LOI - kiem tra dia chi/baud/day truoc" % ten)
        else:
            if r[1] == 1:
                print("--- %s dang bi khoa bao ve -> giai tru" % ten)
                bus.release_protection(addr)
            print("--- %s san sang" % ten)
        time.sleep_ms(150)

    bus.enable_all(True)
    print("--- Da enable ca 2 truc. Bat dau dieu khien.\n")

    speed_pan = MAX_SPEED_PAN
    speed_tilt = MAX_SPEED_TILT

    last_key_ms = {"a": 0, "d": 0, "w": 0, "s": 0}
    pan_state = (0, 0)          # (chieu, toc do) dang gui cho PAN
    tilt_state = (0, 0)
    last_status_ms = 0

    while True:
        now = time.ticks_ms()

        # ---- doc phim ----
        ch = read_key()
        if ch:
            c = ch.lower()
            if c == "q":
                print("\n>>> Thoat.")
                break
            elif c == " ":
                bus.stop_all()
                pan_state = (0, 0)
                tilt_state = (0, 0)
                last_key_ms = {"a": 0, "d": 0, "w": 0, "s": 0}
                print(">>> DUNG NGAY")
            elif c == "h":
                bus.stop_all()
                pan_state = (0, 0)
                tilt_state = (0, 0)
                print(">>> Dung (K230 khong biet vi tri tuyet doi nen chi dung,"
                      " khong ve giua duoc)")
            elif c in ("+", "="):
                speed_pan = min(127, speed_pan + 1)
                speed_tilt = min(127, speed_tilt + 1)
                print(">>> Toc do: PAN %d | TILT %d" % (speed_pan, speed_tilt))
            elif c in ("-", "_"):
                speed_pan = max(1, speed_pan - 1)
                speed_tilt = max(1, speed_tilt - 1)
                print(">>> Toc do: PAN %d | TILT %d" % (speed_pan, speed_tilt))
            elif c in last_key_ms:
                last_key_ms[c] = now

        # ---- quyet dinh trang thai tu bo dem phim ----
        def active(k):
            t = last_key_ms[k]
            return t and time.ticks_diff(now, t) < HOLD_TIMEOUT_MS

        if active("a"):
            new_pan = (1, speed_pan)
        elif active("d"):
            new_pan = (0, speed_pan)
        else:
            new_pan = (0, 0)

        if active("w"):
            new_tilt = (0, speed_tilt)
        elif active("s"):
            new_tilt = (1, speed_tilt)
        else:
            new_tilt = (0, 0)

        # ---- chi gui khi co thay doi ----
        if new_pan != pan_state:
            bus.set_speed(ADDR_PAN, new_pan[0], new_pan[1])
            pan_state = new_pan
            time.sleep_ms(15)          # tach 2 lenh tren bus chung
        if new_tilt != tilt_state:
            bus.set_speed(ADDR_TILT, new_tilt[0], new_tilt[1])
            tilt_state = new_tilt

        # ---- in trang thai dinh ky ----
        if time.ticks_diff(now, last_status_ms) > STATUS_EVERY_MS:
            last_status_ms = now
            if pan_state[1] or tilt_state[1]:
                print("PAN %s%d | TILT %s%d" % (
                    "<" if pan_state[0] else ">", pan_state[1],
                    "v" if tilt_state[0] else "^", tilt_state[1]))

        time.sleep_ms(10)

except KeyboardInterrupt:
    print("\nCtrl-C")
except SystemExit:
    pass
except BaseException as e:
    print(">>> LOI:")
    sys.print_exception(e)
finally:
    # BAT BUOC dung motor trong moi tinh huong thoat
    if bus is not None:
        bus.close()
    print("Da dung motor va dong UART.")
