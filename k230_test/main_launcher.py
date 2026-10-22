# main.py - BO DIEU PHOI: chon script chay khi board khoi dong
#
# Board tu chay file ten "main.py" o goc the SD. Thay vi copy de len main.py
# moi lan doi y, chi can sua 1 dong SCRIPT ben duoi.
#
# CACH DUNG:
#   1. Copy file nay len the SD, DOI TEN thanh "main.py"
#   2. Sua bien SCRIPT thanh file muon chay
#   3. Rut the (nho Eject), cam vao K230, cap nguon
#
# LUU Y: script dieu khien bang phim (08_motor_wasd) KHONG dung duoc o day,
# vi autorun thi khong co IDE de go phim. Dung 07_motor_k230_test.py.

SCRIPT = "07_motor_k230_test.py"     # <<< SUA DONG NAY

# Cac lua chon:
#   "07_motor_k230_test.py"   - test motor tu dong 5 buoc
#   "main_uvc_yolo_grass.py"  - webcam + YOLO detect co (ban day du)
#   "main_display_test.py"    - test camera MIPI + man hinh
#   "test_uvc.py"             - test webcam USB don gian

import sys


def emergency_stop():
    """Luoi an toan cuoi cung: dung ca 2 motor du script co loi gi.

    Chay doc lap voi script ben trong - neu script chet giua chung ma chua
    kip dung motor, ham nay van gui lenh dung. Voi cum pan/tilt mang laser
    thi day la lop bao ve khong the thieu.
    """
    try:
        from machine import UART, FPIOA
        import time
        fpioa = FPIOA()
        fpioa.set_function(11, FPIOA.UART2_TXD)
        fpioa.set_function(12, FPIOA.UART2_RXD)
        u = UART(UART.UART2, baudrate=115200, bits=UART.EIGHTBITS,
                 parity=UART.PARITY_NONE, stop=UART.STOPBITS_ONE)
        for addr in (0xE1, 0xE2):
            frame = [addr, 0xF7]
            frame.append(sum(frame) & 0xFF)
            u.write(bytes(frame))
            time.sleep_ms(20)
        u.deinit()
        print(">>> [launcher] da gui lenh dung ca 2 motor")
    except Exception as e:
        print(">>> [launcher] khong gui duoc lenh dung:", e)


print("=" * 52)
print("  LAUNCHER -> chay:", SCRIPT)
print("=" * 52)

try:
    with open(SCRIPT) as f:
        code = f.read()
    exec(code)

except OSError:
    print(">>> KHONG TIM THAY FILE:", SCRIPT)
    print(">>> Kiem tra lai ten file tren the SD (phan biet hoa/thuong).")
except KeyboardInterrupt:
    print(">>> Nguoi dung dung.")
except BaseException as e:
    print(">>> SCRIPT LOI:")
    sys.print_exception(e)
finally:
    emergency_stop()
    print(">>> [launcher] ket thuc.")
