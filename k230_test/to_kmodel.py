#!/usr/bin/env python3
"""
Convert ONNX -> kmodel cho K230.

Tham so compile lay tu tai lieu chinh thuc Kendryte (K230_nncase_Development_Guide).
Script TU DOC kich thuoc input tu file ONNX nen khong can nho da train imgsz bao nhieu.

CHAY TRONG WSL2 UBUNTU, sau khi da cai:
    sudo apt install -y dotnet-sdk-7.0
    pip install nncase==2.11.0 nncase-kpu==2.11.0
    pip install onnx onnxruntime onnxsim pillow numpy

VI DU:
    python3 to_kmodel.py \
        --model runs/detect/my_model_k230/weights/best.onnx \
        --dataset calibration_imgs \
        --output best.kmodel
"""

import argparse
import os
import sys

import numpy as np


def read_model_file(path):
    with open(path, "rb") as f:
        return f.read()


def get_onnx_input_shape(path):
    """Doc shape input tu ONNX -> khong phai doan imgsz."""
    import onnx
    m = onnx.load(path)
    inp = m.graph.input[0]
    dims = [d.dim_value for d in inp.type.tensor_type.shape.dim]
    return inp.name, dims


def generate_data(shape, num, calib_dir):
    """Doc anh calibration -> list cac tensor uint8 NCHW."""
    from PIL import Image

    exts = (".jpg", ".jpeg", ".png", ".bmp")
    files = sorted(
        os.path.join(calib_dir, f)
        for f in os.listdir(calib_dir)
        if f.lower().endswith(exts)
    )
    if not files:
        sys.exit("LOI: khong tim thay anh nao trong %s" % calib_dir)

    n = min(num, len(files))
    print("Dung %d/%d anh calibration" % (n, len(files)))

    H, W = shape[2], shape[3]
    data = []
    for p in files[:n]:
        img = Image.open(p).convert("RGB").resize((W, H))
        arr = np.asarray(img, dtype=np.uint8)      # HWC
        arr = np.transpose(arr, (2, 0, 1))         # -> CHW
        data.append([arr[np.newaxis, ...]])        # -> NCHW
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="duong dan file .onnx")
    ap.add_argument("--dataset", required=True, help="thu muc anh calibration")
    ap.add_argument("--output", default=None, help="file .kmodel dau ra")
    ap.add_argument("--target", default="k230")
    ap.add_argument("--samples", type=int, default=200,
                    help="so anh calibration dung (100-300 la hop ly)")
    ap.add_argument("--input_width", type=int, default=None,
                    help="ghi de chieu rong (mac dinh: doc tu ONNX)")
    ap.add_argument("--input_height", type=int, default=None,
                    help="ghi de chieu cao (mac dinh: doc tu ONNX)")
    ap.add_argument("--calibrate_method", default="NoClip",
                    choices=["NoClip", "Kld"],
                    help="NoClip an toan hon cho detection; Kld doi khi chinh xac hon")
    ap.add_argument("--quant_type", default="uint8",
                    choices=["uint8", "int16"],
                    help="int16 chinh xac hon nhung CHAM hon tren KPU")
    args = ap.parse_args()

    import nncase

    # nncase KHONG co thuoc tinh __version__ -> phai doc metadata cua package
    try:
        from importlib.metadata import version as _pkgver, PackageNotFoundError
    except ImportError:
        from importlib_metadata import version as _pkgver, PackageNotFoundError

    def pkgver(name):
        try:
            return _pkgver(name)
        except PackageNotFoundError:
            return None

    v_nncase = pkgver("nncase")
    v_kpu = pkgver("nncase-kpu")
    print("nncase     :", v_nncase or "KHONG THAY")
    print("nncase-kpu :", v_kpu or "KHONG THAY")

    if v_kpu is None:
        sys.exit("LOI: chua cai nncase-kpu. Khong co plugin nay thi khong "
                 "compile duoc cho target k230.\n"
                 "     pip install nncase-kpu==2.11.0")

    if not (v_nncase or "").startswith("2.11"):
        print()
        print("!" * 60)
        print("CANH BAO: firmware K230 cua ban co nncase runtime 2.11.0")
        print("Phien ban dang dung:", v_nncase)
        print("Kmodel bien dich sai phien ban se KHONG LOAD DUOC tren board.")
        print("!" * 60)
        print()
        if input("Van tiep tuc? (y/N) ").strip().lower() != "y":
            sys.exit(1)

    # --- Doc shape tu ONNX ---
    inp_name, dims = get_onnx_input_shape(args.model)
    print("ONNX input '%s' shape = %s" % (inp_name, dims))

    if len(dims) != 4:
        sys.exit("LOI: input khong phai 4 chieu. ONNX nay khong phai model anh?")

    H = args.input_height or dims[2]
    W = args.input_width or dims[3]
    if H <= 0 or W <= 0:
        sys.exit("LOI: ONNX co shape dong. Export lai voi dynamic=False, "
                 "hoac truyen --input_width/--input_height thu cong.")

    input_shape = [1, 3, H, W]
    print("Dung input_shape =", input_shape)
    print()
    print(">>> GHI NHO CON SO NAY: main.py tren K230 phai dat")
    print(">>>     model_input_size = [%d, %d]" % (W, H))
    print()

    out = args.output or os.path.splitext(args.model)[0] + ".kmodel"

    # --- Compile options: theo dung tai lieu Kendryte ---
    opt = nncase.CompileOptions()
    opt.target = args.target
    opt.preprocess = True             # nhung buoc tien xu ly vao kmodel
    opt.swapRB = False                # webcam da cho RGB, khong doi kenh
    opt.input_shape = input_shape
    opt.input_type = "uint8"
    opt.input_range = [0, 255]
    opt.mean = [0, 0, 0]
    opt.std = [255, 255, 255]         # uint8 [0,255] -> float [0,1] cho YOLO
    opt.input_layout = "NCHW"
    opt.output_layout = "NCHW"
    opt.letterbox_value = 114         # mau padding chuan cua YOLO
    opt.dump_ir = False
    opt.dump_asm = True
    opt.dump_dir = "nncase_dump"

    compiler = nncase.Compiler(opt)

    print("Import ONNX...")
    compiler.import_onnx(read_model_file(args.model), nncase.ImportOptions())

    print("Chuan bi du lieu calibration...")
    ptq = nncase.PTQTensorOptions()
    data = generate_data(input_shape, args.samples, args.dataset)
    ptq.samples_count = len(data)
    ptq.set_tensor_data(data)
    ptq.calibrate_method = args.calibrate_method
    ptq.quant_type = args.quant_type
    ptq.w_quant_type = args.quant_type
    compiler.use_ptq(ptq)

    print("Compile (buoc nay lau, vai phut)...")
    compiler.compile()

    kmodel = compiler.gencode_tobytes()
    with open(out, "wb") as f:
        f.write(kmodel)

    print()
    print("=" * 60)
    print("XONG:", out, "(%.2f MB)" % (len(kmodel) / 1024 / 1024))
    print("=" * 60)
    print("Buoc tiep: copy file nay vao the SD, roi sua main.py:")
    print('    kmodel_path = "/sdcard/%s"' % os.path.basename(out))
    print("    model_input_size = [%d, %d]" % (W, H))


if __name__ == "__main__":
    main()
