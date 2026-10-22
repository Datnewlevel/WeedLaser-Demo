# TEST 4 - UART loopback. LAM TRUOC KHI CAM DRIVER MOTOR.
#
# PHAN CUNG: noi tat IO11 <-> IO12 bang 1 soi day jumper. Khong can gi khac.
# Muc dich: chung minh UART + FPIOA cau hinh dung, TRUOC khi co motor
# tham gia. Neu bo qua buoc nay, luc motor khong chay ban se khong biet
# loi o UART, o day, o ID motor hay o protocol.
#
# KY VONG: in ra "PASS".

from machine import UART, FPIOA
import time

TX_PIN, RX_PIN = 11, 12        # giong repo 25E_tripod_head

fpioa = FPIOA()
fpioa.set_function(TX_PIN, FPIOA.UART2_TXD)
fpioa.set_function(RX_PIN, FPIOA.UART2_RXD)

uart = UART(UART.UART2, baudrate=115200,
            bits=UART.EIGHTBITS, parity=UART.PARITY_NONE, stop=UART.STOPBITS_ONE)

payload = bytes([0x01, 0xF6, 0x01, 0xFF, 0xFF, 0x00, 0x64, 0x00, 0x6B])

print("Gui :", [hex(b) for b in payload])
uart.write(payload)
time.sleep_ms(100)
got = uart.read()

if got is None:
    print("FAIL - khong nhan duoc gi.")
    print("  -> kiem tra day jumper IO11-IO12")
    print("  -> kiem tra FPIOA co dung ten UART2_TXD/UART2_RXD khong")
elif bytes(got) == payload:
    print("Nhan:", [hex(b) for b in got])
    print("PASS - UART2 hoat dong.")
else:
    print("Nhan:", [hex(b) for b in got])
    print("FAIL - du lieu sai lech (nhieu? sai baudrate?)")

uart.deinit()
