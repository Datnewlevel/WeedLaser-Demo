# WEBCAM USB (UVC) + YOLO DETECT CO -> LCD 2.4"
# Luu tai /sdcard/main.py de tu chay khi K230 bat nguon.
# Ban nhan dien: hien webcam, khung grass va FPS tren LCD.
#
# Dua tren mau chinh thuc: examples/21-AI-With-Others/ai_uvc_soft_decode.py
# (da xac nhan UVC + YOLO chay chung duoc tren firmware nay).
#
# Model: best_grass_320.kmodel (train local, convert bang nncase 2.11.0)
# Mode webcam: 640x480@30 MJPEG (da xac nhan True trong uvc_step1_probe.py)
#
# Backup: main_uvc_display_only_backup.py (webcam khong co YOLO)
#         main_yolo_backup.py (demo YOLO cu tren camera MIPI, kmodel da mat)

import time, os, sys, gc
import image
import aidemo
import nncase_runtime as nn
import ulab.numpy as np
from media.display import *
from media.media import *
from libs.AIBase import AIBase
from libs.AI2D import Ai2d
from libs.Utils import *

DISPLAY_WIDTH = ALIGN_UP(640, 16)     # man 2.4 inch da xac nhan (test_display.py)
DISPLAY_HEIGHT = 480

KMODEL_PATH = "/sdcard/best_grass_320.kmodel"
LABELS = ["grass"]
MODEL_INPUT_SIZE = [320, 320]         # PHAI khop --input_width/height luc convert
RGB888P_SIZE = [640, 480]             # khop mode webcam da chon ben duoi

CONFIDENCE_THRESHOLD = 0.5
NMS_THRESHOLD = 0.45
MAX_BOXES_NUM = 30
TO_IDE = False                     # True neu muon xem them anh trong CanMV IDE
WEBCAM_WAIT_MS = 30000             # cho webcam san sang khi cap nguon nguoi
ERROR_LOG_PATH = "/sdcard/main_error.log"


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
                [1, 3, self.model_input_size[1], self.model_input_size[0]]
            )

    def postprocess(self, results):
        with ScopedTiming("postprocess", self.debug_mode > 0):
            new_result = results[0][0].transpose()
            det_res = aidemo.yolov8_det_postprocess(
                new_result.copy(),
                [self.rgb888p_size[1], self.rgb888p_size[0]],
                [self.model_input_size[1], self.model_input_size[0]],
                [self.display_size[1], self.display_size[0]],
                len(self.labels),
                self.confidence_threshold,
                self.nms_threshold,
                self.max_boxes_num
            )
            return det_res

    def draw_result(self, img, dets):
        with ScopedTiming("display_draw", self.debug_mode > 0):
            if dets:
                for i in range(len(dets[0])):
                    x, y, w, h = map(lambda v: int(round(v, 0)), dets[0][i])
                    img.draw_rectangle(x, y, w, h, color=self.color_four[dets[1][i]],
                                       thickness=4)
                    img.draw_string_advanced(
                        max(0, x), max(0, y - 36), 32,
                        " " + self.labels[dets[1][i]] + " " + str(round(dets[2][i], 2)),
                        color=self.color_four[dets[1][i]])


def hwc2chw(img_np_hwc):
    # Cach HWC -> CHW tuong thich ulab tren CanMV K230.
    # Firmware nay chi ho tro ndarray.transpose() khong co tham so axes.
    shape = img_np_hwc.shape
    img_tmp = img_np_hwc.reshape((shape[0] * shape[1], shape[2]))
    img_trans = img_tmp.transpose()
    img_tmp = img_trans.copy()
    return img_tmp.reshape((shape[2], shape[0], shape[1]))


def show_status(title, detail=""):
    print(title, detail)
    status_img = None
    try:
        status_img = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.RGB565)
        status_img.clear()
        status_img.draw_string_advanced(12, 20, 28, title, color=(0, 255, 0))
        status_img.draw_string_advanced(12, 65, 22, detail[:48], color=(255, 255, 0))
        Display.show_image(status_img)
    finally:
        if status_img is not None:
            status_img.__del__()


def save_error(stage, exc):
    print(">>> LOI TAI:", stage)
    sys.print_exception(exc)
    try:
        # Chi ghi khi co loi dung chuong trinh; giu lai loi gan nhat de doc tren PC.
        with open(ERROR_LOG_PATH, "w") as log:
            log.write("main.py - " + stage + "\n")
            log.write("Model: " + KMODEL_PATH + "\n")
            sys.print_exception(exc, log)
        print("Da luu loi:", ERROR_LOG_PATH)
    except Exception as log_error:
        print("Khong ghi duoc log:", log_error)

ob_det = None
started = False
display_ready = False
stage = "KHOI TAO LCD"

try:
    Display.init(Display.ST7701, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT,
                 to_ide=TO_IDE)
    display_ready = True
    show_status("K230 - YOLO GRASS", "Dang khoi dong...")

    # Import UVC sau khi LCD san sang de hien loi neu firmware khong ho tro.
    stage = "IMPORT UVC"
    from media.uvc import *

    stage = "KIEM TRA MODEL"
    model_size = os.stat(KMODEL_PATH)[6]
    if model_size <= 0:
        raise RuntimeError("File kmodel rong")
    print("Model:", KMODEL_PATH, "size:", model_size)

    # --- Do webcam, co gioi han thoi gian ---
    stage = "CHO WEBCAM"
    show_status("CHO WEBCAM USB", "640x480 MJPEG - toi da 30 giay")
    dev = None
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < WEBCAM_WAIT_MS:
        plugin, d = UVC.probe()
        if plugin:
            dev = d
            print("Da thay webcam:", d)
            break
        time.sleep_ms(200)

    if dev is None:
        raise RuntimeError("Khong thay webcam sau 30 giay")

    stage = "CHON MODE WEBCAM"
    succ, mode = UVC.select_video_mode(
        UVC.video_mode(RGB888P_SIZE[0], RGB888P_SIZE[1], UVC.FOURCC_MJPEG, 30))
    print("Chon mode 640x480@30 MJPEG ->", succ)
    if not succ:
        raise RuntimeError("Webcam khong nhan 640x480@30 MJPEG")

    # --- Khoi tao YOLO ---
    stage = "NAP MODEL"
    show_status("DANG NAP YOLO", "best_grass_320.kmodel")
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

    stage = "BAT UVC"
    UVC.start(cvt=False)
    started = True
    show_status("YOLO SAN SANG", "Dang cho khung hinh dau tien...")
    print("Dang chay YOLO tren luong webcam...")

    clock = time.clock()
    consecutive_bad = 0
    warned = False
    while True:
        clock.tick()
        img = None
        try:
            img = UVC.snapshot()
        except Exception:
            continue
        if img is None:
            continue

        # Bo qua frame JPEG loi le te; canh bao neu loi lien tiep.
        try:
            img = img.to_rgb888()
        except Exception as e:
            consecutive_bad += 1
            try:
                img.__del__()
            except Exception:
                pass
            if consecutive_bad >= 30 and not warned:
                print("CANH BAO: qua nhieu frame JPEG loi lien tiep (%d)" % consecutive_bad)
                print("-> kiem tra cap USB / hub co nguon rieng / do bao hoa bang thong")
                warned = True
            continue

        consecutive_bad = 0
        warned = False

        try:
            stage = "DOI ANH HWC -> CHW"
            img_np_hwc = img.to_numpy_ref()
            img_np_chw = hwc2chw(img_np_hwc)
            stage = "YOLO INFERENCE / POSTPROCESS"
            res = ob_det.run(img_np_chw)
            stage = "VE KET QUA / HIEN LCD"
            ob_det.draw_result(img, res)
            img.draw_string_advanced(8, 8, 24, "GRASS  FPS:%.1f" % clock.fps(),
                                     color=(0, 255, 0))
            Display.show_image(img)
        finally:
            # Bo tham chieu vao buffer anh truoc khi giai phong anh.
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
    print("Da giai phong.")
