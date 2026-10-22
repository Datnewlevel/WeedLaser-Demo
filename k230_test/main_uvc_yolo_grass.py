# WEBCAM USB (UVC) + YOLO DETECT CO -> LCD 2.4"
#
# Dua tren mau chinh thuc: examples/21-AI-With-Others/ai_uvc_soft_decode.py
# (da xac nhan UVC + YOLO chay chung duoc tren firmware nay).
#
# Model: best_grass_320.kmodel (train local, convert bang nncase 2.11.0)
# Mode webcam: 640x480@30 MJPEG (da xac nhan True trong uvc_step1_probe.py)
# Backup: main_uvc_display_only_backup.py (webcam khong co YOLO)
#         main_yolo_backup.py (demo YOLO cu tren camera MIPI, kmodel da mat)

import time, os, sys, gc
import image
import aidemo
import nncase_runtime as nn
import ulab.numpy as np
from media.display import *
from media.media import *
from media.uvc import *
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
                        x, y - 50, 32,
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


# --- Bat man hinh TRUOC TIEN ---
# Bai hoc tu lan truoc: neu cham vao hang so UVC.* truoc khi Display.init(),
# loi se lam man den thui khong co gi bao. Bat man hinh xong moi lam gi khac.
Display.init(Display.ST7701, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, to_ide=True)
print("Display OK")

ob_det = None
started = False

try:
    # --- Do webcam, co gioi han thoi gian ---
    dev = None
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 15000:
        plugin, d = UVC.probe()
        if plugin:
            dev = d
            print("Da thay webcam:", d)
            break
        time.sleep_ms(200)

    if dev is None:
        img = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.RGB565)
        img.clear()
        img.draw_string_advanced(20, 40, 30, "KHONG THAY WEBCAM", color=(255, 80, 80))
        img.draw_string_advanced(20, 90, 24, "Kiem tra cap USB / webcam", color=(255, 255, 0))
        Display.show_image(img)
        time.sleep(8)
        raise SystemExit

    succ, mode = UVC.select_video_mode(
        UVC.video_mode(RGB888P_SIZE[0], RGB888P_SIZE[1], UVC.FOURCC_MJPEG, 30))
    print("Chon mode 640x480@30 MJPEG ->", succ)
    if not succ:
        img = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.RGB565)
        img.clear()
        img.draw_string_advanced(20, 40, 28, "WEBCAM KHONG NHAN MODE", color=(255, 80, 80))
        img.draw_string_advanced(20, 90, 24, "640x480@30 MJPEG", color=(255, 255, 0))
        Display.show_image(img)
        time.sleep(8)
        raise SystemExit

    # --- Khoi tao YOLO ---
    # Cac MOC nay dung de xac dinh chinh xac dong nao lam chuong trinh dung/reset.
    print("MOC 1: sap khoi tao YOLO")
    ob_det = ObjectDetectionApp(
        KMODEL_PATH,
        labels=LABELS,
        model_input_size=MODEL_INPUT_SIZE,
        max_boxes_num=MAX_BOXES_NUM,
        confidence_threshold=CONFIDENCE_THRESHOLD,
        nms_threshold=NMS_THRESHOLD,
        rgb888p_size=RGB888P_SIZE,
        display_size=RGB888P_SIZE,
        debug_mode=1,
    )
    print("MOC 2: YOLO init OK")

    ob_det.config_preprocess()
    print("MOC 3: AI2D config OK")

    UVC.start(cvt=False)
    started = True
    print("MOC 4: UVC start OK")
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

        # JPEG decode co the that bai vi frame MJPEG qua USB bi hong/thieu
        # goi tin - day la chuyen BINH THUONG xay ra theo chu ky, khong phai
        # loi cau hinh. PHAI bo qua frame loi va chay tiep, khong de no lam
        # chet ca vong lap.
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
            img_np_hwc = img.to_numpy_ref()
            img_np_chw = hwc2chw(img_np_hwc)
            res = ob_det.run(img_np_chw)
            ob_det.draw_result(img, res)
            img.draw_string_advanced(8, 8, 24, "FPS:%.1f" % clock.fps(), color=(0, 255, 0))
            Display.show_image(img)
        except BaseException as e:
            # Khong nuot loi AI/inference/postprocess. In day du traceback de
            # biet chinh xac shape/dong nao sai, sau do day loi ra khoi vong lap.
            print("MOC 5: LOI XU LY FRAME")
            sys.print_exception(e)
            raise
        finally:
            img.__del__()
            gc.collect()

except KeyboardInterrupt:
    pass
except SystemExit:
    pass
except BaseException as e:
    print(">>> LOI:")
    sys.print_exception(e)
    try:
        img = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.RGB565)
        img.clear()
        img.draw_string_advanced(10, 10, 24, "LOI:", color=(255, 80, 80))
        img.draw_string_advanced(10, 45, 20, str(e)[:60], color=(255, 255, 0))
        Display.show_image(img)
        time.sleep(8)
    except Exception:
        pass
finally:
    if started:
        UVC.stop()
    time.sleep_ms(100)
    if ob_det is not None:
        ob_det.deinit()
    Display.deinit()
    print("Da giai phong.")
