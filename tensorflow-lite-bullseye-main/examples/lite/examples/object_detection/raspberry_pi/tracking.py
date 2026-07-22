#!/usr/bin/env python3
"""Object detection + PAN/TILT + LASER tracking co dai qua USB webcam + Coral EdgeTPU.

Ban KHONG CO web server - chi dieu khien qua ban phim tren cua so OpenCV local.

Che do:
  - MANUAL (mac dinh khi khoi dong): dieu khien tay bang A/D/W/S
  - TRACKING: AI tu bam cay co gan tam khung hinh nhat
  - LASER ARM: khoa an toan, phai bat rieng, tu tat khi tracking off

Dieu khien:
  T          bat/tat tracking (toggle)
  L          arm/disarm laser (khoa an toan)
  A / D      quay trai / phai (manual, giu de quay lien tuc)
  W / S      nghieng len / xuong (manual)
  Space      dung ngay (huy target hien tai + tat laser)
  H          ve vi tri giua
  + / -      tang / giam nguong score (buoc 0.05)
  ESC        thoat
"""

import argparse
import math
import sys
import threading
import time

import cv2
from gpiozero import DigitalOutputDevice, PWMOutputDevice
from tflite_support.task import core
from tflite_support.task import processor
from tflite_support.task import vision

import utils

# ==========================================================
# CAU HINH
# ==========================================================

# --- PAN (trai/phai) ---
PAN_EN_PIN, PAN_DIR_PIN, PAN_STEP_PIN = 21, 20, 16
PAN_INVERT = True
PAN_LIMIT_STEPS = 2000

# --- TILT (len/xuong) ---
TILT_EN_PIN, TILT_DIR_PIN, TILT_STEP_PIN = 13, 26, 19
TILT_INVERT = False
TILT_LIMIT_STEPS = 950

# --- Xung ---
STEP_DELAY = 0.0006
JOG_CHUNK = 80              # buoc / tick khi giu phim manual

# --- Tracking ---
INITIAL_SCORE_THRESHOLD = 0.5   # chinh runtime bang +/-
SCORE_STEP = 0.05
PAN_KP = 0.15               # buoc / pixel lech tam ngang
TILT_KP = 0.12              # buoc / pixel lech tam doc
PAN_DEADZONE_PX = 40        # trong vung nay coi nhu da vao tam
TILT_DEADZONE_PX = 30
MAX_STEPS_PER_FRAME = 60    # gioi han xung ra lenh moi frame

# --- Laser ---
LASER_PIN = 18
LASER_PWM_FREQ = 1000       # Hz
LASER_POWER = 0.5           # 0.0 - 1.0
LASER_FIRE_DURATION = 5.0   # so giay chieu moi lan
LOCK_TIME_REQUIRED = 0.4    # phai o trong deadzone lien tuc bao lau moi ban


# ==========================================================
# STEPPER
# ==========================================================

class StepperAxis:
    def __init__(self, en_pin, dir_pin, step_pin, invert=False,
                 limit=2000, delay=STEP_DELAY, name="axis"):
        self.name = name
        self.en = DigitalOutputDevice(en_pin)
        self.dir = DigitalOutputDevice(dir_pin)
        self.step = DigitalOutputDevice(step_pin)
        self.invert = invert
        self.limit = limit
        self.delay = delay

        self.position = 0
        self.target = 0
        self._lock = threading.Lock()
        self._running = True

        self.en.off()          # EN active LOW -> off() = kich hoat motor
        time.sleep(0.05)
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def move_by(self, steps):
        with self._lock:
            new_target = self.target + int(steps)
            self.target = max(-self.limit, min(self.limit, new_target))

    def stop_here(self):
        with self._lock:
            self.target = self.position

    def go_home(self):
        with self._lock:
            self.target = 0

    def _worker(self):
        while self._running:
            with self._lock:
                delta = self.target - self.position
            if delta == 0:
                time.sleep(0.002)
                continue

            direction = 1 if delta > 0 else -1
            level = direction > 0
            if self.invert:
                level = not level
            self.dir.value = level
            time.sleep(0.00002)

            self.step.on()
            time.sleep(self.delay)
            self.step.off()
            time.sleep(self.delay)
            self.position += direction

    def close(self):
        self._running = False
        self._thread.join(timeout=1.0)
        self.en.on()           # nha luc giu motor
        for pin in (self.en, self.dir, self.step):
            pin.close()


# ==========================================================
# LASER
# ==========================================================

class LaserController:
    """Quan ly laser voi khoa an toan (arm/disarm).

    Neu chua armed thi moi lenh fire() deu bi bo qua.
    """

    def __init__(self, pin, freq=LASER_PWM_FREQ, power=LASER_POWER,
                 fire_duration=LASER_FIRE_DURATION):
        self.pwm = PWMOutputDevice(pin, frequency=freq)
        self.pwm.value = 0        # tat mac dinh
        self.power = power
        self.fire_duration = fire_duration

        self.armed = False
        self.firing = False
        self._fire_started = 0
        self._lock = threading.Lock()

    def arm(self):
        with self._lock:
            self.armed = True
        print(">>> LASER ARMED (mo khoa an toan)")

    def disarm(self):
        with self._lock:
            self.armed = False
            if self.firing:
                self.pwm.value = 0
                self.firing = False
        print(">>> LASER DISARMED (khoa an toan)")

    def toggle_arm(self):
        if self.armed:
            self.disarm()
        else:
            self.arm()

    def fire(self):
        """Bat dau ban 1 lot (khong lam gi neu chua armed hoac dang ban)."""
        with self._lock:
            if not self.armed or self.firing:
                return False
            self.pwm.value = self.power
            self.firing = True
            self._fire_started = time.time()
        return True

    def stop(self):
        with self._lock:
            self.pwm.value = 0
            self.firing = False

    def update(self):
        """Goi moi frame: tu dong tat sau du LASER_FIRE_DURATION giay."""
        with self._lock:
            if self.firing and time.time() - self._fire_started >= self.fire_duration:
                self.pwm.value = 0
                self.firing = False
                return True
        return False

    def elapsed(self):
        with self._lock:
            if not self.firing:
                return 0
            return time.time() - self._fire_started

    def close(self):
        self.pwm.value = 0
        self.pwm.close()


# ==========================================================
# TARGET SELECTION
# ==========================================================

def pick_target_nearest_center(detection_result, cx, cy, score_threshold):
    """Chon detection co tam gan tam khung hinh nhat, loc theo score_threshold."""
    best = None
    best_dist = float('inf')
    for det in detection_result.detections:
        if not det.categories:
            continue
        cat = det.categories[0]
        if cat.score < score_threshold:
            continue
        box = det.bounding_box
        obj_cx = box.origin_x + box.width / 2.0
        obj_cy = box.origin_y + box.height / 2.0
        dist = math.hypot(obj_cx - cx, obj_cy - cy)
        if dist < best_dist:
            best = det
            best_dist = dist
    return best


# ==========================================================
# VONG CHINH
# ==========================================================

def run(model, camera_id, width, height, num_threads, enable_edgetpu):
    cap = cv2.VideoCapture(camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        sys.exit('ERROR: Unable to open webcam id={}.'.format(camera_id))

    base_options = core.BaseOptions(
        file_name=model, use_coral=enable_edgetpu, num_threads=num_threads)
    detection_options = processor.DetectionOptions(
        max_results=10, score_threshold=0.1)
    options = vision.ObjectDetectorOptions(
        base_options=base_options, detection_options=detection_options)
    detector = vision.ObjectDetector.create_from_options(options)

    pan = StepperAxis(PAN_EN_PIN, PAN_DIR_PIN, PAN_STEP_PIN,
                      invert=PAN_INVERT, limit=PAN_LIMIT_STEPS, name="PAN")
    tilt = StepperAxis(TILT_EN_PIN, TILT_DIR_PIN, TILT_STEP_PIN,
                       invert=TILT_INVERT, limit=TILT_LIMIT_STEPS, name="TILT")
    laser = LaserController(LASER_PIN)

    print(">>> PAN + TILT da kich hoat.")
    print(">>> LASER khoi tao o trang thai DISARMED (an toan).")
    print(">>> T: tracking | L: arm laser | A/D/W/S: manual | SPACE: dung |"
          " H: home | +/-: score | ESC: thoat")

    tracking_enabled = False
    score_threshold = INITIAL_SCORE_THRESHOLD

    center_x = width / 2.0
    center_y = height / 2.0

    # Thoi diem muc tieu bat dau vao deadzone. None = chua vao / vua roi khoi.
    locked_since = None

    # Trang thai phim manual
    last_key_time = {'a': 0, 'd': 0, 'w': 0, 's': 0}
    HOLD_TIMEOUT = 0.15

    try:
        while True:
            success, image = cap.read()
            if not success:
                print("Khong doc duoc frame tu webcam.")
                break

            # --- Inference ---
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            input_tensor = vision.TensorImage.create_from_array(rgb_image)
            detection_result = detector.detect(input_tensor)

            image = utils.visualize(image, detection_result)

            # --- Chon muc tieu + tracking ---
            target = None
            in_deadzone = False

            if tracking_enabled:
                target = pick_target_nearest_center(
                    detection_result, center_x, center_y, score_threshold)

                if target is not None:
                    box = target.bounding_box
                    obj_cx = box.origin_x + box.width / 2.0
                    obj_cy = box.origin_y + box.height / 2.0

                    err_x = obj_cx - center_x
                    err_y = obj_cy - center_y

                    if abs(err_x) > PAN_DEADZONE_PX:
                        steps = PAN_KP * err_x
                        steps = max(-MAX_STEPS_PER_FRAME,
                                    min(MAX_STEPS_PER_FRAME, steps))
                        pan.move_by(steps)

                    if abs(err_y) > TILT_DEADZONE_PX:
                        steps = TILT_KP * err_y
                        steps = max(-MAX_STEPS_PER_FRAME,
                                    min(MAX_STEPS_PER_FRAME, steps))
                        tilt.move_by(steps)

                    in_deadzone = (
                        abs(err_x) <= PAN_DEADZONE_PX
                        and abs(err_y) <= TILT_DEADZONE_PX
                        and pan.target == pan.position
                        and tilt.target == tilt.position
                    )

                    # Danh dau muc tieu duoc chon: vong tron vang + duong noi
                    cv2.line(image, (int(center_x), int(center_y)),
                             (int(obj_cx), int(obj_cy)), (0, 255, 255), 2)
                    cv2.circle(image, (int(obj_cx), int(obj_cy)),
                               max(15, int(box.width * 0.15)),
                               (0, 255, 255), 3)

            # --- Logic ban laser ---
            if tracking_enabled and in_deadzone:
                if locked_since is None:
                    locked_since = time.time()
                elif (time.time() - locked_since >= LOCK_TIME_REQUIRED
                      and not laser.firing):
                    if laser.fire():
                        print(">>> LASER FIRE (ban {}s @ {}%)".format(
                            LASER_FIRE_DURATION, int(LASER_POWER * 100)))
            else:
                locked_since = None

            if laser.update():
                print(">>> LASER het thoi gian ban, da tat.")

            # --- Overlay ---
            mode_txt = "TRACKING" if tracking_enabled else "MANUAL"
            mode_color = (0, 255, 0) if tracking_enabled else (0, 200, 255)
            cv2.putText(image, "[{}] score>={:.2f}".format(mode_txt, score_threshold),
                        (10, 25), cv2.FONT_HERSHEY_PLAIN, 1.4, mode_color, 2)
            cv2.putText(image,
                        "PAN {}/{}  TILT {}/{}".format(
                            pan.position, pan.target, tilt.position, tilt.target),
                        (10, 50), cv2.FONT_HERSHEY_PLAIN, 1.2, (0, 0, 255), 1)

            if laser.firing:
                laser_txt = "LASER FIRING {:.1f}/{:.1f}s".format(
                    laser.elapsed(), LASER_FIRE_DURATION)
                laser_color = (0, 0, 255)
            elif laser.armed:
                laser_txt = "LASER ARMED (san sang ban)"
                laser_color = (0, 165, 255)
            else:
                laser_txt = "LASER SAFE"
                laser_color = (128, 128, 128)
            cv2.putText(image, laser_txt, (10, 78),
                        cv2.FONT_HERSHEY_PLAIN, 1.3, laser_color, 2)

            cv2.putText(image,
                        "T: track | L: arm | A/D/W/S: manual | SPACE: dung"
                        " | H: home | +/-: score | ESC",
                        (10, height - 15), cv2.FONT_HERSHEY_PLAIN,
                        0.85, (0, 255, 0), 1)
            cv2.drawMarker(image, (int(center_x), int(center_y)),
                           (255, 0, 0), cv2.MARKER_CROSS, 20, 2)

            cv2.imshow('grass_tracker', image)

            # --- Xu ly phim ---
            key = cv2.waitKey(1) & 0xFF
            now = time.time()

            if key == 27:                                   # ESC
                break
            elif key == ord('t'):
                tracking_enabled = not tracking_enabled
                if not tracking_enabled:
                    pan.stop_here()
                    tilt.stop_here()
                    laser.stop()
                    locked_since = None
                print(">>> Tracking:", "ON" if tracking_enabled else "OFF")
            elif key == ord('l'):
                laser.toggle_arm()
            elif key == ord(' '):
                pan.stop_here()
                tilt.stop_here()
                laser.stop()
                locked_since = None
                last_key_time = {'a': 0, 'd': 0, 'w': 0, 's': 0}
            elif key == ord('h'):
                pan.go_home()
                tilt.go_home()
            elif key in (ord('+'), ord('=')):
                score_threshold = min(0.95, score_threshold + SCORE_STEP)
                print(">>> Score threshold:", round(score_threshold, 2))
            elif key in (ord('-'), ord('_')):
                score_threshold = max(0.05, score_threshold - SCORE_STEP)
                print(">>> Score threshold:", round(score_threshold, 2))
            elif not tracking_enabled:
                # Manual chi hoat dong khi tracking OFF, tranh gianh voi AI
                if key in (ord('a'), 81):
                    last_key_time['a'] = now
                    pan.move_by(-JOG_CHUNK)
                elif key in (ord('d'), 83):
                    last_key_time['d'] = now
                    pan.move_by(JOG_CHUNK)
                elif key in (ord('w'), 82):
                    last_key_time['w'] = now
                    tilt.move_by(-JOG_CHUNK)
                elif key in (ord('s'), 84):
                    last_key_time['s'] = now
                    tilt.move_by(JOG_CHUNK)

            # --- Auto-stop khi tha phim manual ---
            if not tracking_enabled:
                if last_key_time['a'] and now - last_key_time['a'] > HOLD_TIMEOUT:
                    if pan.target < pan.position:
                        pan.stop_here()
                    last_key_time['a'] = 0
                if last_key_time['d'] and now - last_key_time['d'] > HOLD_TIMEOUT:
                    if pan.target > pan.position:
                        pan.stop_here()
                    last_key_time['d'] = 0
                if last_key_time['w'] and now - last_key_time['w'] > HOLD_TIMEOUT:
                    if tilt.target < tilt.position:
                        tilt.stop_here()
                    last_key_time['w'] = 0
                if last_key_time['s'] and now - last_key_time['s'] > HOLD_TIMEOUT:
                    if tilt.target > tilt.position:
                        tilt.stop_here()
                    last_key_time['s'] = 0

    except KeyboardInterrupt:
        print("\nDung khan cap!")
    finally:
        # BAT BUOC: tat laser NGAY, truoc khi lam bat cu viec gi khac
        laser.disarm()
        laser.stop()
        laser.close()

        print(">>> Dang ve vi tri giua...")
        pan.go_home()
        tilt.go_home()
        time.sleep(1.5)
        pan.close()
        tilt.close()
        cap.release()
        cv2.destroyAllWindows()
        print(">>> Da ngat dong co + laser. Hoan tat!")


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--model', required=False,
                        default='best_grass.tflite')
    parser.add_argument('--cameraId', required=False, type=int, default=0)
    parser.add_argument('--frameWidth', required=False, type=int, default=640)
    parser.add_argument('--frameHeight', required=False, type=int, default=480)
    parser.add_argument('--numThreads', required=False, type=int, default=4)
    parser.add_argument('--enableEdgeTPU', action='store_true',
                        required=False, default=True)
    args = parser.parse_args()

    run(args.model, int(args.cameraId), args.frameWidth, args.frameHeight,
        int(args.numThreads), bool(args.enableEdgeTPU))


if __name__ == '__main__':
    main()