# -*- encoding=utf8 -*-
"""
独立运行入口（不依赖 Airtest）
用法:
  python run_standalone.py ocr <图片路径> [区域 x1,y1,x2,y2]
  python run_standalone.py targets [王国]
  python run_standalone.py info <城池ID>
"""
import sys
import os
import re

_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)

# 不导入 airtest，仅加载数据处理和 OCR 逻辑
import cv2
from city_data import CITIES, NEIGHBORS, get_border_targets


def _get_ocr_standalone():
    """独立模式的 OCR 加载"""
    try:
        import easyocr
        return ('easyocr', easyocr.Reader(['ch_sim'], gpu=False))
    except Exception:
        pass
    try:
        from rapidocr_onnxruntime import RapidOCR
        return ('rapid', RapidOCR())
    except Exception:
        pass
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        return ('tesseract', pytesseract)
    except Exception:
        pass
    raise ImportError("未找到 OCR 库，请: pip install easyocr 或 rapidocr-onnxruntime 或 pytesseract")


def _preprocess(roi, scale=4, thresh=110):
    big = cv2.resize(roi, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
    inv = 255 - binary
    return cv2.copyMakeBorder(inv, 25, 25, 25, 25, cv2.BORDER_CONSTANT, value=255)


def ocr_image(img_path, region=None):
    """对本地图片做 OCR，region=(x1,y1,x2,y2) 或 None 表示全图"""
    img = cv2.imread(img_path)
    if img is None:
        print("无法读取图片:", img_path)
        return ""
    if region:
        x1, y1, x2, y2 = region
        roi = img[y1:y2, x1:x2]
    else:
        roi = img
    processed = _preprocess(roi)
    engine, reader = _get_ocr_standalone()
    text = ""
    if engine == 'easyocr':
        p = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
        out = reader.readtext(p, detail=0, paragraph=True)
        text = re.sub(r'[^\u4e00-\u9fff]', '', ''.join(out))
    elif engine == 'rapid':
        r, _ = reader(processed)
        if r:
            text = re.sub(r'[^\u4e00-\u9fff]', '', ''.join(x[1] for x in r))
    elif engine == 'tesseract':
        from PIL import Image
        text = reader.image_to_string(Image.fromarray(processed), lang='chi_sim', config='--psm 7')
        text = re.sub(r'[^\u4e00-\u9fff]', '', text)
    return text.strip()


def cmd_ocr(args):
    if len(args) < 2:
        print("用法: python run_standalone.py ocr <图片路径> [x1,y1,x2,y2]")
        return
    path = args[1]
    region = None
    if len(args) >= 3:
        pts = [int(x) for x in args[2].replace(',', ' ').split()]
        if len(pts) == 4:
            region = tuple(pts)
    print("OCR 引擎加载中...")
    text = ocr_image(path, region)
    # 去除速来（若为聊天页城池）
    text = text.replace("速来", "").strip()
    print("识别结果:", text)


def cmd_targets(args):
    kingdom = args[1] if len(args) > 1 else 'wei'
    targets = get_border_targets(kingdom)
    print(f"\n{kingdom.upper()} 国可攻击交界城池 ({len(targets)} 个):")
    for t in targets[:30]:
        info = CITIES[t['id']]
        name = info[3] if len(info) > 3 else "?"
        print(f"  #{t['id']} {name} ({t['pos'][0]},{t['pos'][1]})")
    if len(targets) > 30:
        print(f"  ... 共 {len(targets)} 个")


def cmd_info(args):
    if len(args) < 2:
        print("用法: python run_standalone.py info <城池ID>")
        return
    cid = int(args[1])
    if cid not in CITIES:
        print("城池不存在")
        return
    info = CITIES[cid]
    nbs = NEIGHBORS.get(cid, [])
    print(f"城池 #{cid}: {info}")
    print(f"邻居: {nbs}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1].lower()
    args = sys.argv[2:]
    if cmd == 'ocr':
        cmd_ocr(args)
    elif cmd == 'targets':
        cmd_targets(args)
    elif cmd == 'info':
        cmd_info(args)
    else:
        print("未知命令:", cmd)
        print(__doc__)


if __name__ == '__main__':
    main()
