# --- Laser ---
LASER_ARMED   = True        # <<< True = BAN THAT. False = chay kho (khong cap dien laser)
LASER_PIN     = 43          # <<< DIEN CHAN THUC TE noi toi chan PWM cua laser
LASER_PWM_CH  = 1           # <<< kenh PWM tuong ung chan tren
LASER_FREQ    = 1000        # Hz
LASER_POWER   = 50          # % cong suat khi ban
FIRE_SECONDS  = 3.0         # ban bao lau moi lan
LOCK_SECONDS  = 0.5         # phai giu trong deadzone bao lau moi ban
COOLDOWN_SEC  = 2.0         # nghi giua 2 lan ban

# --- Motor ---
UART_TX, UART_RX = 11, 12
UART_BAUD = 115200
ADDR_PAN, ADDR_TILT = 0xE1, 0xE2
MAX_SPEED_PAN, MAX_SPEED_TILT = 5, 3
INTER_CMD_MS = 15

# --- Bam muc tieu ---
DEADZONE_X = 40             # px, trong vung nay coi nhu da vao tam
DEADZONE_Y = 30
GAIN_X = 0.035              # px -> toc do
GAIN_Y = 0.025
EMA_NUM, EMA_DEN = 7, 10    # loc thong thap chong rung (tu repo 25E_tripod_head)

# --- Thi giac ---
KMODEL_PATH = "/sdcard/best_grass_320.kmodel"
LABELS = ["grass"]
MODEL_INPUT = [320, 320]
CAM_W, CAM_H = 640, 480
CONF_THRESH = 0.5
NMS_THRESH = 0.45
MAX_BOXES = 20

# ==========================================================

import time, os, sys, gc, math
import image, aidemo
import nncase_runtime as nn
import ulab.numpy as np
from machine import UART, FPIOA, Pin, PWM
from media.display import *
from media.media import *
from libs.AIBase import AIBase
from libs.AI2D import Ai2d
from libs.Utils import *

DISPLAY_W = ALIGN_UP(CAM_W, 16)
DISPLAY_H = CAM_H
CENTER_X = CAM_W // 2
CENTER_Y = CAM_H // 2

# --- Bat man hinh TRUOC TIEN (bai hoc tu vu man den) ---
Display.init(Display.ST7701, width=DISPLAY_W, height=DISPLAY_H, to_ide=True)
print("Display OK")

from media.uvc import *


# ==========================================================
# MOTOR
# ==========================================================

class Motors:
    def __init__(self):
        f = FPIOA()
        f.set_function(UART_TX, FPIOA.UART2_TXD)
        f.set_function(UART_RX, FPIOA.UART2_RXD)
        self.u = UART(UART.UART2, baudrate=UART_BAUD, bits=UART.EIGHTBITS,
                      parity=UART.PARITY_NONE, stop=UART.STOPBITS_ONE)
        self.last = {}

    def _send(self, addr, *data):
        fr = [addr] + list(data)
        fr.append(sum(fr) & 0xFF)          # checksum = tong & 0xFF
        self.u.write(bytes(fr))

    def enable(self, on=True):
        self._send(ADDR_PAN, 0xF3, 0x01 if on else 0x00)
        time.sleep_ms(INTER_CMD_MS)
        self._send(ADDR_TILT, 0xF3, 0x01 if on else 0x00)

    def speed(self, addr, direction, spd):
        spd = max(0, min(127, int(spd)))
        key = (direction, spd)
        if self.last.get(addr) == key:     # bo qua neu khong doi -> giam tai bus
            return False
        self.last[addr] = key
        self._send(addr, 0xF6, ((1 if direction else 0) << 7) | spd)
        return True

    def stop_all(self):
        try:
            self._send(ADDR_PAN, 0xF7)
            time.sleep_ms(INTER_CMD_MS)
            self._send(ADDR_TILT, 0xF7)
            self.last = {}
        except Exception:
            pass

    def close(self):
        self.stop_all()
        time.sleep_ms(50)
        try:
            self.u.deinit()
        except Exception:
            pass


# ==========================================================
# LASER
# ==========================================================

class Laser:
    """Mac dinh TAT. Chi ban khi armed VA duoc goi fire()."""

    def __init__(self):
        self.pwm = None
        self.gpio = None
        self.mode = None
        self._reported = False
        self.firing = False
        self.t_start = 0
        self.t_last_end = 0
        self._safe_gpio()

    def _safe_gpio(self):
        # Ep chan ve muc THAP = laser tat.
        # Da xac nhan bang thuc nghiem: chan tha noi = BAN,
        # nen muc thap moi la trang thai an toan.
        try:
            f = FPIOA()
            f.set_function(LASER_PIN, getattr(FPIOA, "GPIO%d" % LASER_PIN))
            Pin(LASER_PIN, Pin.OUT).off()
        except Exception as e:
            print("!!! Khong dua duoc chan laser ve muc an toan:", e)

    def _pwm_on(self, duty):
        # Chu ky ham PWM() khac nhau giua cac ban firmware. Tai lieu ghi
        # PWM(ch, freq, duty, enable=False) nhung firmware v1.8 bao
        # "extra positional arguments given". Nen thu lan luot, dung dang nao
        # chay duoc; het cach thi ha xuong GPIO bat/tat (100% cong suat).
        f = FPIOA()
        try:
            f.set_function(LASER_PIN, getattr(FPIOA, "PWM%d" % LASER_PWM_CH))
        except Exception as e:
            print("!!! Khong mux duoc chan sang PWM:", e)

        attempts = (
            ("PWM(ch, freq, duty, enable=True)",
             lambda: PWM(LASER_PWM_CH, LASER_FREQ, duty, enable=True)),
            ("PWM(ch, freq, duty)",
             lambda: PWM(LASER_PWM_CH, LASER_FREQ, duty)),
            ("PWM(ch, freq)",
             lambda: PWM(LASER_PWM_CH, LASER_FREQ)),
            ("PWM(ch)",
             lambda: PWM(LASER_PWM_CH)),
        )

        for ten, tao in attempts:
            try:
                p = tao()
            except Exception:
                continue

            # Firmware v1.8 KHONG co PWM.enable() - no bao thang:
            #   "PWM.enable() is not supported. Please use PWM.freq()
            #    and PWM.duty() instead"
            # PWM tu phat ngay khi dat freq() roi duty(). Thu tu quan trong.
            ket_qua = []
            for nhan, goi in (("freq", lambda: p.freq(LASER_FREQ)),
                              ("duty", lambda: p.duty(duty))):
                try:
                    goi()
                    ket_qua.append(nhan + "=OK")
                except Exception as e:
                    ket_qua.append("%s=LOI(%s)" % (nhan, e))

            self.pwm = p
            self.mode = "PWM"
            if not self._reported:
                print(">>> PWM dung dang:", ten)
                print(">>> Cau hinh PWM:", " | ".join(ket_qua))
                self._reported = True
            return

        # --- Du phong: khong dung duoc PWM thi bat GPIO muc cao ---
        try:
            f.set_function(LASER_PIN, getattr(FPIOA, "GPIO%d" % LASER_PIN))
            self.gpio = Pin(LASER_PIN, Pin.OUT)
            self.gpio.on()
            self.pwm = None
            self.mode = "GPIO"
            if not self._reported:
                print(">>> KHONG dung duoc PWM -> chuyen sang GPIO BAT/TAT")
                print(">>> LUU Y: che do nay chay 100% cong suat, khong phai",
                      LASER_POWER, "%")
                self._reported = True
        except Exception as e:
            print("!!! Khong bat duoc laser bang cach nao:", e)
            self.mode = None

    def fire(self):
        if not LASER_ARMED or self.firing:
            return False
        if time.time() - self.t_last_end < COOLDOWN_SEC:
            return False
        self._pwm_on(LASER_POWER)
        self.firing = True
        self.t_start = time.time()
        print(">>> LASER FIRE")
        return True

    def update(self):
        # Goi moi frame: tu tat sau FIRE_SECONDS
        if self.firing and time.time() - self.t_start >= FIRE_SECONDS:
            self.off()
            return True
        return False

    def off(self):
        # Tat theo dung che do dang dung, roi VAN ep chan ve muc thap
        # bang GPIO - lop cuoi cung khong phu thuoc PWM co hoat dong hay khong.
        if self.pwm is not None:
            # duty(0) la cach tat dung tren firmware nay (khong co enable()).
            try:
                self.pwm.duty(0)
            except Exception:
                pass
            self.pwm = None
        if self.gpio is not None:
            try:
                self.gpio.off()
            except Exception:
                pass
            self.gpio = None
        if self.firing:
            self.t_last_end = time.time()
        self.firing = False
        self._safe_gpio()

    def elapsed(self):
        return time.time() - self.t_start if self.firing else 0


# ==========================================================
# YOLO
# ==========================================================

class Detector(AIBase):
    def __init__(self):
        super().__init__(KMODEL_PATH, MODEL_INPUT, [CAM_W, CAM_H], 0)
        self.labels = LABELS
        self.model_input_size = MODEL_INPUT
        self.rgb888p_size = [ALIGN_UP(CAM_W, 16), CAM_H]
        self.display_size = [ALIGN_UP(CAM_W, 16), CAM_H]
        self.debug_mode = 0
        self.color_four = get_colors(len(LABELS))
        self.ai2d = Ai2d(0)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT, nn.ai2d_format.NCHW_FMT,
                                 np.uint8, np.uint8)

    def config_preprocess(self, sz=None):
        with ScopedTiming("pre", 0):
            s = sz if sz else self.rgb888p_size
            top, bot, left, right, self.scale = letterbox_pad_param(
                self.rgb888p_size, self.model_input_size)
            self.ai2d.pad([0, 0, 0, 0, top, bot, left, right], 0, [128, 128, 128])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build([1, 3, s[1], s[0]],
                            [1, 3, self.model_input_size[1], self.model_input_size[0]])

    def postprocess(self, results):
        with ScopedTiming("post", 0):
            r = results[0][0].transpose()
            return aidemo.yolov8_det_postprocess(
                r.copy(),
                [self.rgb888p_size[1], self.rgb888p_size[0]],
                [self.model_input_size[1], self.model_input_size[0]],
                [self.display_size[1], self.display_size[0]],
                len(self.labels), CONF_THRESH, NMS_THRESH, MAX_BOXES)


# KHONG tu dinh nghia hwc2chw o day.
# libs/Utils.py tren the SD da co san ham nay (file mau ai_uvc_soft_decode.py
# dung no truc tiep), va no da duoc nap qua "from libs.Utils import *".
# Tu viet lai bang a.transpose((2,0,1)) se hong: ulab chi ho tro transpose()
# khong tham so -> loi "takes 1 positional arguments but 2 were given".


def pick_nearest(dets):
    # Chon box co tam gan tam khung hinh nhat
    if not dets or len(dets[0]) == 0:
        return None
    best = None
    best_d = 1e9
    for i in range(len(dets[0])):
        x, y, w, h = dets[0][i]
        cx = x + w / 2.0
        cy = y + h / 2.0
        d = math.sqrt((cx - CENTER_X) ** 2 + (cy - CENTER_Y) ** 2)
        if d < best_d:
            best_d = d
            best = (int(x), int(y), int(w), int(h), cx, cy, dets[2][i])
    return best


# ==========================================================
# CHINH
# ==========================================================

motors = None
laser = None
det = None
uvc_on = False

try:
    laser = Laser()
    print("Laser o trang thai AN TOAN.  ARMED =", LASER_ARMED)

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
        raise Exception("KHONG THAY WEBCAM")

    ok, _ = UVC.select_video_mode(UVC.video_mode(CAM_W, CAM_H, UVC.FOURCC_MJPEG, 30))
    print("Chon mode 640x480@30 MJPEG ->", ok)
    if not ok:
        raise Exception("WEBCAM KHONG NHAN MODE")

    det = Detector()
    det.config_preprocess()
    print("YOLO san sang:", KMODEL_PATH)

    motors = Motors()
    motors.enable(True)
    print("Motor san sang.")

    UVC.start(cvt=False)
    uvc_on = True

    clock = time.clock()
    ema_x = 0
    ema_y = 0
    lock_since = None
    bad_frames = 0

    while True:
        clock.tick()
        try:
            img = UVC.snapshot()
        except Exception:
            continue
        if img is None:
            continue

        # Giai ma JPEG co the that bai - frame hong qua USB la chuyen binh thuong
        try:
            img = img.to_rgb888()
        except Exception:
            bad_frames += 1
            try:
                img.__del__()
            except Exception:
                pass
            continue

        try:
            chw = hwc2chw(img.to_numpy_ref())
            dets = det.run(chw)
            target = pick_nearest(dets)

            # ---- dieu khien motor ----
            if target is None:
                motors.speed(ADDR_PAN, 0, 0)
                motors.speed(ADDR_TILT, 0, 0)
                lock_since = None
                ema_x = 0
                ema_y = 0
            else:
                x, y, w, h, cx, cy, score = target
                ex = int(cx - CENTER_X)
                ey = int(cy - CENTER_Y)

                # loc thong thap chong rung
                ema_x = (EMA_NUM * ex + (EMA_DEN - EMA_NUM) * ema_x) // EMA_DEN
                ema_y = (EMA_NUM * ey + (EMA_DEN - EMA_NUM) * ema_y) // EMA_DEN

                in_x = abs(ema_x) <= DEADZONE_X
                in_y = abs(ema_y) <= DEADZONE_Y

                if in_x:
                    motors.speed(ADDR_PAN, 0, 0)
                else:
                    s = max(1, min(MAX_SPEED_PAN, int(abs(ema_x) * GAIN_X)))
                    motors.speed(ADDR_PAN, 0 if ema_x > 0 else 1, s)

                time.sleep_ms(INTER_CMD_MS)

                if in_y:
                    motors.speed(ADDR_TILT, 0, 0)
                else:
                    s = max(1, min(MAX_SPEED_TILT, int(abs(ema_y) * GAIN_Y)))
                    motors.speed(ADDR_TILT, 1 if ema_y > 0 else 0, s)

                # ---- logic ban laser ----
                if in_x and in_y:
                    if lock_since is None:
                        lock_since = time.time()
                    elif time.time() - lock_since >= LOCK_SECONDS:
                        laser.fire()
                else:
                    lock_since = None

                # ve khung + duong noi toi tam
                img.draw_rectangle(x, y, w, h, color=(255, 0, 0), thickness=3)
                img.draw_line(CENTER_X, CENTER_Y, int(cx), int(cy),
                              color=(0, 255, 255), thickness=2)
                img.draw_string_advanced(x, max(0, y - 34), 28,
                                         "grass %.2f" % score, color=(255, 0, 0))

            laser.update()

            # ---- overlay ----
            img.draw_cross(CENTER_X, CENTER_Y, color=(0, 255, 0), size=18, thickness=2)
            img.draw_rectangle(CENTER_X - DEADZONE_X, CENTER_Y - DEADZONE_Y,
                               DEADZONE_X * 2, DEADZONE_Y * 2,
                               color=(0, 255, 0), thickness=1)

            if laser.firing:
                st = "LASER FIRING %.1fs" % laser.elapsed()
                col = (255, 0, 0)
            elif not LASER_ARMED:
                if lock_since is not None and time.time() - lock_since >= LOCK_SECONDS:
                    st = "SE BAN (chay kho)"
                    col = (255, 160, 0)
                else:
                    st = "LASER TAT (chay kho)"
                    col = (140, 140, 140)
            else:
                st = "LASER ARMED"
                col = (255, 160, 0)

            img.draw_string_advanced(8, 6, 26, st, color=col)
            img.draw_string_advanced(8, 38, 22,
                                     "FPS:%.1f  bad:%d" % (clock.fps(), bad_frames),
                                     color=(255, 255, 0))
            Display.show_image(img)

        except Exception as e:
            print("Loi xu ly frame (bo qua):", e)
        finally:
            try:
                img.__del__()
            except Exception:
                pass
            gc.collect()

except KeyboardInterrupt:
    print("\nNguoi dung dung.")
except BaseException as e:
    print(">>> LOI:")
    sys.print_exception(e)
finally:
    # THU TU BAT BUOC: laser TAT truoc, roi moi den motor
    if laser is not None:
        laser.off()
        print("Laser da tat.")
    if motors is not None:
        motors.close()
        print("Motor da dung.")
    if uvc_on:
        UVC.stop()
    time.sleep_ms(100)
    if det is not None:
        try:
            det.deinit()
        except Exception:
            pass
    Display.deinit()
    print("Da giai phong het.")
