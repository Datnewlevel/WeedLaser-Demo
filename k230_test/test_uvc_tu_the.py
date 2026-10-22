# TEST WEBCAM USB (UVC) tren CanMV K230
#
# Khac camera MIPI: KHONG dung Sensor/MediaManager, dung module media.uvc.
#
# LUU Y CONG USB:
#   Neu board chi co 1 cong USB-C (vua nguon vua IDE) thi khi cam webcam
#   vao do se MAT ket noi CanMV IDE. Khi do phai:
#     - Doi ten file nay thanh main.py de board tu chay, VA
#     - Cap nguon 5V ngoai (dung setup da test OK: "NGUON 5V OK" 65 FPS)
#   Can adapter USB-C OTG (USB-C duc -> USB-A cai) de cam webcam.

import time, os, sys, gc
from media.display import *
from media.media import *
from media.uvc import *

# Man 2.4 inch cua ban: 640x480. ALIGN_UP de khop yeu cau phan cung (boi so 16).
DISPLAY_WIDTH  = ALIGN_UP(640, 16)
DISPLAY_HEIGHT = 480

Display.init(Display.ST7701, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, to_ide=True)

print("Dang do webcam USB... (cam webcam vao neu chua)")
while True:
    plugin, dev = UVC.probe()
    if plugin:
        print("Da thay USB Camera:", dev)
        break
    time.sleep_ms(200)

# MJPEG 640x480 @30fps. Neu webcam khong ho tro se bao succ=False.
mode = UVC.video_mode(640, 480, UVC.FOURCC_MJPEG, 30)
succ, mode = UVC.select_video_mode(mode)
print("Chon mode:", succ, "| mode:", mode)

if not succ:
    print(">>> Webcam KHONG ho tro 640x480 MJPEG 30fps.")
    print(">>> Thu doi sang 320x240, hoac FOURCC_YUYV thay MJPEG.")

UVC.start(cvt=False)

clock = time.clock()
try:
    while True:
        clock.tick()
        img = UVC.snapshot()
        if img is not None:
            try:
                img = img.to_rgb565()          # bat buoc truoc khi show
                img.draw_string_advanced(10, 10, 30, "UVC OK", color=(0, 255, 0))
                img.draw_string_advanced(10, 50, 24, "FPS:%.1f" % clock.fps(),
                                         color=(255, 255, 0))
                Display.show_image(img)
                img.__del__()
                gc.collect()
            except OSError:
                pass
except KeyboardInterrupt:
    pass
except BaseException as e:
    print(">>> LOI:")
    sys.print_exception(e)
finally:
    UVC.stop()
    time.sleep_ms(100)
    Display.deinit()
    print("Da giai phong.")
