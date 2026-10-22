# TEST 11 - BAN LASER MAX CONG SUAT 30 GIAY
#
# PASTE THANG VAO CANMV IDE.
#
# ==========================================================
#  AN TOAN - BAT BUOC DOC
# ==========================================================
#  * DEO KINH CHAN 405nm truoc khi bam Run.
#  * Chia tia vao vat chan kim loai / gach chiu lua. KHONG chia
#    ra khong gian mo, khong co vat phan chieu quanh do.
#  * Cong tac co khi cat 12V cua laser de trong tam tay.
#  * Khong co nguoi/vat nuoi trong phong.
#  * 30 giay LIEN TUC o 100% dai hon nhieu so voi cac lan test 3 giay
#    truoc day -> theo doi nhiet do module. Module co quat tan nhiet,
#    nhung neu vo nhom nong ran thi DUNG NGAY.
#  * Muon dung giua chung: Ctrl-C. Khoi finally luon tat laser.
# ==========================================================

LASER_PIN    = 43
LASER_PWM_CH = 1
LASER_FREQ   = 1000
DUTY_MAX     = 100      # % - full cong suat
BURN_SECONDS = 30

import time, sys
from machine import FPIOA, Pin, PWM

fpioa = FPIOA()


def ve_muc_an_toan():
    # Ep chan xuong muc THAP = laser tat.
    # Da xac nhan bang thuc nghiem: chan tha noi = BAN, nen muc thap
    # moi la trang thai an toan.
    try:
        fpioa.set_function(LASER_PIN, getattr(FPIOA, "GPIO%d" % LASER_PIN))
        Pin(LASER_PIN, Pin.OUT).off()
    except Exception as e:
        print("!!! Khong ep duoc chan ve muc an toan:", e)


pwm = None
try:
    ve_muc_an_toan()
    print("=" * 52)
    print("  BAN LASER %d%% TRONG %d GIAY" % (DUTY_MAX, BURN_SECONDS))
    print("  Ctrl-C de dung giua chung")
    print("=" * 52)
    print("Bat dau sau 3 giay...")
    for i in (3, 2, 1):
        print("  ", i)
        time.sleep(1)

    # Firmware v1.8: KHONG co PWM.enable().
    # PWM tu phat ngay khi dat freq() roi duty().
    fpioa.set_function(LASER_PIN, getattr(FPIOA, "PWM%d" % LASER_PWM_CH))
    pwm = PWM(LASER_PWM_CH)
    pwm.freq(LASER_FREQ)
    pwm.duty(DUTY_MAX)
    print(">>> LASER BAT - %d%%" % DUTY_MAX)

    t0 = time.time()
    while True:
        con_lai = BURN_SECONDS - (time.time() - t0)
        if con_lai <= 0:
            break
        print("   dang ban... con %.0f giay" % con_lai)
        time.sleep(1)

    print(">>> Het thoi gian.")

except KeyboardInterrupt:
    print("\n>>> Nguoi dung dung.")
except BaseException as e:
    print(">>> LOI:")
    sys.print_exception(e)
finally:
    # Tat 2 lop: dua duty ve 0, roi ep chan xuong muc thap bang GPIO.
    # Lop thu hai khong phu thuoc PWM co hoat dong hay khong.
    if pwm is not None:
        try:
            pwm.duty(0)
        except Exception:
            pass
    ve_muc_an_toan()
    print(">>> LASER DA TAT.")
