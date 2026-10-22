# TEST 1 - GPIO + FPIOA. Muc tieu: board con song, IDE nap code duoc.
# Khac Pi 5: K230 BAT BUOC mux chan qua FPIOA truoc khi dung. gpiozero khong co buoc nay.
from machine import Pin, FPIOA
import time

LED_PIN = 52          # 01Studio CanMV K230 = LED xanh. Board khac co the khac -> tra wiki board.

fpioa = FPIOA()
fpioa.set_function(LED_PIN, FPIOA.GPIO52)
led = Pin(LED_PIN, Pin.OUT)

print("LED test bat dau. Ctrl-C de dung.")
try:
    while True:
        led.on()
        time.sleep(0.5)
        led.off()
        time.sleep(0.5)
except KeyboardInterrupt:
    led.off()
    print("Xong.")
