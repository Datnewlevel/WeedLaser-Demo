# TEST 7 - Dieu khien 2 motor MKS SERVO42C tu K230 (KHONG dung camera)
#
# Chay qua CanMV IDE, doc ket qua o tab Serial Terminal.
# Muc dich: xac nhan K230 dieu khien duoc motor TRUOC khi ghep vao
# vong nhan dien - tach biet "loi motor" khoi "loi thi giac".
#
# AN TOAN TRUOC KHI CHAY:
#   - Motor de ROI, CHUA lap len cum pan/tilt
#   - LASER THAO RA HOAN TOAN
#   - GND chung giua K230 va nguon 12V driver
#   - Tro noi tiep 220 ohm da co tren duong TX cua moi driver
#
# Da xac nhan tu ban ky truoc:
#   PAN  = 0xE1 (trai/phai), toc do toi da 5  (~46.9 RPM o Mstep 16)
#   TILT = 0xE2 (len/xuong), toc do toi da 3  (~28.1 RPM o Mstep 16)

import time, sys
from mks_servo import (MksServoBus, ADDR_PAN, ADDR_TILT,
                       MAX_SPEED_PAN, MAX_SPEED_TILT)


def show(nhan, reply):
    if reply is None:
        print("   %-26s (khong doc phan hoi)" % nhan)
    else:
        print("   %-26s <- %s" % (nhan, " ".join("%02x" % b for b in reply)))


bus = None
try:
    bus = MksServoBus(read_reply=True)
    print("=" * 52)
    print("BUOC 1: kiem tra 2 driver co tra loi khong")
    print("=" * 52)
    for addr, ten in ((ADDR_PAN, "PAN  (E1)"), (ADDR_TILT, "TILT (E2)")):
        r = bus.read_protection(addr)
        show(ten + " doc bao ve", r)
        if r is None or len(r) < 2:
            print("   !!! %s KHONG TRA LOI - kiem tra dia chi/baud/day" % ten)
        elif r[1] == 1:
            print("   !!! %s DANG BI KHOA BAO VE -> giai tru" % ten)
            show(ten + " giai tru", bus.release_protection(addr))
        time.sleep_ms(200)

    print()
    print("=" * 52)
    print("BUOC 2: enable ca 2 truc")
    print("=" * 52)
    show("PAN  enable", bus.enable(ADDR_PAN, True))
    time.sleep_ms(200)
    show("TILT enable", bus.enable(ADDR_TILT, True))

    print()
    print("=" * 52)
    print("BUOC 3: quay tung truc, thuan roi nguoc")
    print("=" * 52)

    for addr, ten, spd in ((ADDR_PAN, "PAN ", MAX_SPEED_PAN),
                           (ADDR_TILT, "TILT", MAX_SPEED_TILT)):
        for direction, chieu in ((0, "THUAN"), (1, "NGUOC")):
            print("   %s %s toc do %d - 2 giay" % (ten, chieu, spd))
            bus.set_speed(addr, direction, spd)
            time.sleep(2)
            bus.stop(addr)
            time.sleep(1)

    print()
    print("=" * 52)
    print("BUOC 4: chay ca 2 truc CUNG LUC (thu bus chung)")
    print("=" * 52)
    print("   Ca 2 quay thuan - 3 giay")
    bus.drive(0, MAX_SPEED_PAN, 0, MAX_SPEED_TILT)
    time.sleep(3)
    print("   Ca 2 quay nguoc - 3 giay")
    bus.drive(1, MAX_SPEED_PAN, 1, MAX_SPEED_TILT)
    time.sleep(3)
    bus.stop_all()

    print()
    print("=" * 52)
    print("BUOC 5: mo phong bam muc tieu (sai so pixel -> toc do)")
    print("=" * 52)
    from mks_servo import error_to_speed
    for err_x in (0, 5, 40, 120, -120, -40, 0):
        d, s = error_to_speed(err_x, deadzone_px=20, gain=0.05,
                              max_speed=MAX_SPEED_PAN)
        print("   err_x = %5d px  ->  chieu %d, toc do %d" % (err_x, d, s))
        bus.set_speed(ADDR_PAN, d, s)
        time.sleep(1)

    print()
    print(">>> XONG. Neu ca 4 buoc deu quay dung, san sang ghep vao main.py")

except KeyboardInterrupt:
    print("\nNguoi dung dung.")
except BaseException as e:
    print(">>> LOI:")
    sys.print_exception(e)
finally:
    # BAT BUOC: dung motor trong moi tinh huong.
    # Day chinh la loi cua repo tham khao 25E_tripod_head - thieu buoc nay
    # thi Ctrl-C giua chung se de motor quay mai.
    if bus is not None:
        bus.close()
    print("Da dung motor va dong UART.")
