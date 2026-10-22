# Hướng dẫn: Setup môi trường + Train YOLO trên máy Ubuntu vừa cài (ổ mới)

Tiếp nối sau khi Ubuntu đã nằm trên ổ F: theo hướng dẫn trước. Từ đây là dựng lại toàn bộ pipeline train YOLO từ con số 0.

---

## 0. Vào Ubuntu và cập nhật hệ thống

```bash
wsl -d Ubuntu-22.04
```

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential git curl unzip python3-pip python3-venv
```

---

## 1. Kiểm tra GPU trước khi làm gì khác

WSL **không cần** cài driver NVIDIA riêng cho Linux — nó dùng thẳng driver đã cài trên Windows. Chỉ cần kiểm tra thấy được GPU:

```bash
nvidia-smi
```

- Thấy bảng thông tin GPU + version CUDA driver → ổn, đi tiếp.
- Báo `command not found` → driver NVIDIA trên **Windows** (không phải trong Ubuntu) chưa cài hoặc quá cũ. Cài/update qua GeForce Experience hoặc trang chủ NVIDIA, không cài gì trong WSL cho việc này.

Ghi lại số CUDA version hiện trên `nvidia-smi` (góc trên phải) — dùng để chọn bản PyTorch phù hợp ở bước sau.

---

## 2. Tạo khung project

```bash
mkdir -p /home/do/yolo_project
cd /home/do/yolo_project
```

Cấu trúc mục tiêu:

```
yolo_project/
├── yolo_env/          # venv, tạo ở bước 3
├── dataset/            # tải từ Roboflow, bước 5
├── train.py
├── export.py
└── calibration_imgs/   # dùng nếu sau này export sang NPU (kmodel/tflite/hef)
```

---

## 3. Tạo virtual environment

```bash
python3 -m venv yolo_env
source yolo_env/bin/activate
```

Từ giờ mọi lệnh `pip`/`python3` chạy trong venv này. Terminal sẽ hiện `(yolo_env)` ở đầu dòng — nếu không thấy nghĩa là chưa activate.

Nâng cấp pip trước:

```bash
pip install --upgrade pip
```

---

## 4. Cài PyTorch bản CUDA + Ultralytics

**Đừng `pip install torch` trơn** — mặc định có thể ra bản CPU-only. Lấy đúng lệnh cho CUDA version của bạn tại **pytorch.org/get-started/locally** (chọn Stable / Linux / Pip / Python / CUDA tương ứng số ghi lại ở Bước 1). Ví dụ với CUDA 12.x:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

Sau đó cài các thư viện còn lại:

```bash
pip install ultralytics roboflow onnx onnxslim onnxruntime
```

**Kiểm tra bắt buộc trước khi train** — bỏ qua bước này dễ train cả tiếng bằng CPU mà không biết:

```bash
python3 -c "import torch; print('CUDA:', torch.cuda.is_available(), '| GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
```

Phải ra `CUDA: True` kèm tên GPU. Nếu `False` dù `nvidia-smi` chạy tốt → PyTorch cài nhầm bản CPU, gỡ cài lại đúng lệnh ở trên (`pip uninstall torch torchvision` trước).

---

## 5. Lấy dataset từ Roboflow

Cho vào thẳng `dataset/` như bạn nói. Cách nhanh nhất — dùng API, khỏi tải file zip qua tay:

```bash
pip install roboflow
```

```python
# download_dataset.py
from roboflow import Roboflow

rf = Roboflow(api_key="API_KEY_CUA_BAN")
project = rf.workspace("ten-workspace").project("ten-project")
version = project.version(1)
dataset = version.download("yolov11", location="/home/do/yolo_project/dataset")
```

```bash
python3 download_dataset.py
```

Lấy `workspace / project / version` từ trang dataset trên Roboflow → **Download Dataset** → chọn format **YOLOv11** → **Show download code**.

> Nếu Roboflow chưa có mục YOLOv11 thì chọn **YOLOv8** cũng được — hai format xuất ra cùng một cấu trúc thư mục `images/` + `labels/` và cùng `data.yaml`, Ultralytics đọc giống hệt nhau. Không cần xuất lại dataset chỉ vì đổi phiên bản model.

---

## 6. Sửa `dataset/data.yaml`

Bước hay bị bỏ sót nhất — Roboflow xuất đường dẫn tương đối, WSL rất hay báo *"Dataset not found"*. Sửa `path:` thành tuyệt đối:

```yaml
path: /home/do/yolo_project/dataset
train: train/images
val: valid/images
test: test/images

nc: 3
names: ['car', 'motorbike', 'truck']   # giữ đúng thứ tự Roboflow xuất ra
```

Kiểm tra số ảnh khớp số label:

```bash
ls dataset/train/images | wc -l
ls dataset/train/labels | wc -l
```

---

## 7. `train.py`

```python
from ultralytics import YOLO

model = YOLO("yolo11n.pt")           # đổi yolo11s.pt nếu độ chính xác chưa đủ

model.train(
    data="/home/do/yolo_project/dataset/data.yaml",
    epochs=500,
    imgsz=640,
    batch=16,                        # giảm còn 8 nếu OOM
    device=0,
    name="my_model_its",
    patience=50,                     # tự dừng nếu 50 epoch không cải thiện
    workers=8,
    cache=True,
    project="runs/detect",
)
```

Chạy nền để tắt terminal cũng không mất tiến trình:

```bash
nohup python3 train.py > train.log 2>&1 &
tail -f train.log
```

Bị đứt giữa chừng thì resume:

```python
model = YOLO("runs/detect/my_model_its/weights/last.pt")
model.train(resume=True)
```

---

## 8. Đánh giá kết quả

```bash
yolo val model=runs/detect/my_model_its/weights/best.pt data=dataset/data.yaml split=test
```

Nhìn `mAP50-95` — dưới ~0.4 thường là do dataset chứ không phải tham số train. File đáng xem trong `runs/detect/my_model_its/`: `results.png` (đồ thị loss/mAP), `confusion_matrix.png`, `val_batch0_pred.jpg`.

---

## 9. Export ONNX

```bash
yolo export model=runs/detect/my_model_its/weights/best.pt \
     format=onnx imgsz=640 opset=12 simplify=True dynamic=False batch=1 half=False
```

`dynamic=False` và `half=False` bắt buộc nếu đích cuối là NPU (Hailo/K230/Pi) — shape phải tĩnh, giữ FP32 để toolchain tự lượng tử hóa INT8 sau.

Kiểm tra nhanh file chạy đúng:

```python
from ultralytics import YOLO
model = YOLO("runs/detect/my_model_its/weights/best.onnx")
results = model("dataset/test/images/anh_bat_ky.jpg")
results[0].show()
```

---

## 10. Bước tiếp theo — convert sang kmodel / tflite / hef

Phần này (bao gồm chuẩn bị ảnh calibration, compile Hailo, onnx2tf, nncase K230) đã có sẵn trong hướng dẫn export NPU trước đó — dùng thẳng file `best.onnx` từ Bước 9 làm đầu vào cho các bước đó.

---

## Lỗi hay gặp khi setup từ đầu

| Lỗi | Xử lý |
|---|---|
| `nvidia-smi` không chạy trong WSL | Update driver NVIDIA trên Windows, không phải trong Ubuntu |
| `torch.cuda.is_available()` = False dù driver ổn | Cài nhầm bản PyTorch CPU — gỡ, cài lại đúng `--index-url` theo CUDA version |
| `Dataset ... not found` | Sửa `path:` trong `data.yaml` thành đường dẫn tuyệt đối |
| `CUDA out of memory` | Giảm `batch` 16→8→4, hoặc `imgsz=416` |
| Train chậm bất thường | Bật `cache=True`; đảm bảo `dataset/` nằm trong `/home/do/...` chứ không phải `/mnt/c/...` hay `/mnt/f/...` (đọc qua mount Windows chậm hơn nhiều so với ext4 native) |
| `pip install` báo lỗi permission | Đang quên activate venv — kiểm tra `(yolo_env)` có hiện ở đầu dòng terminal không |

---

## Quy trình rút gọn (chạy 1 lèo trên máy mới)

```bash
wsl -d Ubuntu-22.04
sudo apt update && sudo apt install -y build-essential git curl unzip python3-pip python3-venv
nvidia-smi   # xác nhận GPU thấy được trước khi đi tiếp

mkdir -p /home/do/yolo_project && cd /home/do/yolo_project
python3 -m venv yolo_env
source yolo_env/bin/activate
pip install --upgrade pip
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124   # đổi cu124 theo CUDA version
pip install ultralytics roboflow onnx onnxslim onnxruntime
python3 -c "import torch; print(torch.cuda.is_available())"   # phải True

# tải dataset roboflow vào dataset/, sửa path: trong dataset/data.yaml

python3 train.py
yolo val model=runs/detect/my_model_its/weights/best.pt data=dataset/data.yaml split=test
yolo export model=runs/detect/my_model_its/weights/best.pt format=onnx imgsz=640 opset=12 simplify=True dynamic=False batch=1 half=False
```