# Train YOLO local → kmodel cho K230

## Ràng buộc phiên bản — ĐỌC TRƯỚC

Firmware đang chạy trên board (xem banner boot trong Serial Terminal):

```
CanMV v1.8-0-gc2d1f5c (based on Micropython e00a144) on 2026-07-03; k230_canmv_01studio with K230
```

File firmware gốc: `CanMV_K230_01Studio_Emmc_micropython_v1.8-0-gc2d1f5c_nncase_v2.11.0.img.gz`
→ **nncase runtime = 2.11.0**

**Kmodel PHẢI được biên dịch bằng nncase 2.11.0.** Dùng 2.9 hay 2.10 sẽ tạo ra file
mà firmware không load được (lỗi kiểu "invalid kmodel" hoặc crash lúc khởi tạo YOLO).
Đây là lỗi hay gặp nhất khi tự build kmodel.

---

## Kiến trúc pipeline

```
[Windows + RTX 3060]                    [WSL2 Ubuntu]
  Ultralytics train YOLO11    ──→  best.pt
  export ONNX                 ──→  best.onnx  ──→  to_kmodel.py  ──→  best.kmodel
                                                    (nncase 2.11.0)
                                                          │
                                                          ▼
                                                   copy vào thẻ SD
```

Lý do tách 2 môi trường:
- **Train trên Windows native**: CUDA/Ultralytics chạy sẵn, bạn đã quen từ Coral/AI HAT.
- **Convert trong WSL2**: nncase trên Linux cài bằng pip trực tiếp cả `nncase` lẫn `nncase-kpu`.
  Trên Windows thì `nncase-kpu` phải cài offline (tải wheel thủ công) — rườm rà hơn.

Nếu không muốn dùng WSL thì vẫn làm được hết trên Windows, chỉ tốn thêm bước tải wheel.

---

## PHẦN 1 — Train trên Windows (giống hệt quy trình Coral/AI HAT bạn đã làm)

### Dataset
Định dạng YOLO chuẩn, không khác gì bạn đã dùng:

```
dataset/
├── data.yaml
├── train/
│   ├── images/
│   └── labels/       # .txt: <class> <cx> <cy> <w> <h>  (đã chuẩn hoá 0-1)
└── val/
    ├── images/
    └── labels/
```

`data.yaml`:
```yaml
path: E:/dataset_co
train: train/images
val: val/images
names:
  0: grass
```

### Train

```bash
pip install ultralytics
```

```python
from ultralytics import YOLO

model = YOLO("yolo11n.pt")        # n = nano, nhẹ nhất, hợp cho KPU
model.train(
    data="E:/dataset_co/data.yaml",
    epochs=150,
    imgsz=320,                     # QUAN TRỌNG: khớp với input_width/height khi convert
    batch=32,
    device=0,                      # RTX 3060
    project="runs_co",
    name="grass_v1",
)
```

**Chọn `imgsz`**: model demo của 01Studio dùng `320x320` (`yolo11s_det_320.kmodel`).
320 là điểm cân bằng tốt cho KPU. Muốn nhanh hơn thì 224, nét hơn thì 416/640
nhưng FPS sẽ tụt. Nhớ con số này — phải dùng lại y hệt ở bước convert.

**Chọn model size**: `yolo11n` (nano) trước. Nếu độ chính xác chưa đủ mới lên `yolo11s`.
Webcam của bạn đang cho 25-30 FPS, thêm inference vào sẽ tụt tiếp — nano an toàn hơn.

### Export ONNX

```python
model = YOLO("runs_co/grass_v1/weights/best.pt")
model.export(format="onnx", imgsz=320, opset=12, simplify=True)
```

Ra file `best.onnx`.

---

## PHẦN 2 — Convert sang kmodel (WSL2 Ubuntu)

### Cài môi trường

```bash
# .NET SDK 7 - nncase 2.x bắt buộc có
wget https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
sudo apt update && sudo apt install -y dotnet-sdk-7.0

# nncase - PHIÊN BẢN PHẢI LÀ 2.11.0
pip install nncase==2.11.0
pip install nncase-kpu==2.11.0

# phụ trợ
pip install onnx==1.15.0 onnxruntime==1.19.0 onnxsim==0.4.36
```

Kiểm tra:
```bash
python -c "import nncase; print(nncase.__version__)"    # phải in 2.11.0
dotnet --list-sdks                                       # phải thấy 7.x
```

### Chuẩn bị ảnh calibration

nncase lượng tử hoá INT8 nên cần ảnh mẫu để dò dải giá trị:

```
calib_images/       # 100-300 ảnh LẤY TỪ TẬP TRAIN, đại diện đủ các điều kiện
├── 001.jpg          # sáng/tối, góc chụp, nền đất khác nhau...
├── 002.jpg
└── ...
```

Ảnh calibration kém đại diện → model lượng tử hoá sai lệch → phát hiện tệ dù
train tốt. Đây là chỗ hay bị bỏ qua.

### Chạy convert

Tải bộ script `test_yolov5.zip` từ tài liệu Kendryte (chứa `to_kmodel.py`), giải nén, rồi:

```bash
python to_kmodel.py \
  --target k230 \
  --model best.onnx \
  --dataset calib_images \
  --input_width 320 \
  --input_height 320 \
  --ptq_option 0
```

`--input_width/height` **phải khớp `imgsz` lúc train và export**.

`--ptq_option`: 0-5, tổ hợp giữa Kld/NoClip và uint8/int16.
Bắt đầu bằng `0`. Nếu độ chính xác tụt nhiều so với lúc chạy trên PC thì thử các giá trị khác
(int16 chính xác hơn nhưng chậm hơn).

Kết quả: `best.kmodel` nằm cùng thư mục file onnx.

---

## PHẦN 3 — Chạy trên K230

Copy `best.kmodel` vào thẻ SD, rồi sửa `main.py`:

```python
kmodel_path = "/sdcard/best.kmodel"
labels = {0: 'grass'}
model_input_size = [320, 320]        # khớp lúc train + convert
```

Phần còn lại giữ nguyên cấu trúc `main.py` mà 01Studio sinh ra
(dùng `libs.YOLO.YOLO11`) — nó đã xử lý sẵn tiền/hậu xử lý cho YOLO11.

Nhớ:
- `display = "lcd2_4"` (màn 2.4 inch đã xác nhận)
- Nguồn video: đổi từ MIPI Sensor sang UVC (xem `uvc_step3_display.py`)

---

## Checklist khi model không chạy

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Load kmodel lỗi / crash ngay | Sai phiên bản nncase (không phải 2.11.0) |
| Không phát hiện được gì | `model_input_size` lệch với lúc convert |
| Phát hiện kém hơn hẳn trên PC | Ảnh calibration không đại diện, hoặc thử `--ptq_option` khác |
| Box lệch vị trí | Tỉ lệ khung hình webcam (640x480 = 4:3) vs input model (320x320 = 1:1) |
| FPS quá thấp | Dùng `yolo11n` thay `yolo11s`, hoặc giảm `imgsz` xuống 224 |

---

## Khác biệt so với Coral / AI HAT

| | Coral Edge TPU | Pi AI HAT | K230 |
|---|---|---|---|
| Định dạng cuối | `.tflite` (INT8) | `.hef` | `.kmodel` |
| Công cụ convert | `edgetpu_compiler` | Hailo Dataflow Compiler | `nncase` |
| Đầu vào convert | TFLite INT8 | ONNX | ONNX |
| Ràng buộc phiên bản | compiler vs runtime | SDK vs firmware | **nncase vs firmware** |

Bước train (Ultralytics YOLO) **giống hệt nhau** cả 3 nền tảng — chỉ khác khâu convert cuối.
