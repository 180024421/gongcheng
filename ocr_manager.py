import os
import cv2
import numpy as np
import requests
from typing import Union

ImageInput = Union[str, np.ndarray]

class OCRManager:
    """
    网络版 OCR 管理器 (用于 APK 打包)
    该类会替换原有的 PaddleOCR/RapidOCR 逻辑，将图片发送到 PC 端运行的 Web 服务进行识别。
    """
    def __init__(self, use_gpu: bool = False, lang: str = "ch"):
        # 从环境变量获取 PC 服务器的 IP 地址 (由 main.py Kivy 界面设置)
        self.server_url = os.environ.get("OCR_SERVER_URL", "http://192.168.1.100:5000/ocr")
        print(f"[OCR_Client] Initialized. Target server: {self.server_url}")

    def _load_image(self, image: ImageInput) -> np.ndarray:
        if isinstance(image, np.ndarray):
            return image
        img = cv2.imread(str(image))
        if img is None:
            raise ValueError(f"无法读取图片: {image}")
        return img

    def _request_ocr(self, img: np.ndarray) -> str:
        try:
            # 将 numpy array 编码为 JPEG 格式
            _, img_encoded = cv2.imencode('.jpg', img)
            files = {'image': ('image.jpg', img_encoded.tobytes(), 'image/jpeg')}
            
            # 发送 POST 请求到服务器
            response = requests.post(self.server_url, files=files, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("text", "")
            else:
                print(f"[OCR_Client] Server returned status code: {response.status_code}")
                return ""
        except Exception as e:
            print(f"[OCR_Client] Request failed: {e}")
            return ""

    def get_region_text_only(self, image: ImageInput, x1: int, y1: int, x2: int, y2: int, crop_padding: int = 3) -> str:
        """截取指定区域并发送给服务器识别"""
        try:
            img = self._load_image(image)
            h, w = img.shape[:2]
            
            x1 = max(0, x1 - crop_padding)
            y1 = max(0, y1 - crop_padding)
            x2 = min(w, x2 + crop_padding)
            y2 = min(h, y2 + crop_padding)
            
            cropped = img[y1:y2, x1:x2]
            
            # 向服务器请求识别
            result_text = self._request_ocr(cropped)
            return result_text
        except Exception as e:
            print(f"[OCR_Client] Crop or request error: {e}")
            return ""
