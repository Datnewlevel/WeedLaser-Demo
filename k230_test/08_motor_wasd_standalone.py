# TEST 8 (BAN GOP 1 FILE) - Dieu khien 2 motor bang phim W/A/S/D
#
# Ban nay KHONG can import mks_servo.py -> paste thang vao CanMV IDE la chay.
# (Ban tach module o 08_motor_wasd.py, dung khi da copy mks_servo.py len the SD.)
#
# AN TOAN:
#   - Motor de ROI hoac cum pan/tilt da lap nhung LASER THAO RA
#   - Da do dien ap IO cua K230 truoc khi noi vao driver
#   - Tro noi tiep 220 ohm tren TX va RX
#
# PHIM:  A/D = PAN trai/phai | W/S = TILT len/xuong
#        SPACE = dung ngay   | +/- = doi toc do  | Q = thoat

import sys, time, select
from machine import UART, FPIOA

# ==========================================================
# CAU HINH
# ==========================================================
TX_PIN, RX_PIN = 11, 12
BAUD = 115200

ADDR_PAN, ADDR_TILT = 0xE1, 0xE2
MAX_SPEED_PAN, MAX_SPEED_TILT = 5, 3

INTER_CMD_MS = 15          # tach 2 lenh tren bus chung
HOLD_TIMEOUT_MS = 250      # tha phim bao lau thi dung
STATUS_EVERY_MS = 500

CMD_RELEASE_PROT = 0x3D
CMD_READ_PROT = 0x3E
CMD_ENABLE = 0xF3
CMD_SPEED = 0xF6
CMD_STOP = 0xF7

# ==========================================================
# GIAO THUC MKS SERVO42C
# ==========================================================

fpioa = FPIOA()
fpioa.set_function(TX_PIN, FPIOA.UART2_TXD)
fpioa.set_function(RX_PIN, FPIOA.UART2_RXD)
uart = UART(UART.UART2, baudrate=BAUD, bits=UART.EIGHTBITS,
            parity=UART.PARITY_NONE, stop=UART.STOPBITS_ONE)


def send(addr, *data):
    """Khung = [addr][function][data...][checksum], checksum = tong & 0xFF.
    THIEU checksum -> driver im lang hoan toan (no van cho byte con thieu)."""
    frame = [addr] + list(data)
    frame.append(sum(frame) & 0xFF)
    uart.write(bytes(frame))
    time.sleep_ms(5)
    try:
        return uart.read()
    except Exception:
        return None


def set_speed(addr, direction, speed):
    speed = max(0, min(127, int(speed)))
    val = ((1 if direction else 0) << 7) | speed
    return send(addr, CMD_SPEED, val)


def stop_all():
    try:
        send(ADDR_PAN, CMD_STOP)
        time.sleep_ms(INTER_CMD_MS)
        send(ADDR_TILT, CMD_STOP)
    except Exception:
        pass


# ==========================================================
# DOC PHIM KHONG CHAN
# ==========================================================

def make_reader():
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


# ==========================================================
# CHUONG TRINH CHINH
# ==========================================================

try:
    read_key = make_reader()
    if read_key is None:
        print("!" * 56)
        print("IDE/firmware nay KHONG doc duoc phim tu terminal.")
        print("Dung 07_motor_k230_test.py (chay tu dong) thay the.")
        print("!" * 56)
        raise SystemExit

    print("=" * 56)
    print("  DIEU KHIEN MOTOR BANG PHIM")
    print("  A/D = PAN trai/phai  |  W/S = TILT len/xuong")
    print("  SPACE = dung ngay    |  +/- = toc do  |  Q = thoat")
    print("=" * 56)

    for addr, ten in ((ADDR_PAN, "PAN  (E1)"), (ADDR_TILT, "TILT (E2)")):
        r = send(addr, CMD_READ_PROT)
        if r is None or len(r) < 2:
            print("!!! %s KHONG TRA LOI - kiem tra dia chi/baud/day" % ten)
        else:
            if r[1] == 1:
                print("--- %s bi khoa bao ve -> giai tru" % ten)
                send(addr, CMD_RELEASE_PROT)
            print("--- %s san sang" % ten)
        time.sleep_ms(150)

    send(ADDR_PAN, CMD_ENABLE, 0x01)
    time.sleep_ms(INTER_CMD_MS)
    send(ADDR_TILT, CMD_ENABLE, 0x01)
    print("--- Da enable ca 2 truc.\n")

    speed_pan, speed_tilt = MAX_SPEED_PAN, MAX_SPEED_TILT
    last_key = {"a": 0, "d": 0, "w": 0, "s": 0}
    pan_state = (0, 0)
    tilt_state = (0, 0)
    last_status = 0

    while True:
        now = time.ticks_ms()

        ch = read_key()
        if ch:
            c = ch.lower()
            if c == "q":
                print("\n>>> Thoat.")
                break
            elif c == " ":
                stop_all()
                pan_state = tilt_state = (0, 0)
                last_key = {"a": 0, "d": 0, "w": 0, "s": 0}
                print(">>> DUNG NGAY")
            elif c in ("+", "="):
                speed_pan = min(127, speed_pan + 1)
                speed_tilt = min(127, speed_tilt + 1)
                print(">>> Toc do: PAN %d | TILT %d" % (speed_pan, speed_tilt))
            elif c in ("-", "_"):
                speed_pan = max(1, speed_pan - 1)
                speed_tilt = max(1, speed_tilt - 1)
                print(">>> Toc do: PAN %d | TILT %d" % (speed_pan, speed_tilt))
            elif c in last_key:
                last_key[c] = now

        def active(k):
            t = last_key[k]
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

        if new_pan != pan_state:
            set_speed(ADDR_PAN, new_pan[0], new_pan[1])
            pan_state = new_pan
            time.sleep_ms(INTER_CMD_MS)
        if new_tilt != tilt_state:
            set_speed(ADDR_TILT, new_tilt[0], new_tilt[1])
            tilt_state = new_tilt

        if time.ticks_diff(now, last_status) > STATUS_EVERY_MS:
            last_status = now
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
    stop_all()
    time.sleep_ms(50)
    try:
        uart.deinit()
    except Exception:
        pass
    print("Da dung motor va dong UART.")
