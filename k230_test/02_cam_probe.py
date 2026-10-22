# TEST 2 - Camera. Ban co 3 cam -> can biet cam nao ung voi id nao.
#
# CACH DUNG: doi SENSOR_ID = 0, chay. Roi 1, chay. Roi 2, chay.
# Chay tung id MOT LAN MOT. Khong loop qua 3 id trong 1 script:
# MediaManager init/deinit lien tuc rat de treo.
#
# Ket qua mong doi: cua so anh hien trong CanMV IDE + FPS in ra console.
# Loi "sensor not found" / treo -> id do khong co cam cam vao.

SENSOR_ID = 0          # <<< DOI SO NAY: 0, 1, 2

import time, os, sys, gc
from media.sensor import *
from media.display import *
from media.media import *

W, H = 640, 480
sensor = None

try:
    print("Dang mo sensor id =", SENSOR_ID)
    sensor = Sensor(id=SENSOR_ID)
    sensor.reset()
    sensor.set_framesize(width=W, height=H)
    sensor.set_pixformat(Sensor.RGB565)

    # VIRT = chi hien trong CanMV IDE, khong can LCD. An toan nhat de test dau tien.
    Display.init(Display.VIRT, width=W, height=H, fps=60)
    MediaManager.init()
    sensor.run()

    print("OK! Sensor id", SENSOR_ID, "hoat dong.")
    clock = time.clock()
    while True:
        clock.tick()
        img = sensor.snapshot()
        img.draw_string_advanced(0, 0, 30, "id=%d  FPS:%.1f" % (SENSOR_ID, clock.fps()),
                                 color=(255, 0, 0))
        Display.show_image(img)
        gc.collect()

except KeyboardInterrupt:
    pass
except BaseException as e:
    print("Sensor id", SENSOR_ID, "LOI:")
    sys.print_exception(e)
finally:
    if isinstance(sensor, Sensor):
        sensor.stop()
    Display.deinit()
    os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
    time.sleep_ms(100)
    MediaManager.deinit()
    print("Da giai phong.")
