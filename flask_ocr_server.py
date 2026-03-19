import os
import cv2
import numpy as np
from flask import Flask, request, jsonify

app = Flask(__name__)

# 全局 OCR 引擎实例
ocr_engine = None

def init_ocr():
    global ocr_engine
    try:
        from rapidocr_onnxruntime import RapidOCR
        ocr_engine = RapidOCR()
        print("[Server] RapidOCR initialized.")
        return
    except ImportError:
        pass
        
    try:
        from paddleocr import PaddleOCR
        ocr_engine = PaddleOCR(use_angle_cls=False, lang="ch", show_log=False)
        print("[Server] PaddleOCR initialized.")
    except ImportError:
        print("[Server] No OCR engine found. Please install rapidocr_onnxruntime or paddleocr.")

init_ocr()

@app.route('/ocr', methods=['POST'])
def ocr_api():
    if 'image' not in request.files:
        return jsonify({"error": "No image part in the request"}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        # 读取上传的图片转换为 numpy array
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({"error": "Failed to decode image"}), 400

        texts = []
        if ocr_engine is not None:
            # 兼容 RapidOCR 和 PaddleOCR 的调用
            engine_name = ocr_engine.__class__.__name__
            if "RapidOCR" in engine_name:
                result, _ = ocr_engine(img)
                if result:
                    for item in result:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            texts.append(item[1])
            elif "PaddleOCR" in engine_name:
                result = ocr_engine.ocr(img)
                if result:
                    if isinstance(result, list) and result and isinstance(result[0], dict):
                        # V3/PaddleX
                        for page in result:
                            rec_texts = page.get("rec_texts") or []
                            for t in rec_texts:
                                if t is not None and str(t).strip() != "":
                                    texts.append(str(t))
                    else:
                        # V2
                        for line in result:
                            if not line: continue
                            for item in line:
                                if isinstance(item, (list, tuple)) and len(item) >= 2:
                                    texts.append(str(item[1][0]))
        
        full_text = "".join(texts).strip()
        print(f"[Server] Recognized text: {full_text}")
        return jsonify({"text": full_text})

    except Exception as e:
        print(f"[Server] OCR Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Starting OCR Server on 0.0.0.0:5000 ...")
    app.run(host='0.0.0.0', port=5000)
