
LOG_ENABLED   = True
LOG_PATH      = "/sdcard/run_log.txt"
LOG_PATH_PREV = "/sdcard/run_log_prev.txt"
LOG_MAX_BYTES = 20000000
LOG_FLUSH_MS  = 1000

LASER_ARMED   = True
LASER_PIN     = 43
LASER_PWM_CH  = 1
LASER_FREQ    = 1000
LASER_POWER   = 100     # duty %
FIRE_SECONDS  = 15.0
LOCK_SECONDS  = 3.5     # time inside deadzone before firing
COOLDOWN_SEC  = 5.0
ARM_DELAY_SEC = 10

UART_TX, UART_RX = 11, 12
UART_BAUD = 115200
ADDR_PAN, ADDR_TILT = 0xE1, 0xE2
PAN_DAO_CHIEU = True    # replaced PAN motor turns the other way; flip its dir bit
MSTEP = 64  # must match driver menu
RPM_MOI_NAC = 30000.0 / (MSTEP * 200)

MAX_SPEED_PAN, MAX_SPEED_TILT = 8, 2
INTER_CMD_MS = 15
CMD_REFRESH_MS = 250      # resend even when unchanged; a lost stop must not latch motion
FRAME_FAIL_STOP = 2       # stop after this many consecutive missing/bad camera frames
BRAKE_SETTLE_MS = 450     # measured image delay is about 380 ms; wait before reversing

DO_MOI_NAC_GIAY = (30000.0 / (MSTEP * 200)) * 6

# TILT tracks without homing, camera stop detection, or a travel limit.
# goc_tilt below is only a relative open-loop estimate for display/logging.
CHO_VE_ZERO_SEC = 5     # driver settle pause, not a homing move

PAN_GIOI_HAN = 1138.0   # PAN behavior unchanged

DEADZONE_X = 25         # stop moving below this
DEADZONE_Y = 30         # must exceed delay x slowest step = 3 x 7.5 = 22.5 px

KHOI_DONG_X = 30        # start moving above this; hysteresis vs detect noise
KHOI_DONG_Y = 40        # start moving above this; hysteresis vs detect noise
GAIN_X = 0.035
GAIN_Y = 0.015          # conservative after the observed two-axis limit cycle

PX_MOI_NAC_X = 35.0     # larger value = stronger speed clamp near the target
PX_MOI_NAC_Y = 65.0     # includes camera delay + mechanical settling

GATE_NAC_X = 18.0       # gating radius per speed step; kept at old brake value
GATE_NAC_Y = 20.0       # gating radius per speed step; kept at old brake value

PX_KHUNG_NAC_X = 3.15   # measured travel per frame, NOT stopping distance
PX_KHUNG_NAC_Y = 4.96   # measured travel per frame, NOT stopping distance

VI_TRI_BAT = False       # 0xFD is open-loop and can overlap before delayed images arrive
XUNG_MOI_DO = (MSTEP * 200) / 360.0
XUNG_MOI_PX_X = 7.73    # measured pulses per pixel
XUNG_MOI_PX_Y = 4.94    # measured pulses per pixel

NGUONG_VI_TRI_X = 150
NGUONG_VI_TRI_Y = 120

VI_TRI_NAC = 6
VI_TRI_XUNG_GIAY = VI_TRI_NAC * (30000.0 / (MSTEP * 200)) / 60 * (MSTEP * 200)

VI_TRI_HE_SO = 0.85     # deliberate undershoot so a move never overshoots

VI_TRI_BIEN_MS = 60

V_DUNG_YEN = 6.0        # px/frame below this counts as target at rest
DUNG_YEN_KHUNG = 4
EMA_NUM, EMA_DEN = 7, 10
LOC_N = 1               # 1 = off; real detect noise is p99 15px, filter only adds delay

FF_BAT = False
FF_MAX_NAC = 8
V_EMA_NUM, V_EMA_DEN = 4, 10
V_NGUONG_PX = 4.0

KMODEL_PATH = "/sdcard/best_grass_320.kmodel"
LABELS = ["grass"]
MODEL_INPUT_SIZE = [320, 320]
RGB888P_SIZE = [640, 480]
CONFIDENCE_THRESHOLD = 0.5

CONF_TRACK = 0.65       # above the model's false-positive band
CONF_FIRE  = 0.75       # average over CONFIRM_M frames before firing

CONFIRM_N, CONFIRM_M = 3, 5

MAX_JUMP_PX = 120
MIN_HITS = 3
MAX_MISS = 5

LOCK_TOLERANCE_FRAMES = 3
NMS_THRESHOLD = 0.45
MAX_BOXES_NUM = 30

LCD_WIDTH  = 640
LCD_HEIGHT = 480

TO_IDE = False
WEBCAM_WAIT_MS = 30000
ERROR_LOG_PATH = "/sdcard/main_error.log"


import time, os, sys, gc, math
import image
import aidemo
import nncase_runtime as nn
import ulab.numpy as np
from machine import UART, FPIOA, Pin, PWM
from media.display import *
from media.media import *
from libs.AIBase import AIBase
from libs.AI2D import Ai2d
from libs.Utils import *

DISPLAY_WIDTH = ALIGN_UP(LCD_WIDTH, 16)
DISPLAY_HEIGHT = LCD_HEIGHT
OFFSET_X = max(0, (DISPLAY_WIDTH - RGB888P_SIZE[0]) // 2)
OFFSET_Y = max(0, (DISPLAY_HEIGHT - RGB888P_SIZE[1]) // 2)
CENTER_X = RGB888P_SIZE[0] // 2
CENTER_Y = RGB888P_SIZE[1] // 2


class ObjectDetectionApp(AIBase):
    def __init__(self, kmodel_path, labels, model_input_size, max_boxes_num,
                 confidence_threshold=0.5, nms_threshold=0.45,
                 rgb888p_size=[224, 224], display_size=[1920, 1080], debug_mode=0):
        super().__init__(kmodel_path, model_input_size, rgb888p_size, debug_mode)
        self.kmodel_path = kmodel_path
        self.labels = labels
        self.model_input_size = model_input_size
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.max_boxes_num = max_boxes_num
        self.rgb888p_size = [ALIGN_UP(rgb888p_size[0], 16), rgb888p_size[1]]
        self.display_size = [ALIGN_UP(display_size[0], 16), display_size[1]]
        self.debug_mode = debug_mode
        self.color_four = get_colors(len(self.labels))
        self.x_factor = float(self.rgb888p_size[0]) / self.model_input_size[0]
        self.y_factor = float(self.rgb888p_size[1]) / self.model_input_size[1]
        self.ai2d = Ai2d(debug_mode)
        self.ai2d.set_ai2d_dtype(nn.ai2d_format.NCHW_FMT, nn.ai2d_format.NCHW_FMT,
                                 np.uint8, np.uint8)

    def config_preprocess(self, input_image_size=None):
        with ScopedTiming("set preprocess config", self.debug_mode > 0):
            ai2d_input_size = input_image_size if input_image_size else self.rgb888p_size
            top, bottom, left, right, self.scale = letterbox_pad_param(
                self.rgb888p_size, self.model_input_size)
            self.ai2d.pad([0, 0, 0, 0, top, bottom, left, right], 0, [128, 128, 128])
            self.ai2d.resize(nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel)
            self.ai2d.build(
                [1, 3, ai2d_input_size[1], ai2d_input_size[0]],
                [1, 3, self.model_input_size[1], self.model_input_size[0]])

    def postprocess(self, results):
        with ScopedTiming("postprocess", self.debug_mode > 0):
            new_result = results[0][0].transpose()
            return aidemo.yolov8_det_postprocess(
                new_result.copy(),
                [self.rgb888p_size[1], self.rgb888p_size[0]],
                [self.model_input_size[1], self.model_input_size[0]],
                [self.display_size[1], self.display_size[0]],
                len(self.labels), self.confidence_threshold,
                self.nms_threshold, self.max_boxes_num)

    def draw_result(self, img, dets):
        with ScopedTiming("display_draw", self.debug_mode > 0):
            try:
                if not dets or len(dets) < 3:
                    return
                n = min(len(dets[0]), len(dets[1]), len(dets[2]))
            except Exception:
                return
            if n:
                for i in range(n):
                    x, y, w, h = map(lambda v: int(round(v, 0)), dets[0][i])
                    img.draw_rectangle(x, y, w, h,
                                       color=self.color_four[dets[1][i]], thickness=3)
                    img.draw_string_advanced(
                        x, max(0, y - 34), 28,
                        " " + self.labels[dets[1][i]] + " " + str(round(dets[2][i], 2)),
                        color=self.color_four[dets[1][i]])


def hwc2chw(img_np_hwc):
    shape = img_np_hwc.shape
    img_tmp = img_np_hwc.reshape((shape[0] * shape[1], shape[2]))
    img_trans = img_tmp.transpose()
    img_tmp = img_trans.copy()
    return img_tmp.reshape((shape[2], shape[0], shape[1]))


class Tracker:
    """Track one single target across frames; reject jumps and noise."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.gate = MAX_JUMP_PX
        self.n_det = 0
        self.n_loc = 0
        self.alive = False
        self.cx = 0.0
        self.cy = 0.0
        self.w = 0
        self.h = 0
        self.conf = 0.0
        self.hits = 0
        self.miss = 0
        self.lich_su = []
        self.conf_hist = []

    def _ghi(self, co):
        self.lich_su.append(1 if co else 0)
        if len(self.lich_su) > CONFIRM_M:
            self.lich_su.pop(0)

    def _truot(self):
        self._ghi(False)
        self.miss += 1
        if self.miss > MAX_MISS:
            self.reset()

    def cap_nhat(self, dets, dich_du_kien=0.0):
        """dich_du_kien: expected image shift from our own last move."""
        ung_vien = []
        boxes = []
        scores = []
        try:
            if dets and len(dets) >= 3:
                boxes = dets[0] if dets[0] is not None else []
                scores = dets[2] if dets[2] is not None else []
            self.n_det = len(boxes)
            n = min(len(boxes), len(scores))
        except Exception:
            self.n_det = 0
            n = 0
        for i in range(n):
            try:
                c = float(scores[i])
                if c < CONF_TRACK:
                    continue
                x, y, w, h = boxes[i]
                ung_vien.append((x + w / 2.0, y + h / 2.0, w, h, c))
            except Exception:
                # A partially formed result must behave like a missed detection,
                # never terminate the autonomous main loop.
                continue
        self.n_loc = len(ung_vien)

        if not ung_vien:
            self._truot()
            return

        if self.alive:
            best = None
            best_d = MAX_JUMP_PX + dich_du_kien
            self.gate = best_d
            for u in ung_vien:
                d = math.sqrt((u[0] - self.cx) ** 2 + (u[1] - self.cy) ** 2)
                if d < best_d:
                    best_d = d
                    best = u
            if best is None:
                self._truot()
                return
        else:
            best = None
            best_d = 1e9
            for u in ung_vien:
                d = (u[0] - CENTER_X) ** 2 + (u[1] - CENTER_Y) ** 2
                if d < best_d:
                    best_d = d
                    best = u

        self.alive = True
        self.miss = 0
        self.hits += 1
        self.cx, self.cy, self.w, self.h, self.conf = best
        self._ghi(True)
        self.conf_hist.append(best[4])
        if len(self.conf_hist) > CONFIRM_M:
            self.conf_hist.pop(0)

    def xac_nhan(self):
        """True when the track is confirmed enough to drive motors."""
        return (self.alive and self.hits >= MIN_HITS
                and sum(self.lich_su) >= CONFIRM_N)

    def conf_tb(self):
        if not self.conf_hist:
            return 0.0
        return sum(self.conf_hist) / len(self.conf_hist)


def show_status(title, detail=""):
    print(title, detail)
    status_img = None
    try:
        status_img = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.RGB888)
        status_img.clear()
        status_img.draw_string_advanced(12, 20, 28, title, color=(0, 255, 0))
        status_img.draw_string_advanced(12, 65, 22, detail[:48], color=(255, 255, 0))
        Display.show_image(status_img)
    finally:
        if status_img is not None:
            status_img.__del__()


class Log:
    """CSV logger on SD card; flushes periodically, not per line."""

    def __init__(self):
        self.f = None
        self.n = 0
        self.tran = False
        self.t_flush = 0
        self.t0 = time.ticks_ms()
        if not LOG_ENABLED:
            return
        try:
            try:
                os.remove(LOG_PATH_PREV)
            except Exception:
                pass
            try:
                os.rename(LOG_PATH, LOG_PATH_PREV)
            except Exception:
                pass
            self.f = open(LOG_PATH, "w")
        except Exception as e:
            print("Khong mo duoc log:", e)
            self.f = None

    def _raw(self, s):
        if self.f is None or self.tran:
            return
        try:
            self.f.write(s)
            self.n += len(s)
            if self.n >= LOG_MAX_BYTES:
                self.f.write("\n[LOG DAY - ngung ghi]\n")
                self.f.flush()
                self.tran = True
        except Exception:
            self.f = None

    def _giay(self):
        return time.ticks_diff(time.ticks_ms(), self.t0) / 1000.0

    def su_kien(self, s):
        """Important event: write and flush immediately."""
        print(s)
        self._raw("# %8.2f  %s\n" % (self._giay(), s))
        self.flush()

    def ghi(self, s):
        """Ordinary line: no flush."""
        self._raw("# %8.2f  %s\n" % (self._giay(), s))

    def csv(self, *cot):
        self._raw(",".join(str(c) for c in cot) + "\n")

    def dinh_ky(self):
        """Call every frame; flushes on its own schedule."""
        if self.f is None:
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self.t_flush) >= LOG_FLUSH_MS:
            self.t_flush = now
            self.flush()

    def flush(self):
        if self.f is None:
            return
        try:
            self.f.flush()
        except Exception:
            pass

    def close(self):
        if self.f is None:
            return
        try:
            self.f.write("# --- het ---\n")
            self.f.flush()
            self.f.close()
        except Exception:
            pass
        self.f = None


log = Log()


def save_error(stage, exc):
    print(">>> LOI TAI:", stage)
    sys.print_exception(exc)
    try:
        log.su_kien("LOI TAI [%s] -> %s: %s"
                    % (stage, type(exc).__name__, exc))
    except Exception:
        pass
    try:
        with open(ERROR_LOG_PATH, "w") as log:
            log.write("main.py - " + stage + "\n")
            log.write("Model: " + KMODEL_PATH + "\n")
            sys.print_exception(exc, log)
        print("Da luu loi:", ERROR_LOG_PATH)
    except Exception as log_error:
        print("Khong ghi duoc log:", log_error)


class Motors:
    def __init__(self):
        f = FPIOA()
        f.set_function(UART_TX, FPIOA.UART2_TXD)
        f.set_function(UART_RX, FPIOA.UART2_RXD)
        self.u = UART(UART.UART2, baudrate=UART_BAUD, bits=UART.EIGHTBITS,
                      parity=UART.PARITY_NONE, stop=UART.STOPBITS_ONE)
        self.last = {}
        self.last_ms = {}

    def _send(self, addr, *data):
        fr = [addr] + list(data)
        fr.append(sum(fr) & 0xFF)
        self.u.write(bytes(fr))

    def enable(self, on=True):
        self._send(ADDR_PAN, 0xF3, 0x01 if on else 0x00)
        time.sleep_ms(INTER_CMD_MS)
        self._send(ADDR_TILT, 0xF3, 0x01 if on else 0x00)

    def speed(self, addr, direction, spd):
        spd = max(0, min(127, int(spd)))
        if PAN_DAO_CHIEU and addr == ADDR_PAN and spd > 0:
            direction = not direction   # stop frame stays the proven F6 00
        key = (direction, spd)
        now = time.ticks_ms()
        last_at = self.last_ms.get(addr, None)
        if (self.last.get(addr) == key and last_at is not None
                and time.ticks_diff(now, last_at) < CMD_REFRESH_MS):
            return False
        self._send(addr, 0xF6, ((1 if direction else 0) << 7) | spd)
        # Cache only after UART.write returned. Refreshing periodically makes a
        # dropped direction/stop frame self-healing without reading the shared bus.
        self.last[addr] = key
        self.last_ms[addr] = now
        return True

    def move(self, addr, direction, nac, xung):
        """0xFD: move exactly `xung` pulses then stop by itself."""
        if PAN_DAO_CHIEU and addr == ADDR_PAN:
            direction = not direction
        val = ((1 if direction else 0) << 7) | (int(nac) & 0x7F)
        p = int(xung) & 0xFFFFFFFF
        self._send(addr, 0xFD, val,
                   (p >> 24) & 0xFF, (p >> 16) & 0xFF,
                   (p >> 8) & 0xFF, p & 0xFF)
        self.last[addr] = None
        self.last_ms.pop(addr, None)

    def stop_all(self):
        try:
            self._send(ADDR_PAN, 0xF6, 0x00)
            time.sleep_ms(INTER_CMD_MS)
            self._send(ADDR_TILT, 0xF6, 0x00)
            self.last = {}
            self.last_ms = {}
        except Exception:
            pass

    def close(self):
        self.stop_all()
        time.sleep_ms(50)
        try:
            self.u.deinit()
        except Exception:
            pass


class Laser:
    def __init__(self):
        self.pwm = None
        self.firing = False
        self.t_start = 0
        self.t_last_end = 0
        self.safe_state()

    def safe_state(self):
        try:
            f = FPIOA()
            f.set_function(LASER_PIN, getattr(FPIOA, "GPIO%d" % LASER_PIN))
            Pin(LASER_PIN, Pin.OUT).off()
        except Exception as e:
            print("!!! Khong ep duoc chan laser ve muc an toan:", e)

    def fire(self, allowed):
        if not (LASER_ARMED and allowed) or self.firing:
            return False
        if time.time() - self.t_last_end < COOLDOWN_SEC:
            return False
        try:
            f = FPIOA()
            f.set_function(LASER_PIN, getattr(FPIOA, "PWM%d" % LASER_PWM_CH))
            p = PWM(LASER_PWM_CH)
            p.freq(LASER_FREQ)
            p.duty(LASER_POWER)
            self.pwm = p
        except Exception as e:
            print("!!! Khong bat duoc laser:", e)
            self.safe_state()
            return False
        self.firing = True
        self.t_start = time.time()
        log.su_kien(">>> LASER FIRE duty=%d trong %.1fs"
                    % (LASER_POWER, FIRE_SECONDS))
        return True

    def update(self):
        if self.firing and time.time() - self.t_start >= FIRE_SECONDS:
            self.off()
            return True
        return False

    def off(self):
        if self.pwm is not None:
            try:
                self.pwm.duty(0)
            except Exception:
                pass
            self.pwm = None
        if self.firing:
            self.t_last_end = time.time()
        self.firing = False
        self.safe_state()

    def elapsed(self):
        return time.time() - self.t_start if self.firing else 0


ob_det = None
motors = None
laser = None
started = False
display_ready = False
stage = "KHOI TAO LCD"

log.ghi("=" * 60)
log.ghi("WEEDLASER K230 - bat dau")
log.ghi("Mstep %d  (1 nac = %.3f RPM)" % (MSTEP, RPM_MOI_NAC))
log.ghi("MAX_SPEED  PAN %d  TILT %d" % (MAX_SPEED_PAN, MAX_SPEED_TILT))
log.ghi("GAIN       X %.4f  Y %.4f" % (GAIN_X, GAIN_Y))
log.ghi("DEADZONE   X %d  Y %d" % (DEADZONE_X, DEADZONE_Y))
log.ghi("PHANH      px/nac X %.1f  Y %.1f" % (PX_MOI_NAC_X, PX_MOI_NAC_Y))
log.ghi("LASER      armed=%s pin=%d ch=%d duty=%d fire=%.1fs arm_delay=%ds"
        % (LASER_ARMED, LASER_PIN, LASER_PWM_CH, LASER_POWER,
           FIRE_SECONDS, ARM_DELAY_SEC))
log.ghi("MODEL      %s  labels=%s" % (KMODEL_PATH, LABELS))
log.ghi("PANEL      %dx%d   anh %dx%d"
        % (DISPLAY_WIDTH, DISPLAY_HEIGHT, RGB888P_SIZE[0], RGB888P_SIZE[1]))
log.ghi("=" * 60)
log.ghi("Cot CSV: t_giay,fps,co_muc_tieu,err_x,err_y,nac_x,nac_y,"
        "laser,bo_frame,box_w,box_h,conf,conf_tb,hits,khoa_giay,"
        "n_det,n_loc,gate,goc_tilt,goc_pan,vt_x,vt_y,tho_x,tho_y,chan_x,chan_y")
log.ghi("  chan_x/y   : 0=binh thuong; TILT khong chan huong")
log.ghi("TILT tracking tu do: HOME=OFF, flow stop=OFF, gioi han goc=OFF")
log.ghi("  co_muc_tieu: 1=thay co, 0=khong")
log.ghi("  err_x/err_y: sai so SAU median%d + EMA %d/%d - la cai dieu khien dung"
        % (LOC_N, EMA_NUM, EMA_DEN))
log.ghi("  tho_x/tho_y: sai so THO chua loc - dung de do lai nhieu detect")
log.ghi("  nac_*      : nac toc do dang ra lenh (0 = da dung)")
log.ghi("  laser      : 1=dang ban")
log.ghi("  bo_frame   : so frame JPEG loi bi bo tu lan ghi truoc")
log.ghi("  box_w/h    : kich thuoc box - de dat nguong loc kich thuoc")
log.ghi("  conf/conf_tb: tin cay khung nay / trung binh %d khung" % CONFIRM_M)
log.ghi("  hits       : so khung lien tuc da bam duoc muc tieu nay")
log.ghi("  n_det/n_loc: so box model tra ve / so con lai sau CONF_TRACK")
log.ghi("               chenh lech = so box bo loc da CHAN")
log.ghi("  gate       : ban kinh gating thuc te = %d + luong cum vua quay"
        % MAX_JUMP_PX)
log.ghi("  goc_tilt   : goc cong don TILT, DO O TRUC MOTOR, TUONG DOI tu luc cap nguon")
log.ghi("               gioi han mem TILT TAT; goc chi de hien thi")
log.ghi("  goc_pan    : goc cong don PAN, TUONG DOI tu luc cap nguon")
log.ghi("  vt_x/vt_y  : so XUNG cua lenh vi tri 0xFD gui trong khung nay")
log.ghi("               0 = khung do dung che do toc do (hoac dung yen)")
log.ghi("CHE DO LAI  vi_tri=%s  nguong X %d Y %d  he so %.2f  nac %d"
        % (VI_TRI_BAT, NGUONG_VI_TRI_X, NGUONG_VI_TRI_Y,
           VI_TRI_HE_SO, VI_TRI_NAC))
log.ghi("            chi ra lenh vi tri khi muc tieu dung yen: |dich| < %.1f px"
        % V_DUNG_YEN)
log.ghi("            trong %d khung LIEN TIEP, do o khung TRUC DANG DUNG IM"
        % DUNG_YEN_KHUNG)
log.ghi("  khoa_giay  : da giu trong deadzone bao lau (can %.1fs)"
        % LOCK_SECONDS)
log.ghi("LOC BOX    median %d khung tren sai so tho" % LOC_N)
log.ghi("LOC NHIEU  conf_track %.2f  conf_fire %.2f  %d/%d khung"
        % (CONF_TRACK, CONF_FIRE, CONFIRM_N, CONFIRM_M))
log.ghi("           gating %dpx  min_hits %d  max_miss %d"
        % (MAX_JUMP_PX, MIN_HITS, MAX_MISS))
log.flush()

try:
    Display.init(Display.ST7701, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT,
                 to_ide=TO_IDE)
    display_ready = True
    show_status("WEEDLASER K230", "Dang khoi dong...")

    stage = "KHOI TAO LASER (trang thai an toan)"
    laser = Laser()
    print("Laser o trang thai AN TOAN. ARMED =", LASER_ARMED)

    stage = "IMPORT UVC"
    from media.uvc import *

    stage = "KIEM TRA MODEL"
    model_size = os.stat(KMODEL_PATH)[6]
    if model_size <= 0:
        raise RuntimeError("File kmodel rong")
    log.su_kien("Model OK: %s (%d byte)" % (KMODEL_PATH, model_size))

    stage = "CHO WEBCAM"
    show_status("CHO WEBCAM USB", "640x480 MJPEG - toi da 30 giay")
    dev = None
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < WEBCAM_WAIT_MS:
        plugin, d = UVC.probe()
        if plugin:
            dev = d
            log.su_kien("Da thay webcam sau %d ms"
                        % time.ticks_diff(time.ticks_ms(), t0))
            break
        time.sleep_ms(200)
    if dev is None:
        raise RuntimeError("Khong thay webcam sau 30 giay")

    stage = "CHON MODE WEBCAM"
    succ, mode = UVC.select_video_mode(
        UVC.video_mode(RGB888P_SIZE[0], RGB888P_SIZE[1], UVC.FOURCC_MJPEG, 30))
    log.su_kien("Chon mode %dx%d@30 MJPEG -> %s"
                % (RGB888P_SIZE[0], RGB888P_SIZE[1], succ))
    if not succ:
        raise RuntimeError("Webcam khong nhan 640x480@30 MJPEG")

    stage = "NAP MODEL"
    show_status("DANG NAP YOLO", KMODEL_PATH.split("/")[-1])
    ob_det = ObjectDetectionApp(
        KMODEL_PATH,
        labels=LABELS,
        model_input_size=MODEL_INPUT_SIZE,
        max_boxes_num=MAX_BOXES_NUM,
        confidence_threshold=CONFIDENCE_THRESHOLD,
        nms_threshold=NMS_THRESHOLD,
        rgb888p_size=RGB888P_SIZE,
        display_size=RGB888P_SIZE,
        debug_mode=0,
    )
    stage = "CAU HINH AI2D"
    ob_det.config_preprocess()

    stage = "KHOI TAO MOTOR"
    show_status("KHOI TAO MOTOR", "PAN 0xE1 | TILT 0xE2")
    motors = Motors()
    motors.enable(True)

    stage = "CHO ON DINH"
    for _t in range(CHO_VE_ZERO_SEC, 0, -1):
        show_status("KHOI DONG",
                    "cho on dinh - con %ds" % _t)
        time.sleep(1)
    motors.speed(ADDR_TILT, 0, 0)
    motors.speed(ADDR_PAN, 0, 0)
    log.su_kien("Cho %ds. Goc cong don = 0 tai VI TRI LUC CAP NGUON "
                "(khong dung 0_Mode)." % CHO_VE_ZERO_SEC)
    print("Motor san sang.")

    stage = "BAT UVC"
    UVC.start(cvt=False)
    started = True
    show_status("SAN SANG", "Dang cho khung hinh dau tien...")

    log.su_kien("TILT tracking tu do: khong HOME, khong gioi han goc, khong do cu")
    show_status("SAN SANG", "TILT bam binh thuong - khong gioi han")

    clock = time.clock()
    ema_x = 0
    ema_y = 0
    tho_x = 0
    tho_y = 0
    loc_x = []
    loc_y = []
    lock_since = None
    consecutive_bad = 0
    warned = False
    show_ok = True
    sp_x = sp_y = 0
    ngoai_lien_tiep = 0
    tracker = Tracker()
    goc_tilt = 0.0
    goc_pan = 0.0
    chu_ky = 0.08
    ban_x = time.ticks_ms()
    ban_y = time.ticks_ms()
    sp_x_truoc = sp_y_truoc = 0
    chan = [0, 0]               # PAN state; TILT chan_y stays 0 for CSV compatibility
    thu_pha = [0, 0]            # legacy PAN state remains disabled/unchanged
    vt_x = vt_y = 0
    yen_x = yen_y = 0
    chay_x = chay_y = False
    raise_skip_x = raise_skip_y = False
    ex_truoc = None
    ey_truoc = None
    dich_cum_x = 0.0
    dich_cum_y = 0.0
    vx = 0.0
    vy = 0.0
    bo_frame = 0
    frame_fail = 0
    frame_fail_stopped = False
    co_muc_tieu_truoc = None
    t_boot = time.time()

    while True:
        clock.tick()
        _f = clock.fps()
        if _f > 1.0:
            chu_ky = 1.0 / _f
        img = None
        try:
            img = UVC.snapshot()
        except Exception:
            frame_fail += 1
            if frame_fail >= FRAME_FAIL_STOP and not frame_fail_stopped:
                motors.stop_all()
                sp_x = sp_y = 0
                dich_cum_x = dich_cum_y = 0.0
                frame_fail_stopped = True
                log.su_kien("WATCHDOG: mat frame camera -> dung ca hai motor")
            continue
        if img is None:
            frame_fail += 1
            if frame_fail >= FRAME_FAIL_STOP and not frame_fail_stopped:
                motors.stop_all()
                sp_x = sp_y = 0
                dich_cum_x = dich_cum_y = 0.0
                frame_fail_stopped = True
                log.su_kien("WATCHDOG: camera tra ve None -> dung ca hai motor")
            continue

        try:
            img = img.to_rgb888()
        except Exception:
            consecutive_bad += 1
            bo_frame += 1
            frame_fail += 1
            try:
                img.__del__()
            except Exception:
                pass
            if frame_fail >= FRAME_FAIL_STOP and not frame_fail_stopped:
                motors.stop_all()
                sp_x = sp_y = 0
                dich_cum_x = dich_cum_y = 0.0
                frame_fail_stopped = True
                log.su_kien("WATCHDOG: loi giai ma anh -> dung ca hai motor")
            if consecutive_bad >= 30 and not warned:
                log.su_kien("CANH BAO: %d frame JPEG loi LIEN TIEP"
                            " -> kiem tra cap USB / hub co nguon rieng"
                            % consecutive_bad)
                warned = True
            continue
        frame_fail = 0
        frame_fail_stopped = False
        consecutive_bad = 0
        warned = False

        try:
            stage = "DOI ANH HWC -> CHW"
            img_np_hwc = img.to_numpy_ref()
            img_np_chw = hwc2chw(img_np_hwc)

            stage = "YOLO INFERENCE / POSTPROCESS"
            res = ob_det.run(img_np_chw)

            stage = "BAM MUC TIEU"
            armed_now = (time.time() - t_boot) >= ARM_DELAY_SEC
            sp_x_truoc, sp_y_truoc = sp_x, sp_y
            vt_x = vt_y = 0
            dich_du_kien = sp_x * GATE_NAC_X + sp_y * GATE_NAC_Y
            tracker.cap_nhat(res, dich_du_kien)
            target = ((tracker.cx, tracker.cy)
                      if tracker.xac_nhan() else None)

            if target is None:
                motors.speed(ADDR_PAN, 0, 0)
                time.sleep_ms(INTER_CMD_MS)
                motors.speed(ADDR_TILT, 0, 0)
                lock_since = None
                ngoai_lien_tiep = 0
                ema_x = 0
                ema_y = 0

                tho_x = 0
                tho_y = 0
                loc_x = []
                loc_y = []
                ex_truoc = None
                ey_truoc = None
                yen_x = yen_y = 0
                dich_cum_x = 0.0
                dich_cum_y = 0.0
                vx = 0.0
                vy = 0.0
                in_x = in_y = False
                chay_x = chay_y = False
                sp_x = sp_y = 0
                ban_x = ban_y = time.ticks_ms()
            else:
                cx, cy = target
                tho_x = int(cx - CENTER_X)
                tho_y = int(cy - CENTER_Y)

                loc_x.append(tho_x)
                loc_y.append(tho_y)
                if len(loc_x) > LOC_N:
                    loc_x.pop(0)
                if len(loc_y) > LOC_N:
                    loc_y.pop(0)
                ex = sorted(loc_x)[len(loc_x) // 2]
                ey = sorted(loc_y)[len(loc_y) // 2]
                ema_x = (EMA_NUM * ex + (EMA_DEN - EMA_NUM) * ema_x) // EMA_DEN
                ema_y = (EMA_NUM * ey + (EMA_DEN - EMA_NUM) * ema_y) // EMA_DEN

                if ex_truoc is None:
                    vx = 0.0
                    vy = 0.0
                else:
                    vx_tho = (ex - ex_truoc) - dich_cum_x
                    vy_tho = (ey - ey_truoc) - dich_cum_y
                    vx = (V_EMA_NUM * vx_tho
                          + (V_EMA_DEN - V_EMA_NUM) * vx) / V_EMA_DEN
                    vy = (V_EMA_NUM * vy_tho
                          + (V_EMA_DEN - V_EMA_NUM) * vy) / V_EMA_DEN
                x_ranh = (sp_x_truoc == 0
                          and time.ticks_diff(ban_x, time.ticks_ms()) <= 0)
                y_ranh = (sp_y_truoc == 0
                          and time.ticks_diff(ban_y, time.ticks_ms()) <= 0)
                if ex_truoc is not None and x_ranh:
                    yen_x = yen_x + 1 if abs(ex - ex_truoc) < V_DUNG_YEN else 0
                else:
                    yen_x = 0
                if ey_truoc is not None and y_ranh:
                    yen_y = yen_y + 1 if abs(ey - ey_truoc) < V_DUNG_YEN else 0
                else:
                    yen_y = 0

                ex_truoc = ex
                ey_truoc = ey

                if abs(ema_x) > KHOI_DONG_X:
                    chay_x = True
                elif abs(ema_x) <= DEADZONE_X:
                    chay_x = False
                if abs(ema_y) > KHOI_DONG_Y:
                    chay_y = True
                elif abs(ema_y) <= DEADZONE_Y:
                    chay_y = False
                in_x = not chay_x
                in_y = not chay_y

                if laser.firing:
                    motors.speed(ADDR_PAN, 0, 0)
                    time.sleep_ms(INTER_CMD_MS)
                    motors.speed(ADDR_TILT, 0, 0)
                    sp_x = sp_y = 0
                    dich_cum_x = dich_cum_y = 0.0
                    ban_x = ban_y = time.ticks_ms()
                elif time.ticks_diff(ban_x, time.ticks_ms()) > 0:
                    motors.speed(ADDR_PAN, 0, 0)
                    sp_x = 0
                    dich_cum_x = 0.0
                elif in_x:
                    motors.speed(ADDR_PAN, 0, 0)
                    if sp_x_truoc > 0:
                        ban_x = time.ticks_add(time.ticks_ms(), BRAKE_SETTLE_MS)
                    sp_x = 0
                    dich_cum_x = 0.0
                elif (VI_TRI_BAT and abs(ema_x) <= NGUONG_VI_TRI_X
                      and yen_x >= DUNG_YEN_KHUNG):
                    if sp_x_truoc > 0:
                        motors.speed(ADDR_PAN, 0, 0)
                        ban_x = time.ticks_add(time.ticks_ms(), 200)
                        sp_x = 0
                        dich_cum_x = 0.0
                        raise_skip_x = True
                    else:
                        raise_skip_x = False
                    pan_duong = ema_x > 0
                    xung = int(abs(ema_x) * XUNG_MOI_PX_X * VI_TRI_HE_SO)
                    con_lai_p = ((PAN_GIOI_HAN - goc_pan) if pan_duong
                                 else (goc_pan + PAN_GIOI_HAN))
                    xung = min(xung, max(0, int(con_lai_p * XUNG_MOI_DO)))
                    if raise_skip_x:
                        xung = 0
                    if xung >= 20:
                        motors.move(ADDR_PAN, 0 if pan_duong else 1,
                                    VI_TRI_NAC, xung)
                        vt_x = xung
                        ban_x = time.ticks_add(
                            time.ticks_ms(),
                            int(xung / VI_TRI_XUNG_GIAY * 1000) + VI_TRI_BIEN_MS)
                        goc_pan += (1 if pan_duong else -1) * xung / XUNG_MOI_DO
                    sp_x = 0
                    dich_cum_x = 0.0
                else:
                    huong_x = 1 if ema_x > 0 else -1
                    ff_x = 0.0
                    if FF_BAT and abs(vx) >= V_NGUONG_PX:
                        ff_x = (vx / PX_KHUNG_NAC_X) * huong_x
                        ff_x = max(-FF_MAX_NAC, min(FF_MAX_NAC, ff_x))
                    sp_x = int(abs(ema_x) * GAIN_X + ff_x)
                    sp_x = max(1, min(MAX_SPEED_PAN, sp_x))

                    v_ra_xa = (vx * huong_x) if FF_BAT else 0.0
                    ngan_sach = (abs(ema_x) - DEADZONE_X) + max(0.0, v_ra_xa)
                    s_phanh = int(ngan_sach / PX_MOI_NAC_X)
                    sp_x = max(1, min(sp_x, s_phanh))

                    pan_duong = ema_x > 0
                    con_lai_p = ((PAN_GIOI_HAN - goc_pan) if pan_duong
                                 else (goc_pan + PAN_GIOI_HAN))
                    buoc_mot_nac = DO_MOI_NAC_GIAY * chu_ky
                    sp_bien = int(con_lai_p / buoc_mot_nac) if buoc_mot_nac > 0 else 0
                    if sp_bien < sp_x:
                        sp_x = max(0, sp_bien)

                    if thu_pha[0]:
                        sp_x = 0            # dang dung thu xem co that cham cu
                    elif chan[0] == huong_x:
                        sp_x = 0            # huong nay da cham cu
                    elif chan[0] != 0:
                        chan[0] = 0         # doi chieu -> go chan

                    if sp_x == 0:
                        motors.speed(ADDR_PAN, 0, 0)
                        dich_cum_x = 0.0
                    else:
                        motors.speed(ADDR_PAN, 0 if pan_duong else 1, sp_x)
                        dich_cum_x = -huong_x * sp_x * PX_KHUNG_NAC_X
                        goc_pan += ((1 if pan_duong else -1)
                                    * sp_x * DO_MOI_NAC_GIAY * chu_ky)

                if not laser.firing:
                    time.sleep_ms(INTER_CMD_MS)

                    if time.ticks_diff(ban_y, time.ticks_ms()) > 0:
                        motors.speed(ADDR_TILT, 0, 0)
                        sp_y = 0
                        dich_cum_y = 0.0
                    elif in_y:
                        motors.speed(ADDR_TILT, 0, 0)
                        if sp_y_truoc > 0:
                            ban_y = time.ticks_add(time.ticks_ms(), BRAKE_SETTLE_MS)
                        sp_y = 0
                        dich_cum_y = 0.0
                    elif (VI_TRI_BAT and abs(ema_y) <= NGUONG_VI_TRI_Y
                          and yen_y >= DUNG_YEN_KHUNG):
                        if sp_y_truoc > 0:
                            motors.speed(ADDR_TILT, 0, 0)
                            ban_y = time.ticks_add(time.ticks_ms(), 200)
                            sp_y = 0
                            dich_cum_y = 0.0
                            raise_skip_y = True
                        else:
                            raise_skip_y = False
                        di_xuong = ema_y > 0
                        xung = int(abs(ema_y) * XUNG_MOI_PX_Y * VI_TRI_HE_SO)
                        if raise_skip_y:
                            xung = 0
                        if xung >= 20:
                            motors.move(ADDR_TILT, 1 if di_xuong else 0,
                                        VI_TRI_NAC, xung)
                            ban_y = time.ticks_add(
                                time.ticks_ms(),
                                int(xung / VI_TRI_XUNG_GIAY * 1000) + VI_TRI_BIEN_MS)
                            goc_tilt += ((-1 if di_xuong else 1)
                                         * xung / XUNG_MOI_DO)
                            vt_y = xung
                        sp_y = 0
                        dich_cum_y = 0.0
                    else:
                        huong_y = 1 if ema_y > 0 else -1
                        ff_y = 0.0
                        if FF_BAT and abs(vy) >= V_NGUONG_PX:
                            ff_y = (vy / PX_KHUNG_NAC_Y) * huong_y
                            ff_y = max(-FF_MAX_NAC, min(FF_MAX_NAC, ff_y))
                        sp_y = int(abs(ema_y) * GAIN_Y + ff_y)
                        sp_y = max(1, min(MAX_SPEED_TILT, sp_y))

                        v_ra_xa = (vy * huong_y) if FF_BAT else 0.0
                        ngan_sach = (abs(ema_y) - DEADZONE_Y) + max(0.0, v_ra_xa)
                        s_phanh = int(ngan_sach / PX_MOI_NAC_Y)
                        sp_y = max(1, min(sp_y, s_phanh))

                        di_xuong = ema_y > 0

                        if sp_y == 0:
                            motors.speed(ADDR_TILT, 0, 0)
                            dich_cum_y = 0.0
                        else:
                            motors.speed(ADDR_TILT, 1 if di_xuong else 0, sp_y)
                            dich_cum_y = -huong_y * sp_y * PX_KHUNG_NAC_Y
                            goc_tilt += ((-1 if di_xuong else 1)
                                         * sp_y * DO_MOI_NAC_GIAY * chu_ky)

                if in_x and in_y:
                    ngoai_lien_tiep = 0
                    if lock_since is None:
                        lock_since = time.time()
                elif lock_since is not None:
                    ngoai_lien_tiep += 1
                    if ngoai_lien_tiep > LOCK_TOLERANCE_FRAMES:
                        lock_since = None
                        ngoai_lien_tiep = 0

                if (lock_since is not None
                        and time.time() - lock_since >= LOCK_SECONDS
                        and tracker.conf_tb() >= CONF_FIRE):
                    if laser.fire(armed_now):
                        lock_since = None
                        ngoai_lien_tiep = 0

            laser.update()

            co = 0 if target is None else 1
            khoa = (0.0 if lock_since is None
                    else time.time() - lock_since)
            if co:
                log.csv("%.2f" % log._giay(), "%.1f" % clock.fps(), 1,
                        ema_x, ema_y, sp_x, sp_y,
                        1 if laser.firing else 0, bo_frame,
                        int(tracker.w), int(tracker.h),
                        "%.2f" % tracker.conf, "%.2f" % tracker.conf_tb(),
                        tracker.hits, "%.1f" % khoa,
                        tracker.n_det, tracker.n_loc,
                        "%.0f" % tracker.gate,
                        "%.0f" % goc_tilt, "%.0f" % goc_pan, vt_x, vt_y,
                        tho_x, tho_y, chan[0], chan[1])
                bo_frame = 0
            elif co_muc_tieu_truoc != 0:
                log.csv("%.2f" % log._giay(), "%.1f" % clock.fps(), 0,
                        0, 0, 0, 0, 1 if laser.firing else 0, bo_frame,
                        0, 0, "0.00", "0.00", 0, "0.0",
                        tracker.n_det, tracker.n_loc,
                        "%.0f" % tracker.gate,
                        "%.0f" % goc_tilt, "%.0f" % goc_pan, vt_x, vt_y,
                        0, 0, chan[0], chan[1])
                bo_frame = 0
            co_muc_tieu_truoc = co
            log.dinh_ky()

            stage = "VE KET QUA / HIEN LCD"
            ob_det.draw_result(img, res)
            img.draw_cross(CENTER_X, CENTER_Y, color=(0, 255, 0),
                           size=18, thickness=2)
            img.draw_rectangle(CENTER_X - DEADZONE_X, CENTER_Y - DEADZONE_Y,
                               DEADZONE_X * 2, DEADZONE_Y * 2,
                               color=(0, 255, 0), thickness=1)

            if laser.firing:
                st = "LASER FIRING %.1fs" % laser.elapsed()
                col = (255, 0, 0)
            elif not LASER_ARMED:
                st = "LASER TAT (chay kho)"
                col = (140, 140, 140)
            elif not armed_now:
                st = "CHO ARM %.0fs" % (ARM_DELAY_SEC - (time.time() - t_boot))
                col = (255, 255, 0)
            else:
                st = "LASER ARMED"
                col = (255, 160, 0)

            img.draw_string_advanced(8, 6, 26, st, color=col)
            img.draw_string_advanced(8, 38, 22,
                                     "FPS:%.1f  anh:%dx%d" % (
                                         clock.fps(), img.width(), img.height()),
                                     color=(0, 255, 0))
            img.draw_string_advanced(8, 66, 22,
                                     "err %d,%d   nac %d,%d   Mstep%d" % (
                                         ema_x, ema_y, sp_x, sp_y, MSTEP),
                                     color=(0, 220, 255))
            img.draw_string_advanced(
                8, 122, 22,
                "tilt %.0f  pan %.0f  yen %d,%d  chan PAN %+d" % (
                    goc_tilt, goc_pan, yen_x, yen_y, chan[0]),
                color=(255, 90, 90) if chan[0] else (180, 180, 255))
            img.draw_string_advanced(
                8, 94, 22,
                "conf %.2f/%.2f  hits %d  khoa %.1f/%.1fs  box %d/%d" % (
                    tracker.conf_tb(), CONF_FIRE, tracker.hits,
                    (0.0 if lock_since is None else time.time() - lock_since),
                    LOCK_SECONDS, tracker.n_loc, tracker.n_det),
                color=(255, 180, 255))
            if chan[0]:
                canh = "CHAM CU PAN %s" % ("PHAI" if chan[0] > 0 else "TRAI")
                img.draw_rectangle(0, CENTER_Y - 34, img.width(), 68,
                                   color=(60, 0, 0), fill=True)
                img.draw_string_advanced(
                    max(0, CENTER_X - int(len(canh) * 11)), CENTER_Y - 26, 42,
                    canh, color=(255, 0, 0))

            if show_ok:
                try:
                    Display.show_image(img, x=OFFSET_X, y=OFFSET_Y)
                except Exception as e:
                    show_ok = False
                    log.su_kien("Display.show_image loi -> TAT hien thi: %s" % e)
        finally:
            img_np_hwc = None
            img_np_chw = None
            img.__del__()
            gc.collect()

except KeyboardInterrupt:
    pass
except SystemExit:
    pass
except BaseException as e:
    save_error(stage, e)
    try:
        if display_ready:
            show_status("LOI: " + stage, str(e))
            time.sleep(15)
    except Exception:
        pass
finally:
    if laser is not None:
        try:
            laser.off()
            print("Laser da tat.")
        except Exception as e:
            print("laser.off:", e)
    if motors is not None:
        try:
            motors.close()
            print("Motor da dung.")
        except Exception as e:
            print("motors.close:", e)
    if started:
        try:
            UVC.stop()
        except Exception as e:
            print("UVC.stop:", e)
    time.sleep_ms(100)
    if ob_det is not None:
        try:
            ob_det.deinit()
        except Exception as e:
            print("YOLO.deinit:", e)
    if display_ready:
        try:
            Display.deinit()
        except Exception as e:
            print("Display.deinit:", e)
    try:
        log.su_kien("Da giai phong. Ket thuc.")
        log.close()
    except Exception:
        pass
    print("Da giai phong.")
