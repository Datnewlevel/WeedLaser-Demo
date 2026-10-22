"""
MKS SERVO42C - dieu khien qua UART tu CanMV K230.

Giao thuc xac nhan tu manual V1.1.2 + thu nghiem thuc te ngay 02/09/2026:
    Khung lenh: [addr] [function] [data...] [checksum]
    checksum   = tong tat ca byte truoc do & 0xFF

CANH BAO tu kinh nghiem debug:
  - THIEU byte checksum => driver KHONG phan hoi gi ca (no van cho byte con
    thieu, khong coi la khung hoan chinh). Day KHONG phai loi phan cung.
  - Manual co IT NHAT 2 cho in sai/thieu checksum:
      * "e0 f6 81 d7" (nguoc toc do 1) -> dung phai la "e0 f6 81 57"
      * "E0 FD 02 00 00 0C 80" (muc 6.4) -> thieu han byte checksum (6B)
    Nen luon TU TINH checksum, dung copy tu manual.
"""

import time
from machine import UART, FPIOA

# ==========================================================
# CAU HINH - SUA O DAY
# ==========================================================

UART_ID   = UART.UART2
TX_PIN    = 11              # IO11 -> RX cua driver (qua tro noi tiep 220 ohm)
RX_PIN    = 12              # IO12 <- TX cua driver (qua tro noi tiep 220 ohm)
BAUD      = 115200          # PHAI khop UartBaud tren menu OLED cua CA HAI driver

ADDR_PAN  = 0xE1            # <<< XAC NHAN LAI dia chi thuc te
ADDR_TILT = 0xE2            # <<< XAC NHAN LAI dia chi thuc te

# Toc do toi da moi truc (0-127). Nguoi dung chon: ngang 5, doc 3.
MAX_SPEED_PAN  = 5          # ~46.9 RPM o Mstep 16
MAX_SPEED_TILT = 3          # ~28.1 RPM o Mstep 16

# Khoang nghi giua 2 lenh gui cho 2 driver khac nhau.
# BAT BUOC khi 2 driver dung chung 1 bus UART: driver truoc phai tra loi
# xong han truoc khi hoi con sau, tranh 2 chan TX cung day tin hieu 1 luc.
# Frame + phan hoi ~1.5ms o 115200 baud -> 15ms la du rong rai.
INTER_CMD_MS = 15

# ==========================================================
# MA LENH (manual muc 5)
# ==========================================================

CMD_READ_ENCODER = 0x30
CMD_RELEASE_PROT = 0x3D     # giai tru bao ve ket rotor
CMD_READ_PROT    = 0x3E     # doc trang thai bao ve
CMD_RESTORE      = 0x3F     # khoi phuc mac dinh (can khoi dong lai sau do)
CMD_ENABLE       = 0xF3     # data: 01 = enable, 00 = disable
CMD_SPEED        = 0xF6     # data: bit7 = chieu, bit0-6 = toc do
CMD_STOP         = 0xF7
CMD_MOVE         = 0xFD     # data: VAL + so xung


def checksum(payload):
    return sum(payload) & 0xFF


def build(addr, *data):
    """Dung khung hoan chinh, tu them checksum."""
    frame = [addr] + list(data)
    frame.append(checksum(frame))
    return bytes(frame)


class MksServoBus:
    """Quan ly nhieu driver MKS SERVO42C tren CUNG MOT bus UART.

    Cac driver phan biet nhau bang byte dia chi dau khung (0xE0-0xE9),
    nen chi can 1 cap TX/RX cho tat ca.
    """

    def __init__(self, uart_id=UART_ID, tx=TX_PIN, rx=RX_PIN, baud=BAUD,
                 read_reply=True):
        fpioa = FPIOA()
        fpioa.set_function(tx, FPIOA.UART2_TXD)
        fpioa.set_function(rx, FPIOA.UART2_RXD)
        self.uart = UART(uart_id, baudrate=baud,
                         bits=UART.EIGHTBITS,
                         parity=UART.PARITY_NONE,
                         stop=UART.STOPBITS_ONE)
        self.read_reply = read_reply
        self._last_speed = {}          # addr -> (direction, speed) da gui lan cuoi

    # ---------- tang thap ----------

    def _send(self, addr, *data):
        frame = build(addr, *data)
        self.uart.write(frame)
        if not self.read_reply:
            return None
        time.sleep_ms(5)
        try:
            return self.uart.read()
        except Exception:
            return None

    # ---------- lenh co ban ----------

    def enable(self, addr, on=True):
        return self._send(addr, CMD_ENABLE, 0x01 if on else 0x00)

    def stop(self, addr):
        self._last_speed[addr] = (0, 0)
        return self._send(addr, CMD_STOP)

    def set_speed(self, addr, direction, speed):
        """direction: 0 = thuan, 1 = nguoc.  speed: 0-127."""
        speed = max(0, min(127, int(speed)))
        direction = 1 if direction else 0
        # Bo qua neu khong doi gi -> giam tai bus dang ke khi bam muc tieu
        if self._last_speed.get(addr) == (direction, speed):
            return None
        self._last_speed[addr] = (direction, speed)
        val = (direction << 7) | speed
        return self._send(addr, CMD_SPEED, val)

    def move_pulses(self, addr, direction, speed, pulses):
        """Quay dung so xung roi tu dung. 3200 xung = 1 vong o Mstep 16."""
        speed = max(0, min(127, int(speed)))
        val = (1 if direction else 0) << 7 | speed
        p = int(pulses) & 0xFFFFFFFF
        return self._send(addr, CMD_MOVE, val,
                          (p >> 24) & 0xFF, (p >> 16) & 0xFF,
                          (p >> 8) & 0xFF, p & 0xFF)

    # ---------- chan doan ----------

    def read_encoder(self, addr):
        return self._send(addr, CMD_READ_ENCODER)

    def read_protection(self, addr):
        """Phan hoi data=1 -> DANG bi khoa bao ve; data=2 -> binh thuong."""
        return self._send(addr, CMD_READ_PROT)

    def release_protection(self, addr):
        return self._send(addr, CMD_RELEASE_PROT)

    # ---------- dieu khien 2 truc ----------

    def drive(self, pan_dir, pan_speed, tilt_dir, tilt_speed):
        """Gui lenh cho ca 2 truc, co khoang nghi giua 2 lenh."""
        self.set_speed(ADDR_PAN, pan_dir, pan_speed)
        time.sleep_ms(INTER_CMD_MS)
        self.set_speed(ADDR_TILT, tilt_dir, tilt_speed)

    def stop_all(self):
        """Dung ca 2 truc. LUON goi trong finally."""
        try:
            self.stop(ADDR_PAN)
            time.sleep_ms(INTER_CMD_MS)
            self.stop(ADDR_TILT)
        except Exception:
            pass

    def enable_all(self, on=True):
        self.enable(ADDR_PAN, on)
        time.sleep_ms(INTER_CMD_MS)
        self.enable(ADDR_TILT, on)

    def close(self):
        self.stop_all()
        time.sleep_ms(50)
        try:
            self.uart.deinit()
        except Exception:
            pass


# ==========================================================
# LUAT DIEU KHIEN: sai so pixel -> toc do
# ==========================================================

def error_to_speed(err_px, deadzone_px, gain, max_speed):
    """Doi sai so pixel thanh (chieu, toc do).

    Tra ve (0, 0) khi nam trong vung chet -> motor dung.
    Toc do toi thieu la 1 khi ra ngoai vung chet, vi speed=0 nghia la dung.
    """
    if abs(err_px) <= deadzone_px:
        return 0, 0
    direction = 0 if err_px > 0 else 1
    speed = int(abs(err_px) * gain)
    speed = max(1, min(max_speed, speed))
    return direction, speed
