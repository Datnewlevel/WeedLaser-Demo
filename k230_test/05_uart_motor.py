# TEST 5 - Quay thu 1 motor.
#
# !!! AN TOAN TRUOC KHI CHAY !!!
#   1. Motor de ROI, CHUA lap len co cau pan/tilt.
#   2. LASER THAO RA HOAN TOAN. Chua dung den o buoc nay.
#   3. Da noi GND chung giua K230 va nguon driver. Bat buoc.
#   4. Da DO mux dien ap IO cua board (1.8V hay 3.3V) truoc khi cam.
#   5. Chi cam 1 motor duy nhat o test nay.
#
# Truoc do vao menu OLED cua driver dat: che do UART, ID = 1, baudrate khop.

from machine import UART, FPIOA
import time

DRIVER = "ZDT"        # "ZDT" (Emm42 / truong dai dau) hoac "MKS" (SERVO42C)
ADDR   = 1            # ZDT: 1,2 ... | MKS: 0xE0, 0xE1 ...
BAUD   = 115200       # MKS mac dinh thuong 38400 -> sua cho khop menu OLED

TX_PIN, RX_PIN = 11, 12

fpioa = FPIOA()
fpioa.set_function(TX_PIN, FPIOA.UART2_TXD)
fpioa.set_function(RX_PIN, FPIOA.UART2_RXD)
uart = UART(UART.UART2, baudrate=BAUD,
            bits=UART.EIGHTBITS, parity=UART.PARITY_NONE, stop=UART.STOPBITS_ONE)


def speed_zdt(addr, direction, vel):
    """Emm42/ZDT: addr, 0xF6, dir, acc_hi, acc_lo, vel_hi, vel_lo, sync, 0x6B"""
    return bytes([addr, 0xF6, direction & 1, 0xFF, 0xFF,
                  (vel >> 8) & 0xFF, vel & 0xFF, 0x00, 0x6B])


def speed_mks(addr, direction, vel):
    """MKS SERVO42C: addr, 0xF6, (dir<<7 | speed 0-127), checksum.
    CHUA KIEM CHUNG - doi chieu manual firmware cua ban truoc khi tin."""
    vel = max(0, min(127, vel))
    b = ((direction & 1) << 7) | vel
    frame = [addr, 0xF6, b]
    frame.append(sum(frame) & 0xFF)
    return bytes(frame)


build = speed_zdt if DRIVER == "ZDT" else speed_mks


def send(direction, vel):
    f = build(ADDR, direction, vel)
    uart.write(f)
    print("TX", [hex(x) for x in f])


def stop():
    send(0, 0)


try:
    print(">>> Quay thuan 2s")
    send(0, 100 if DRIVER == "ZDT" else 30)
    time.sleep(2)

    print(">>> Dung 1s")
    stop()
    time.sleep(1)

    print(">>> Quay nguoc 2s")
    send(1, 100 if DRIVER == "ZDT" else 30)
    time.sleep(2)

    print(">>> Dung")
    stop()

except KeyboardInterrupt:
    pass
finally:
    # QUAN TRONG: repo 25E_tripod_head THIEU doan nay -> Ctrl-C giua chung
    # thi motor giu nguyen toc do cuoi va quay mai. Voi laser 12W tren cum
    # pan/tilt thi day la loi nguy hiem. Luon dung motor trong finally.
    stop()
    time.sleep_ms(50)
    uart.deinit()
    print("Da dung motor + dong UART.")
