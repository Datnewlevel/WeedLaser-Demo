# CHAN DOAN MAN HINH - CanMV K230 / K230 mini
#
# Doi bien DISPLAY ben duoi roi chay tu CanMV IDE (KHONG de autorun).
# Muc dich: tach bach "man hinh sai cau hinh" voi "main.py loi vi ly do khac".
#
# to_ide=True -> anh van stream ve CanMV IDE ke ca khi man vat ly khong len.
#   + Neu IDE CO anh nhung man vat ly den  -> sai loai man / cap MIPI.
#   + Neu IDE cung KHONG co anh            -> loi camera hoac loi sau hon.
#
# THU TU LAM:
#   1. Doi ten main.py -> main.py.bak tren the SD (chan autorun, khong xoa).
#   2. Cam board, mo CanMV IDE, bam ket noi.
#   3. Chay file nay tu IDE. Doc ky console neu co traceback.
#   4. Chua len thi doi DISPLAY sang gia tri khac, chay lai.
#   5. Tim ra gia tri dung -> sua dong `display = "..."` trong main.py goc,
#      roi doi ten lai thanh main.py.

DISPLAY = "lcd2_4"        # <<< thu lan luot: "lcd2_4" / "lcd3_5" / "hdmi"

import time, os, sys, gc
from media.sensor import *
from media.display import *
from media.media import *

if DISPLAY == "hdmi":
    MODE, W, H = Display.LT9611, 1920, 1080
elif DISPLAY == "lcd3_5":
    MODE, W, H = Display.ST7701, 800, 480
else:                                   # lcd2_4
    MODE, W, H = Display.ST7701, 640, 480

print("=" * 46)
print("Thu che do:", DISPLAY, "->", W, "x", H)
print("=" * 46)

sensor = None
try:
    sensor = Sensor()
    sensor.reset()
    sensor.set_framesize(width=640, height=480)
    sensor.set_pixformat(Sensor.RGB565)

    Display.init(MODE, width=W, height=H, to_ide=True)
    MediaManager.init()
    sensor.run()

    print("Init OK. Neu man van den ma IDE co anh -> sai loai man.")
    clock = time.clock()
    while True:
        clock.tick()
        img = sensor.snapshot()
        # Ve that noi bat de de nhan ra man da len hay chua
        img.draw_rectangle(0, 0, 639, 479, color=(255, 0, 0), thickness=8)
        img.draw_string_advanced(20, 20, 40, DISPLAY, color=(0, 255, 0))
        img.draw_string_advanced(20, 70, 30, "%dx%d  FPS:%.1f" % (W, H, clock.fps()),
                                 color=(255, 255, 0))
        Display.show_image(img)
        gc.collect()

except KeyboardInterrupt:
    pass
except BaseException as e:
    print(">>> LOI - day chinh la thu can doc:")
    sys.print_exception(e)
finally:
    if isinstance(sensor, Sensor):
        sensor.stop()
    Display.deinit()
    os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
    time.sleep_ms(100)
    MediaManager.deinit()
    print("Da giai phong.")
