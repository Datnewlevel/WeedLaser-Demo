# UVC BUOC 3 - WEBCAM USB HIEN LEN MAN HINH LCD 2.4"
# Mode da xac nhan: 640x480 MJPEG 30fps | Webcam: Jieli Technology
#
# BAI HOC tu lan truoc: BAT MAN HINH TRUOC khi dung bat ky hang so UVC nao.
# Neu UVC loi, con co man hinh de bao loi - khong bi den thui.

import sys, time, gc
from media.display import *
from media.media import *

W, H = 640, 480

# --- Bat man hinh NGAY DAU TIEN ---
Display.init(Display.ST7701, width=ALIGN_UP(W, 16), height=H, to_ide=True)
print("Display OK")

from media.uvc import *          # import sau khi man hinh da san sang

started = False
try:
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

    succ, m = UVC.select_video_mode(UVC.video_mode(W, H, UVC.FOURCC_MJPEG, 30))
    print("Chon mode 640x480@30 MJPEG ->", succ)
    if not succ:
        raise SystemExit

    UVC.start(cvt=False)
    started = True
    print("Dang stream len man hinh...")

    clock = time.clock()
    while True:
        clock.tick()
        try:
            img = UVC.snapshot()
        except Exception:
            continue
        if img is None:
            continue
        try:
            img = img.to_rgb565()        # MJPEG -> RGB565 de show duoc
            img.draw_string_advanced(8, 8, 24, "WEBCAM USB", color=(0, 255, 0))
            img.draw_string_advanced(8, 38, 22, "FPS:%.1f" % clock.fps(),
                                     color=(255, 255, 0))
            Display.show_image(img)
            img.__del__()
            gc.collect()
        except OSError:
            pass

except KeyboardInterrupt:
    pass
except SystemExit:
    pass
except BaseException as e:
    print(">>> LOI:")
    sys.print_exception(e)
finally:
    if started:
        UVC.stop()
    time.sleep_ms(100)
    Display.deinit()
    print("Da giai phong.")
