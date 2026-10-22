# TEST 6 - Chan dieu khien laser.
#
# CANH BAO: mac dinh cua driver laser (thoi diem chan tha noi / chua co
# lenh gi) la KHONG THE DOAN duoc chi bang doc datasheet chung chung -
# PHAI TU KIEM CHUNG tren dung module dang co. Bai nay dung de lam dieu do.
#
# QUY TRINH AN TOAN BAT BUOC (doc het truoc khi cam 12V vao laser):
#   - Chan tia laser vao 1 vat chan kim loai/gom KHONG chay, sat mieng
#     phat, khong co vat phan chieu xung quanh.
#   - Deo kinh chan dung buoc song 405nm cho TAT CA nguoi co mat, ke ca
#     khi tin rang no khong ban.
#   - Day 12V vao laser KHONG han/khoa co dinh - cam tay hoac qua cong
#     tac bam-nha, san sang rut ngay lap tuc.
#   - Cap 12V tung dot 1-2s roi rut ra ngay, khong de lien tuc.
#
# THU TU CHAY:
#   1. K230 CHUA nap gi ca (chan la GPIO mac dinh cua chip, gan giong
#      luc vua bat nguon). Cap 12V cho laser 1-2s, quan sat vat chan.
#      -> Day la phep thu quan trong nhat: no mo phong dung trang thai
#         thuc te truoc khi code chay xong.
#   2. Chay MODE_TEST = "floating" o duoi, nap vao K230, cap 12V lai.
#      Neu ket qua khac buoc 1 -> chinh la khoang trong luc boot ma
#      dien tro phan cung phai bit.
#   3. Chay MODE_TEST = "safe_low" - xac nhan muc AN TOAN thuc su tat laser.
#   4. Chay MODE_TEST = "pwm_low" - xac nhan PWM co dieu khien duoc that.
#   5. Ket luan:
#      - Tha noi ma BAN  -> BAT BUOC dien tro keo XUONG ~1k o chan PWM,
#        khong duoc bo qua trong moi truong hop.
#      - Tha noi ma TAT  -> nguy co thap hon, nhung van nen giu dien tro
#        keo xuong nhu bao hiem re tien (sai lech linh kien, lo khac...).

from machine import Pin, PWM, FPIOA
import time

LASER_PIN   = 43          # <<< doi theo board cua ban
PWM_CH      = 1           # kenh PWM tuong ung chan tren (IO43 -> PWM1)
ACTIVE_HIGH = True        # <<< True = module ban khi HIGH. XAC DINH TRUOC KHI CHAY.
FREQ        = 1000        # giong LASER_PWM_FREQ trong tracking.py

SAFE = 0 if ACTIVE_HIGH else 100     # duty % o trang thai an toan


def safe_state_gpio():
    """Dua chan ve muc an toan bang GPIO thuan (chac chan nhat)."""
    fpioa = FPIOA()
    fpioa.set_function(LASER_PIN, getattr(FPIOA, "GPIO%d" % LASER_PIN))
    p = Pin(LASER_PIN, Pin.OUT)
    if ACTIVE_HIGH:
        p.off()
    else:
        p.on()
    return p


print("=" * 50)
print("Chan laser :", LASER_PIN)
print("Kich muc   :", "CAO" if ACTIVE_HIGH else "THAP")
print("Muc an toan:", "0V (LOW)" if ACTIVE_HIGH else "3.3V (HIGH)")
print("=" * 50)
print()
print('  MODE_TEST = "floating" -> chan de INPUT, KHONG pull gi ca.')
print('                            Day la phep thu QUAN TRONG NHAT: no gia lap')
print('                            dung trang thai chan luc chua co code nao chay')
print('                            (moi bat nguon / crash / dang boot).')
print('                            CAP 12V TUNG DOT NGAN roi xem vat chan co sang.')
print('  MODE_TEST = "safe_low"  -> ep chan ve muc an toan da xac dinh.')
print('  MODE_TEST = "pwm_low"   -> PWM duty thap, xac nhan dieu khien duoc that.')
print('  MODE_TEST = "pwm_mid"   -> PWM duty 50%.')
print()

MODE_TEST = "floating"     # <<< doi: "floating" / "safe_low" / "pwm_low" / "pwm_mid"

pwm = None
try:
    if MODE_TEST == "floating":
        # KHONG goi fpioa.set_function o day - de nguyen chan o trang thai
        # sau reset cua chip, roi cau hinh no thanh input KHONG pull.
        # Day la mo phong gan nhat voi "chan tha noi thuc su".
        fpioa = FPIOA()
        fpioa.set_function(LASER_PIN, getattr(FPIOA, "GPIO%d" % LASER_PIN))
        pin = Pin(LASER_PIN, Pin.IN, Pin.PULL_NONE)
        print(">>> Chan dang THA NOI (input, khong pull).")
        print(">>> BAY GIO moi cap 12V cho laser, tung dot 1-2s, quan sat vat chan.")
        print(">>> Ctrl-C de thoat.")
        while True:
            time.sleep(1)

    elif MODE_TEST == "safe_low":
        pin = safe_state_gpio()
        print(">>> Dang ep muc AN TOAN. Do dong ho / cap 12V thu de xac nhan TAT.")
        print(">>> Ctrl-C de thoat.")
        while True:
            time.sleep(1)

    else:
        duty = 10 if MODE_TEST == "pwm_low" else 50
        fpioa = FPIOA()
        fpioa.set_function(LASER_PIN, getattr(FPIOA, "PWM%d" % PWM_CH))
        pwm = PWM(PWM_CH, FREQ, duty if ACTIVE_HIGH else 100 - duty, enable=True)
        print(">>> PWM %dHz duty %d%%. Quan sat do sang tia (an toan da chan)." % (FREQ, duty))
        print(">>> Ctrl-C de thoat.")
        while True:
            time.sleep(1)

except KeyboardInterrupt:
    pass
finally:
    # Luon tra ve muc an toan khi thoat. Khong bao gio de chan thu noi.
    if pwm is not None:
        try:
            pwm.enable(False)
        except Exception:
            pass
    safe_state_gpio()
    print("Da tra chan ve muc AN TOAN (GPIO ep cung).")
