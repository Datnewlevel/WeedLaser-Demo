# TEST 3 - Man hinh LCD + camera cung luc.
# Chi chay sau khi TEST 2 da tim ra SENSOR_ID dung.
#
# Neu man hinh den thui: doi USE_LCD = False -> xem qua IDE de biet
# loi o LCD hay o camera.

SENSOR_ID = 0          # <<< dien id tim duoc o TEST 2
USE_LCD   = True       # False = chi xem trong CanMV IDE

import time, os, sys, gc
from media.sensor import *
from media.display import *
from media.media import *

CAM_W, CAM_H = 640, 480
LCD_W, LCD_H = 800, 480        # ST7701 3.5" cua 01Studio. Man khac -> sua lai.

off_x = (LCD_W - CAM_W) // 2
off_y = (LCD_H - CAM_H) // 2

sensor = None
try:
    sensor = Sensor(id=SENSOR_ID)
    sensor.reset()
    sensor.set_framesize(width=CAM_W, height=CAM_H)
    sensor.set_pixformat(Sensor.RGB565)

    if USE_LCD:
        # to_ide=True -> vua ra LCD vua stream ve IDE. Rat tien luc dev.
        Display.init(Display.ST7701, width=LCD_W, height=LCD_H, to_ide=True)
    else:
        Display.init(Display.VIRT, width=CAM_W, height=CAM_H, fps=60)
        off_x = off_y = 0

    MediaManager.init()
    sensor.run()

    clock = time.clock()
    cx, cy = CAM_W // 2, CAM_H // 2

    while True:
        clock.tick()
        img = sensor.snapshot()

        # Ve crosshair - chinh la thu thay the cv2.drawMarker trong tracking.py
        img.draw_cross(cx, cy, color=(255, 0, 0), size=20, thickness=2)
        img.draw_circle(cx, cy, 40, color=(0, 255, 255), thickness=2, fill=False)
        img.draw_string_advanced(0, 0, 30, "FPS:%.1f" % clock.fps(), color=(0, 255, 0))

        Display.show_image(img, x=off_x, y=off_y)
        gc.collect()

except KeyboardInterrupt:
    pass
except BaseException as e:
    sys.print_exception(e)
finally:
    if isinstance(sensor, Sensor):
        sensor.stop()
    Display.deinit()
    os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
    time.sleep_ms(100)
    MediaManager.deinit()
