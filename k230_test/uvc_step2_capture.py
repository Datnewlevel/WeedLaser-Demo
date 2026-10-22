# UVC BUOC 2 - LAY FRAME THAT, dung dung mode da xac nhan: 640x480 MJPEG 30fps
# Khong dung Display o day nua - chi in ra so lieu qua Serial Terminal.

import sys, time
from media.uvc import *

print("Do webcam...")
dev = None
t0 = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), t0) < 15000:
    plugin, d = UVC.probe()
    if plugin:
        dev = d
        print("Thay webcam:", d)
        break
    time.sleep_ms(200)

if dev is None:
    print("KHONG THAY WEBCAM")
    raise SystemExit

succ, m = UVC.select_video_mode(UVC.video_mode(640, 480, UVC.FOURCC_MJPEG, 30))
print("Chon mode 640x480@30 MJPEG ->", succ)
if not succ:
    print("LOI: mode nay lan truoc da THANH CONG, gio lai FAIL - webcam co the")
    print("     can rut cam lai (usb chua reset het tu lan chay truoc).")
    raise SystemExit

print("Bat dau UVC.start()...")
UVC.start(cvt=False)

got = 0
dropped = 0
clock_start = time.ticks_ms()
try:
    for i in range(90):
        try:
            img = UVC.snapshot()
        except Exception as e:
            dropped += 1
            continue
        if img is None:
            dropped += 1
            continue
        got += 1
        if got == 1:
            print("Frame dau tien:", img.width(), "x", img.height(),
                  "sau", time.ticks_diff(time.ticks_ms(), clock_start), "ms")
        img.__del__()
        if got >= 60:
            break
finally:
    UVC.stop()

elapsed = time.ticks_diff(time.ticks_ms(), clock_start) / 1000.0
print()
print("Lay duoc", got, "frame, rot", dropped, "trong", round(elapsed, 2), "s")
if got > 0:
    print("FPS thuc te ~", round(got / elapsed, 1))
    print(">>> WEBCAM CHAY DUOC. San sang ghep vao Display / YOLO.")
else:
    print(">>> select_video_mode OK nhung khong lay duoc frame nao.")
