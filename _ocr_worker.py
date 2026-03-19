# -*- encoding=utf8 -*-
"""
OCR 子进程 Worker —— 独立于 Airtest 运行，避免 DLL 冲突。
从 stdin 读取图片路径（每行一个），OCR 识别后将纯中文结果写入 stdout。
通信协议：stdin/stdout 均使用 UTF-8 编码，每行一条消息。
"""
import sys
import os
import re
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')

try:
    from rapidocr_onnxruntime import RapidOCR
    import cv2
    ocr = RapidOCR()
    sys.stdout.write("READY\n")
    sys.stdout.flush()
except Exception as e:
    sys.stdout.write("ERROR:" + str(e) + "\n")
    sys.stdout.flush()
    sys.exit(1)

for line in sys.stdin:
    path = line.strip()
    if not path:
        sys.stdout.write("\n")
        sys.stdout.flush()
        continue
    try:
        img = cv2.imread(path)
        if img is None:
            sys.stdout.write("\n")
            sys.stdout.flush()
            continue
        result, _ = ocr(img)
        if result:
            text = ''.join(item[1] for item in result)
            text = re.sub(r'[^\u4e00-\u9fff]', '', text)
            sys.stdout.write(text + "\n")
        else:
            sys.stdout.write("\n")
        sys.stdout.flush()
    except Exception:
        sys.stdout.write("\n")
        sys.stdout.flush()
