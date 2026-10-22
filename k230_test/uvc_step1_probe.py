# UVC BUOC 1 - CHAN DOAN, KHONG DUNG MAN HINH  (v2 - fix FOURCC)
import sys, time

print("=" * 50)
print("BUOC 1: thu import media.uvc")
print("=" * 50)
try:
    from media.uvc import *
    print("OK - import media.uvc THANH CONG")
except Exception as e:
    print("THAT BAI - firmware nay KHONG CO module media.uvc")
    sys.print_exception(e)
    raise SystemExit

print()
print("=" * 50)
print("BUOC 2: cac hang FOURCC firmware nay THAT SU co")
print("=" * 50)
fourcc_names = [n for n in dir(UVC) if n.startswith("FOURCC")]
if not fourcc_names:
    print("  (khong tim thay hang nao ten FOURCC* - in het dir(UVC) de xem)")
    for n in dir(UVC):
        print("   ", n)
else:
    for n in fourcc_names:
        print("  ", n, "=", getattr(UVC, n))

print()
print("=" * 50)
print("BUOC 3: do webcam trong 15 giay")
print("=" * 50)
dev = None
t0 = time.ticks_ms()
n = 0
while time.ticks_diff(time.ticks_ms(), t0) < 15000:
    try:
        plugin, d = UVC.probe()
    except Exception as e:
        print("probe() nem loi:")
        sys.print_exception(e)
        raise SystemExit
    n += 1
    if plugin:
        dev = d
        print("THAY WEBCAM sau", n, "lan do:", d)
        break
    time.sleep_ms(200)

if dev is None:
    print("KHONG THAY WEBCAM sau", n, "lan do.")
    raise SystemExit

print()
print("=" * 50)
print("BUOC 4: thu cac che do video (dung getattr - khong crash neu thieu hang)")
print("=" * 50)

candidates = [
    (640, 480, "MJPEG", "FOURCC_MJPEG", 30),
    (640, 480, "MJPEG", "FOURCC_MJPEG", 15),
    (320, 240, "MJPEG", "FOURCC_MJPEG", 30),
    (1280, 720, "MJPEG", "FOURCC_MJPEG", 30),
    (640, 480, "YUYV", "FOURCC_YUYV", 30),
    (640, 480, "YUY2", "FOURCC_YUY2", 30),
    (640, 480, "NV12", "FOURCC_NV12", 30),
    (640, 480, "UYVY", "FOURCC_UYVY", 30),
]

ok_modes = []
for (w, h, tag, attr_name, fps) in candidates:
    fourcc = getattr(UVC, attr_name, None)
    if fourcc is None:
        print("  bo qua", tag, "- khong co UVC." + attr_name, "o firmware nay")
        continue
    label = "%dx%d@%d %s" % (w, h, fps, tag)
    try:
        succ, m = UVC.select_video_mode(UVC.video_mode(w, h, fourcc, fps))
    except Exception as e:
        print("  ", label, "-> nem loi:", e)
        continue
    print("  ", label, "->", succ)
    if succ:
        ok_modes.append((label, w, h, fourcc, fps))

print()
if ok_modes:
    print("CHE DO DUNG DUOC:", [m[0] for m in ok_modes])
else:
    print("KHONG CHE DO NAO DUNG DUOC")
    raise SystemExit

print()
print("=" * 50)
print("BUOC 5: lay thu 30 frame voi che do dau tien dung duoc (khong hien man hinh)")
print("=" * 50)

label, w, h, fourcc, fps = ok_modes[0]
print("Dung che do:", label)
UVC.start(cvt=False)
got = 0
dropped = 0
try:
    for i in range(90):
        try:
            img = UVC.snapshot()
        except Exception:
            dropped += 1
            continue
        if img is None:
            dropped += 1
            continue
        got += 1
        if got == 1:
            print("Frame dau tien OK! size:", img.width(), "x", img.height())
        img.__del__()
        if got >= 30:
            break
finally:
    UVC.stop()

print("Lay duoc", got, "frame, rot", dropped)
if got > 0:
    print()
    print(">>> WEBCAM HOAT DONG TOT voi che do:", label)
    print(">>> Dung dung che do nay trong main.py chinh thuc.")
else:
    print()
    print(">>> select_video_mode() bao thanh cong nhung KHONG lay duoc frame.")
    print(">>> Co the do drop qua nhieu / bang thong USB khong du.")
