# -*- encoding=utf8 -*-
__author__ = "Administrator"

import atexit
import cv2
import numpy as np
import os
import re
import tempfile
from airtest.core.api import *
from airtest.cli.parser import cli_setup

if not cli_setup():
    device_uri = os.environ.get("AIRTEST_DEVICE_URI", "android://127.0.0.1:5037/emulator-5554?")
    auto_setup(__file__, logdir=False, devices=[device_uri])

# 运行时不再保存 Airtest 截图到 log 目录，减少磁盘占用
ST.SAVE_IMAGE = False

# 保证 Airtest 从任意目录运行时都能找到同目录下的 city_data
import sys
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from city_data import (
    CITIES, NEIGHBORS, get_border_targets,
    get_border_targets_from_kingdoms, get_touch_pos,
)

# 融合 ocr_project 的 PaddleOCR 管理器（若未安装 paddleocr，会自动回退到现有 OCR）
try:
    from ocr_manager import OCRManager as _PaddleOCRManager
except Exception:
    _PaddleOCRManager = None

# ==================== 配置 ====================

SCREEN_W, SCREEN_H = 1280, 720
MY_KINGDOM = 'wei'
KINGDOM_LABEL = {'wei': '魏', 'wu': '吴', 'shu': '蜀'}

MAP_OVERVIEW_BTN = (1223, 423)       # 点击此点位打开世界地图
OCR_REGION = (540, 327, 582, 416)    # OCR识别区域 (left, top, right, bottom)
VISIBLE_CITIES_OCR_REGION = (50, 50, 1230, 670)  # 当前页面地图区域，OCR 识别可见城池名
CHAT_CITY_OCR_REGION = (376, 500, 533, 549)  # 聊天页城池文字 OCR 区域
POPUP_BTN = (666, 431)               # 点击城池后弹窗内的固定按钮
ATTACK_LOOP_WAIT_SEC = 30            # 点击后等待秒数
BTN_66_177 = (66, 177)               # 固定点位，用于弹窗操作
# 点击 POPUP_BTN 后在范围内查找的图片 (648,433,681,455)
TPL_CLICK_REGION = (648, 433, 681, 455)
TPL_CLICK_AFTER_POPUP = "tpl1773581337008.png"   # 点击按钮后需点击的图
# 点击 TPL_CLICK_AFTER_POPUP 后，如果此区域识别到“不”，表示城池无法前往
UNREACHABLE_OCR_REGION = (686, 308, 718, 384)
# 点击 66,177 后弹出页面中的「单挑」检测范围 (1175,218,1235,240)
TPL_DAN_TIAO_REGION = (1175, 218, 1235, 240)
TPL_DAN_TIAO = "tpl1773581904344.png"            # 单挑
# 单挑后的子流程：展开、撤退、手动/自动、退出
TPL_ZHAN_KAI = "tpl1773582946677.png"            # 展开 (20,330,50,355)
TPL_ZHAN_KAI_REGION = (20, 330, 50, 355)
TPL_TUI_TUI = "tpl1773583007294.png"             # 撤退 (74,156,997,178)
TPL_TUI_TUI_REGION = (74, 156, 997, 178)
TPL_SHOU_DONG = "tpl1773583315159.png"           # 手动 (486,539,787,614)
TPL_ZI_DONG = "tpl1773583396096.png"             # 自动 (486,539,787,614)
TPL_AUTO_MANUAL_REGION = (486, 539, 787, 614)
TPL_TUI_CHU = "tpl1773583470830.png"             # 退出 (717,603,749,627)
TPL_TUI_CHU_REGION = (717, 603, 749, 627)
SHARE_COOLDOWN = 60                  # 分享被限制时等待秒数
CITY_DATA_FILE = os.path.join(os.path.dirname(__file__), "city_data.py")

# 点完 TPL_CLICK_AFTER_POPUP 后，用 OCR 轮询此小区域文字
STATUS_OCR_REGION = (37, 172, 59, 200)  # (left, top, right, bottom)
SINGLE_DUEL_OCR_REGION = (999, 639, 1028, 674)  # 单挑：出现任意单字则点击中心
AUTO_MANUAL_OCR_REGION = (546, 549, 575, 582)   # 自动/手动：出现“自/手”则点击中心切换
# 单挑后判断区域：识别“国”或单字
SINGLE_OR_GUO_REGION = (87, 159, 115, 188)
# 退出按钮改为 OCR：出现“退”则点击中心
EXIT_TUI_REGION = (694, 600, 720, 630)

# 运行时临时图片，退出时清理
_ocr_snap_path = os.path.join(_script_dir, "_ocr_snap.png")


def _cleanup_temp_images():
    """退出时删除运行时生成的临时图片"""
    try:
        if os.path.isfile(_ocr_snap_path):
            os.remove(_ocr_snap_path)
    except Exception:
        pass


atexit.register(_cleanup_temp_images)

# 模板图片（1280x720），用于 collect_city_names 流程
def _tpl(name):
    return os.path.join(_script_dir, name)
TPL_HUAN_YE = Template(_tpl("tpl1773537118491.png"), record_pos=(-0.08, 0.13), resolution=(1280, 720))      # 换页
TPL_FEN_XIANG = Template(_tpl("tpl1773537146262.png"), record_pos=(0.005, 0.075), resolution=(1280, 720))   # 分享
TPL_LIAO_TIAN = Template(_tpl("tpl1773537279130.png"), record_pos=(-0.465, 0.25), resolution=(1280, 720))   # 聊天
TPL_GUAN_BI = Template(_tpl("tpl1773537435006.png"), record_pos=(0.013, 0.002), resolution=(1280, 720))     # 关闭聊天

# 世界地图三国点位参考色 (BGR，根据三国图 tpl1773477536988 取色)
# 蜀=红 RGB(227,60,56), 吴=绿 RGB(69,192,60), 魏=蓝 RGB(73,115,207)
KINGDOM_COLORS_BGR = {
    'shu': np.array([56, 60, 227], dtype=np.float32),   # 蜀 红
    'wu': np.array([60, 192, 69], dtype=np.float32),    # 吴 绿
    'wei': np.array([207, 115, 73], dtype=np.float32),  # 魏 蓝
}


# ==================== OCR 初始化 ====================

import subprocess as _sp

_ocr_engine = None   # 'easyocr' | 'rapid' | 'rapid_sub' | 'tesseract'
_ocr_reader = None


def _find_python_exe():
    """找到当前 Python 解释器的真实路径（Airtest IDE 的 sys.executable 可能是 IDE 自身）"""
    exe = sys.executable
    if "python" in os.path.basename(exe).lower():
        return exe
    try:
        import site
        for sp in site.getsitepackages():
            py_home = os.path.dirname(os.path.dirname(sp))
            for name in ("python.exe", "python3.exe"):
                candidate = os.path.join(py_home, name)
                if os.path.isfile(candidate):
                    return candidate
    except Exception:
        pass
    return exe

def _build_clean_env(python_exe):
    """
    为 OCR 子进程构建一个干净的环境，仅包含 Python 和系统必要路径。
    Airtest IDE 的环境可能污染 PATH/PYTHONHOME 导致 DLL 加载失败。
    """
    py_dir = os.path.dirname(python_exe)
    sys_root = os.environ.get('SystemRoot', r'C:\Windows')
    clean_path = ';'.join(filter(os.path.isdir, [
        py_dir,
        os.path.join(py_dir, 'DLLs'),
        os.path.join(py_dir, 'Scripts'),
        os.path.join(py_dir, 'Lib', 'site-packages', 'onnxruntime', 'capi'),
        os.path.join(sys_root, 'System32'),
        sys_root,
    ]))
    env = {
        'PATH': clean_path,
        'SystemRoot': sys_root,
        'TEMP': os.environ.get('TEMP', os.path.join(sys_root, 'Temp')),
        'TMP': os.environ.get('TMP', os.environ.get('TEMP', '')),
        'PYTHONIOENCODING': 'utf-8',
        'USERPROFILE': os.environ.get('USERPROFILE', ''),
        'APPDATA': os.environ.get('APPDATA', ''),
        'LOCALAPPDATA': os.environ.get('LOCALAPPDATA', ''),
    }
    for k in ('PYTHONHOME', 'PYTHONPATH'):
        env.pop(k, None)
    return env


class _SubprocessOCR:
    """通过独立子进程运行 rapidocr，避免 Airtest 环境 DLL 冲突"""

    def __init__(self):
        python_exe = _find_python_exe()
        worker = os.path.join(_script_dir, '_ocr_worker.py')
        env = _build_clean_env(python_exe)
        self.proc = _sp.Popen(
            [python_exe, worker],
            stdin=_sp.PIPE, stdout=_sp.PIPE, stderr=_sp.PIPE,
            cwd=_script_dir, env=env,
        )
        import io
        self._stdin = io.TextIOWrapper(self.proc.stdin, encoding='utf-8', line_buffering=True)
        self._stdout = io.TextIOWrapper(self.proc.stdout, encoding='utf-8')
        line = self._stdout.readline().strip()
        if not line.startswith('READY'):
            self.proc.kill()
            raise RuntimeError("OCR worker 启动失败: " + line)

    def recognize(self, image_path):
        self._stdin.write(image_path + '\n')
        self._stdin.flush()
        return self._stdout.readline().strip()

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def _fix_dll_paths():
    """
    修复 Airtest IDE 环境下 DLL 加载失败。
    Airtest 可能修改 PATH，导致 PyTorch/ONNX 加载到错误 DLL。
    将 Python 及依赖的 DLL 目录置于 PATH 最前，并注册 add_dll_directory。
    """
    if sys.platform != 'win32':
        return
    py_exe = sys.executable
    if 'python' not in os.path.basename(py_exe).lower():
        try:
            import site
            for sp in site.getsitepackages():
                ph = os.path.dirname(os.path.dirname(sp))
                for n in ('python.exe', 'python3.exe'):
                    c = os.path.join(ph, n)
                    if os.path.isfile(c):
                        py_exe = c
                        break
        except Exception:
            pass
    py_dir = os.path.dirname(py_exe)
    dirs = [py_dir, os.path.join(py_dir, 'DLLs')]
    try:
        import site
        for sp in site.getsitepackages():
            dirs.extend([
                os.path.join(sp, 'torch', 'lib'),
                os.path.join(sp, 'onnxruntime', 'capi'),
            ])
    except Exception:
        pass
    path_front = ';'.join(d for d in dirs if os.path.isdir(d))
    if path_front:
        os.environ['PATH'] = path_front + ';' + os.environ.get('PATH', '')
    # Airtest 可能设置 PYTHONHOME 指向自带 Python，干扰 DLL 查找
    for k in ('PYTHONHOME', 'PYTHONPATH'):
        os.environ.pop(k, None)
    if hasattr(os, 'add_dll_directory'):
        for d in dirs:
            if os.path.isdir(d):
                try:
                    os.add_dll_directory(d)
                except OSError:
                    pass


def _get_ocr():
    """
    加载 OCR 引擎（自动选择可用引擎）。
    优先级：easyocr → rapidocr → pytesseract（Python 3.13 推荐 easyocr）
    """
    global _ocr_engine, _ocr_reader
    if _ocr_reader is not None:
        return _ocr_engine, _ocr_reader

    # --- 第一选择: easyocr ---
    _fix_dll_paths()  # 在导入前修复 DLL 路径，避免 Airtest 环境干扰
    try:
        import easyocr
        _ocr_reader = easyocr.Reader(['ch_sim'], gpu=False)
        _ocr_engine = 'easyocr'
        print("[OCR] 引擎已加载 (easyocr)")
        return _ocr_engine, _ocr_reader
    except Exception as e:
        print("[OCR] easyocr 不可用: %s" % e)

    # --- 第二选择: rapidocr ---
    try:
        _fix_dll_paths()
        from rapidocr_onnxruntime import RapidOCR
        _ocr_reader = RapidOCR()
        _ocr_engine = 'rapid'
        print("[OCR] 引擎已加载 (rapidocr-onnxruntime)")
        return _ocr_engine, _ocr_reader
    except Exception as e:
        print("[OCR] rapidocr 不可用: %s" % e)

    # --- 第三选择: pytesseract ---
    try:
        import pytesseract
        _tess_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for tp in _tess_paths:
            if os.path.isfile(tp):
                pytesseract.pytesseract.tesseract_cmd = tp
                break
        pytesseract.get_tesseract_version()
        _ocr_reader = pytesseract
        _ocr_engine = 'tesseract'
        print("[OCR] 引擎已加载 (pytesseract + Tesseract-OCR)")
        return _ocr_engine, _ocr_reader
    except Exception as e:
        print("[OCR] pytesseract 不可用: %s" % e)

    raise ImportError(
        "所有 OCR 引擎均不可用。请任选一种方案：\n"
        "  方案A（推荐）: pip install easyocr\n"
        "  方案B: pip install rapidocr-onnxruntime\n"
        "  方案C: pip install pytesseract 并安装 Tesseract-OCR"
    )







def _edit_distance(a, b):
    """计算两个字符串的编辑距离（Levenshtein）"""
    la, lb = len(a), len(b)
    dp = list(range(lb + 1))
    for i in range(1, la + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, lb + 1):
            tmp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = tmp
    return dp[lb]


# ==================== OCR 截图与识别 ====================


def _preprocess_for_ocr(roi, scale=4, thresh=110):
    """
    将游戏文字转为白底黑字，方便 OCR 识别。
    支持两种风格：①深色背景+浅色字 ②浅色背景+白字深色描边
    """
    big = cv2.resize(roi, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    pad = 25
    # 方案A：高阈值+反转（深色背景金色字）
    _, bin_a = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
    inv_a = 255 - bin_a
    # 方案B：低阈值不反转（浅色背景+白字深色描边）
    _, bin_b = cv2.threshold(gray, 90, 255, cv2.THRESH_BINARY)
    # 返回方案A（兼容旧图），实际会多策略尝试
    out = cv2.copyMakeBorder(inv_a, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)
    return out


def _preprocess_variants(roi):
    """生成多种预处理结果，供多策略 OCR 使用"""
    scale = 4
    big = cv2.resize(roi, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    pad = 25
    variants = []
    # 深色背景：高阈值+反转
    for thresh in [100, 110, 120]:
        _, b = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
        variants.append(cv2.copyMakeBorder(255 - b, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255))
    # 浅色背景白字描边：低阈值不反转
    for thresh in [80, 90, 100]:
        _, b = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
        variants.append(cv2.copyMakeBorder(b, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255))
    # 原图放大
    variants.append(cv2.copyMakeBorder(big, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(255, 255, 255)))
    return variants


def ocr_region(region=OCR_REGION, pad=8, retry=3):
    """
    截图并对指定区域进行 OCR 识别，返回识别文本。
    - 区域自动向外扩展 pad 像素
    - 对游戏字体做预处理（深色背景金色字 → 白底黑字）
    - OCR 结果会用三国城池字典进行纠正
    - 失败时自动重试 retry 次
    """
    engine, reader = _get_ocr()

    for attempt in range(1, retry + 1):
        try:
            from airtest.core.api import G
            img = G.DEVICE.snapshot(quality=99)
        except Exception:
            img = None
        if img is None:
            snapshot(filename=_ocr_snap_path)
            img = cv2.imread(_ocr_snap_path)
        if img is None:
            continue

        h, w = img.shape[:2]
        l, t, r, b = region
        l2 = max(0, l - pad)
        t2 = max(0, t - pad)
        r2 = min(w, r + pad)
        b2 = min(h, b + pad)
        roi = img[t2:b2, l2:r2]

        text = ""
        variants = _preprocess_variants(roi)

        if engine == 'easyocr':
            for processed in variants:
                if len(processed.shape) == 2:
                    processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
                results = reader.readtext(processed, detail=0, paragraph=True)
                t = re.sub(r'[^\u4e00-\u9fff]', '', ''.join(results).strip())
                if t:
                    text = t
                    break
            if not text:
                processed = _preprocess_for_ocr(roi)
                if len(processed.shape) == 2:
                    processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
                results = reader.readtext(processed, detail=0, paragraph=True)
                text = re.sub(r'[^\u4e00-\u9fff]', '', ''.join(results).strip()) if results else ''
        elif engine == 'rapid':
            processed = _preprocess_for_ocr(roi)
            result, _ = reader(processed)
            if result:
                text = ''.join(item[1] for item in result)
        elif engine == 'rapid_sub':
            processed = _preprocess_for_ocr(roi)
            fd, tmp = tempfile.mkstemp(suffix='.png', prefix='_ocr_')
            try:
                os.close(fd)
                cv2.imwrite(tmp, processed)
                text = reader.recognize(tmp)
            finally:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
        elif engine == 'tesseract':
            processed = _preprocess_for_ocr(roi)
            from PIL import Image
            pil_img = Image.fromarray(processed)
            text = reader.image_to_string(pil_img, lang='chi_sim', config='--psm 7')

        text = re.sub(r'[^\u4e00-\u9fff]', '', text)
        if text:
            return text

        if attempt < retry:
            print("  [OCR] 第%d次为空，重试..." % attempt)
            sleep(1)

    return ""


def get_visible_city_ids_from_screen(region=None):
    """
    根据当前页面截图 OCR 识别可见的城池名称，匹配 CITIES 返回城池 ID 集合。
    """
    r = region or VISIBLE_CITIES_OCR_REGION
    text = ocr_region(r, pad=16, retry=2)
    if not text:
        print("[OCR] 当前页面未识别到城池文字")
        return set()
    visible = set()
    for cid, info in CITIES.items():
        name = info[3] if len(info) > 3 else ""
        if len(name) >= 2 and name in text:
            visible.add(cid)
    return visible


# ==================== 世界地图与可攻击城池 ====================

def open_world_map():
    """点击固定点位 (1223, 423) 打开世界地图"""
    touch(MAP_OVERVIEW_BTN)
    sleep(2)


def _classify_by_rgb(bgr_sample, refs=None, max_dist=55):
    """
    根据 BGR 采样与三国参考色比较，返回最接近的国家。
    refs: KINGDOM_COLORS_BGR，max_dist: 允许的最大欧氏距离。
    """
    if bgr_sample is None or bgr_sample.size == 0:
        return None
    refs = refs or KINGDOM_COLORS_BGR
    if len(bgr_sample.shape) == 3:
        color = np.array([
            float(np.median(bgr_sample[:, :, 0])),
            float(np.median(bgr_sample[:, :, 1])),
            float(np.median(bgr_sample[:, :, 2])),
        ], dtype=np.float32)
    else:
        return None
    # 排除过暗/过浅（背景、连接线等）
    if np.mean(color) < 40 or np.mean(color) > 235:
        return None
    best_k, best_d = None, max_dist + 1
    for k, ref in refs.items():
        d = np.sqrt(np.sum((color - ref) ** 2))
        if d < best_d:
            best_d, best_k = d, k
    return best_k if best_d <= max_dist else None


def detect_kingdoms_from_world_map(img, radius=7, max_color_dist=69):
    """
    在世界地图截图上，根据各城池坐标处的 RGB 取色识别实时占领情况。
    参考色取自三国图：蜀红(227,60,56)、吴绿(69,192,60)、魏蓝(73,115,207)。
    返回 {city_id: 'wei'|'wu'|'shu'}，未识别到的城池不包含。
    """
    if img is None:
        return {}
    if isinstance(img, np.ndarray):
        screen = img
    else:
        screen = cv2.imread(img) if isinstance(img, str) else np.array(img)
    if screen is None:
        return {}
    h, w = screen.shape[:2]
    kingdom_map = {}
    for cid, info in CITIES.items():
        x, y = int(info[0]), int(info[1])
        if x < 0 or x >= w or y < 0 or y >= h:
            continue
        x1 = max(0, x - radius)
        x2 = min(w, x + radius + 1)
        y1 = max(0, y - radius)
        y2 = min(h, y + radius + 1)
        roi = screen[y1:y2, x1:x2]
        k = _classify_by_rgb(roi, max_dist=max_color_dist)
        if k:
            kingdom_map[cid] = k
    return kingdom_map


def get_attackable_from_world_map(img=None, my_kingdom=MY_KINGDOM):
    """
    根据世界地图截图识别可攻击的敌方城池。
    - 按 RGB 取色得到 kingdom_map（蜀红/吴绿/魏蓝）
    - 筛选与己方交界的敌方城池
    若 img 为 None，则先打开世界地图并截图。
    """
    if img is None:
        open_world_map()
        try:
            from airtest.core.api import G
            img = G.DEVICE.snapshot(quality=99)
        except Exception:
            pass
        if img is None:
            snapshot(filename=_ocr_snap_path)
            img = cv2.imread(_ocr_snap_path)
        sleep(0.5)
    kingdom_map = detect_kingdoms_from_world_map(img)
    targets = get_border_targets_from_kingdoms(kingdom_map, my_kingdom)
    return targets, kingdom_map


def _find_template_in_region(screen, tpl_name, region, threshold=0.7):
    """在指定区域内模板匹配，返回匹配中心坐标或 None。"""
    tpl_path = os.path.join(_script_dir, tpl_name)
    if not os.path.isfile(tpl_path):
        return None
    tpl = cv2.imread(tpl_path)
    if tpl is None:
        return None
    l, t, r, b = region
    roi = screen[t:b, l:r]
    if roi.size == 0:
        return None
    th, tw = tpl.shape[:2]
    if th > roi.shape[0] or tw > roi.shape[1]:
        return None
    res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    if max_val >= threshold:
        return (l + max_loc[0] + tw // 2, t + max_loc[1] + th // 2)
    return None


def _find_and_click_template_in_region(tpl_name, region, threshold=0.7):
    """截图后在区域内查找模板并点击，找到返回 True 否则 False。"""
    try:
        from airtest.core.api import G
        img = G.DEVICE.snapshot(quality=99)
    except Exception:
        img = None
    if img is None:
        snapshot(filename=_ocr_snap_path)
        img = cv2.imread(_ocr_snap_path)
    if img is None:
        return False
    if isinstance(img, np.ndarray):
        screen = img.copy()
    else:
        screen = np.array(img)
    if len(screen.shape) == 2:
        screen = cv2.cvtColor(screen, cv2.COLOR_GRAY2BGR)
    elif screen.shape[2] == 3:
        try:
            # 远程 bridge 返回 BGR，无需转换；Airtest 返回 RGB 需转 BGR
            if not getattr(sys.modules.get('remote_bridge'), 'returns_bgr', False):
                screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
        except Exception:
            pass
    pos = _find_template_in_region(screen, tpl_name, region, threshold)
    if pos:
        touch(pos)
        return True
    return False


def _exists_template_in_region(tpl_name, region, threshold=0.7):
    """截图后在区域内仅检测模板是否存在，不点击。"""
    try:
        from airtest.core.api import G
        img = G.DEVICE.snapshot(quality=99)
    except Exception:
        img = None
    if img is None:
        snapshot(filename=_ocr_snap_path)
        img = cv2.imread(_ocr_snap_path)
    if img is None:
        return False
    if isinstance(img, np.ndarray):
        screen = img.copy()
    else:
        screen = np.array(img)
    if len(screen.shape) == 2:
        screen = cv2.cvtColor(screen, cv2.COLOR_GRAY2BGR)
    elif screen.shape[2] == 3:
        try:
            if not getattr(sys.modules.get('remote_bridge'), 'returns_bgr', False):
                screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
        except Exception:
            pass
    return _find_template_in_region(screen, tpl_name, region, threshold) is not None


def _ocr_status_text_once():
    """
    识别 STATUS_OCR_REGION 的文字，优先 PaddleOCR，否则回退到现有 ocr_region。
    返回清洗后的中文文本（只保留汉字）。
    """
    l, t, r, b = STATUS_OCR_REGION

    # PaddleOCR（更适合小区域、单字）
    if _PaddleOCRManager is not None:
        try:
            from airtest.core.api import G
            img = G.DEVICE.snapshot(quality=99)
        except Exception:
            img = None
        if img is None:
            snapshot(filename=_ocr_snap_path)
            img = cv2.imread(_ocr_snap_path)
        if img is not None:
            ocr = getattr(_ocr_status_text_once, "_paddle_ocr", None)
            if ocr is None:
                try:
                    ocr = _PaddleOCRManager(use_gpu=False, lang="ch")
                    setattr(_ocr_status_text_once, "_paddle_ocr", ocr)
                except Exception:
                    ocr = None
            if ocr is not None:
                txt = ocr.get_region_text_only(img, l, t, r, b)
                return re.sub(r"[^\u4e00-\u9fff]", "", txt or "")

    # 回退：用现有 OCR 引擎（easyocr/rapid/tesseract）
    txt = ocr_region(STATUS_OCR_REGION, pad=2, retry=1)
    return re.sub(r"[^\u4e00-\u9fff]", "", txt or "")


def wait_status_ready(timeout_sec=30, interval_sec=1.0):
    """
    点完按钮后轮询 STATUS_OCR_REGION：
    - 若识别结果为“国”或任意单字（len==1）则认为 ready，返回 True
    - 超时仍未识别到则返回 False（用于重新查找城池）
    """
    end_ts = time.time() + float(timeout_sec)
    last = ""
    while time.time() < end_ts:
        txt = _ocr_status_text_once()
        if txt:
            last = txt
            if txt == "国" or len(txt) == 1:
                print(f"  [OCR] 状态已就绪: [{txt}]")
                return True
            print(f"  [OCR] 状态未就绪: [{txt}]")
        else:
            print("  [OCR] 状态未识别到")
        sleep(interval_sec)
    print(f"  [OCR] 超时未就绪（最后一次: [{last}]），将重新查找城池")
    return False


def _region_center(region):
    l, t, r, b = region
    return (int((l + r) / 2), int((t + b) / 2))


def ocr_cn_text_in_region(region):
    """识别指定区域中文（仅保留汉字）。"""
    l, t, r, b = region
    if _PaddleOCRManager is not None:
        try:
            from airtest.core.api import G
            img = G.DEVICE.snapshot(quality=99)
        except Exception:
            img = None
        if img is None:
            snapshot(filename=_ocr_snap_path)
            img = cv2.imread(_ocr_snap_path)
        if img is not None:
            ocr = getattr(_ocr_status_text_once, "_paddle_ocr", None)
            if ocr is None:
                try:
                    ocr = _PaddleOCRManager(use_gpu=False, lang="ch")
                    setattr(_ocr_status_text_once, "_paddle_ocr", ocr)
                except Exception:
                    ocr = None
            if ocr is not None:
                txt = ocr.get_region_text_only(img, l, t, r, b)
                return re.sub(r"[^\u4e00-\u9fff]", "", txt or "")
    txt = ocr_region(region, pad=2, retry=1)
    return re.sub(r"[^\u4e00-\u9fff]", "", txt or "")


def click_center_if_ocr_has_any_single_char(region):
    """区域内识别到任意单字（len==1）则点击中心点并返回 True。"""
    txt = ocr_cn_text_in_region(region)
    if txt and len(txt) == 1:
        pos = _region_center(region)
        print(f"  [OCR] 检测到单字[{txt}]，点击中心 {pos}")
        touch(pos)
        return True
    return False


def click_center_if_ocr_has_any_of(region, chars):
    """区域内识别到 chars 中任意字符则点击中心点并返回 True。"""
    txt = ocr_cn_text_in_region(region)
    if txt and any(c in txt for c in chars):
        pos = _region_center(region)
        print(f"  [OCR] 检测到[{txt}] 命中{chars}，点击中心 {pos}")
        touch(pos)
        return True
    return False


def is_city_unreachable_by_ocr():
    """检测 UNREACHABLE_OCR_REGION 是否出现“不”，出现则认为不可前往。"""
    l, t, r, b = UNREACHABLE_OCR_REGION
    # 复用同一套 OCR：优先 PaddleOCR，否则回退
    if _PaddleOCRManager is not None:
        try:
            from airtest.core.api import G
            img = G.DEVICE.snapshot(quality=99)
        except Exception:
            img = None
        if img is None:
            snapshot(filename=_ocr_snap_path)
            img = cv2.imread(_ocr_snap_path)
        if img is not None:
            ocr = getattr(_ocr_status_text_once, "_paddle_ocr", None)
            if ocr is None:
                try:
                    ocr = _PaddleOCRManager(use_gpu=False, lang="ch")
                    setattr(_ocr_status_text_once, "_paddle_ocr", ocr)
                except Exception:
                    ocr = None
            if ocr is not None:
                txt = ocr.get_region_text_only(img, l, t, r, b)
                txt = re.sub(r"[^\u4e00-\u9fff]", "", txt or "")
                if "不" in txt:
                    print(f"  [OCR] 检测到不可前往提示: [{txt}]")
                    return True
                return False

    txt = ocr_region(UNREACHABLE_OCR_REGION, pad=2, retry=1)
    txt = re.sub(r"[^\u4e00-\u9fff]", "", txt or "")
    if "不" in txt:
        print(f"  [OCR] 检测到不可前往提示: [{txt}]")
        return True
    return False


def attack_city_from_world_map(target_id):
    """
    在世界地图已打开的情况下，点击可攻击城池并完成攻击操作。
    1. 点击目标城池进入详细地图
    2. 若有 touch 则点击 touch 坐标，否则点击固定点位 (666, 431)
    """
    if target_id not in CITIES:
        print(f"城池ID {target_id} 不存在")
        return False
    info = CITIES[target_id]
    pos = (info[0], info[1])
    name = info[3] if len(info) > 3 else ""
    touch_pos = get_touch_pos(target_id)
    print(f"点击城池 #{target_id} [{name or '未命名'}] 坐标{pos}")
    touch(pos)
    sleep(1.5)
    print(f"点击攻击按钮 坐标{touch_pos}")
    touch(touch_pos)
    sleep(1.2)
    return True


def find_attackable_cities_on_screen(my_kingdom=MY_KINGDOM):
    """
    打开世界地图，根据 RGB 取色（蜀红/吴绿/魏蓝）识别实时占领情况，
    筛选与己方交界的敌方城池并返回。
    """
    targets, kingdom_map = get_attackable_from_world_map(img=None, my_kingdom=my_kingdom)
    print(f"\n{'='*50}")
    print(f"  {KINGDOM_LABEL[my_kingdom]}国 世界地图可攻击城池")
    print(f"  （共 {len(targets)} 个，仅交界）")
    print(f"{'='*50}\n")
    if targets:
        by_kingdom = {}
        for t in targets:
            by_kingdom.setdefault(t['kingdom'], []).append(t)
        for k, lst in by_kingdom.items():
            print(f"  -> {KINGDOM_LABEL[k]}国: {len(lst)} 个")
        print(f"\n{'序号':>4}  {'ID':>4}  {'阵营':>4}  {'名称':>8}  {'屏幕坐标':>14}")
        print("-" * 55)
        for i, t in enumerate(targets, 1):
            lbl = KINGDOM_LABEL[t['kingdom']]
            nm = t.get('name', '') or '?'
            print(f"{i:>4}  {t['id']:>4}  {lbl+'国':>4}  {nm:>8}  {str(t['pos']):>14}")
    else:
        print("  未识别到可攻击城池（请确认世界地图已正确打开）")
    return targets


# ==================== 保存城池数据 ====================

def _city_order():
    """获取城池写入顺序：有效名称(>=2字)在前，单字或空名在后"""
    def _to_end(cid):
        info = CITIES.get(cid, (0, 0, '', ''))
        n = info[3] if len(info) > 3 else ''
        return not n or len(n) == 1
    keep = sorted(c for c in CITIES if not _to_end(c))
    end = sorted(c for c in CITIES if _to_end(c))
    return keep + end

def save_city_data():
    """将当前内存中的 CITIES / NEIGHBORS 写回 city_data.py"""
    order = _city_order()
    lines = []
    lines.append('# -*- encoding=utf8 -*-')
    lines.append('"""')
    lines.append('城池地图数据 (1280x720 分辨率)')
    lines.append('CITIES[id] = (screen_x, screen_y, kingdom, name)')
    lines.append('NEIGHBORS[id] = [相邻城池id, ...]')
    lines.append('单字或空名城池已排至末尾')
    lines.append('"""')
    lines.append('')
    lines.append('CITIES = {')

    for cid in order:
        info = CITIES[cid]
        x, y, kingdom = info[0], info[1], info[2]
        name = info[3] if len(info) > 3 else ""
        if len(info) > 4:
            tx, ty = info[4][0], info[4][1]
            lines.append(f'    {cid}: ({x}, {y}, "{kingdom}", "{name}", ({tx}, {ty})),')
        else:
            lines.append(f'    {cid}: ({x}, {y}, "{kingdom}", "{name}"),')

    lines.append('}')
    lines.append('')
    lines.append('NEIGHBORS = {')

    for cid in order:
        if cid not in NEIGHBORS:
            continue
        nbs = NEIGHBORS[cid]
        lines.append(f'    {cid}: {nbs},')

    lines.append('}')
    lines.append('')
    lines.append('')
    lines.append("def get_border_targets(my_kingdom='wei'):")
    lines.append('    """获取可攻击的交界敌方城池列表"""')
    lines.append("    my_ids = {cid for cid, v in CITIES.items() if v[2] == my_kingdom}")
    lines.append("    targets = []")
    lines.append("    seen = set()")
    lines.append("    for cid in my_ids:")
    lines.append("        for nb in NEIGHBORS.get(cid, []):")
    lines.append("            if nb not in my_ids and nb not in seen:")
    lines.append("                seen.add(nb)")
    lines.append("                info = CITIES[nb]")
    lines.append("                targets.append({'id': nb, 'pos': (info[0], info[1]),")
    lines.append("                    'kingdom': info[2], 'name': info[3],")
    lines.append("                    'from_ally': cid,")
    lines.append("                    'ally_pos': (CITIES[cid][0], CITIES[cid][1])})")
    lines.append("    return targets")
    lines.append('')

    with open(CITY_DATA_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"[OK] city_data.py 已保存 ({len(CITIES)} 城池)")


# ==================== OCR 采集城池名称 ====================

def collect_city_names(start_id=None):
    """
    自动采集所有未命名城池的名称。

    流程:
      1. 点击 MAP_OVERVIEW_BTN 打开地图概览
      2. 依次点击每个未命名城池
      3. OCR 识别城池名称
      4. 识别到一个立即写回 city_data.py

    参数:
      start_id: 从指定 ID 开始（用于断点续传），None 则从头开始
    """
    unnamed = []
    for cid in sorted(CITIES.keys()):
        info = CITIES[cid]
        name = info[3] if len(info) > 3 else ""
        if not name:
            if start_id is not None and cid < start_id:
                continue
            unnamed.append(cid)

    if not unnamed:
        print("所有城池已有名称，无需采集")
        return

    print(f"{'='*50}")
    print(f"  开始采集城池名称")
    print(f"  待识别: {len(unnamed)} 个")
    print(f"  OCR区域(聊天页): {CHAT_CITY_OCR_REGION}")
    print(f"{'='*50}")

    # 预热 OCR 引擎
    print("初始化 OCR 引擎...")
    _get_ocr()

    # 打开地图概览
    print("打开地图概览...")
    touch(MAP_OVERVIEW_BTN)
    sleep(2)

    collected = 0
    failed = []
    last_ocr_name = None  # 用于检测分享是否被限制

    for i, cid in enumerate(unnamed):
        info = CITIES[cid]
        pos = (info[0], info[1])
        kingdom = info[2]
        lbl = KINGDOM_LABEL.get(kingdom, kingdom)

        # 单城循环：检测到分享被限制时重试
        while True:
            print(f"\n[{i+1}/{len(unnamed)}] 城池 #{cid} ({lbl}国) 坐标{pos}")

            # 1. 点击城池
            touch(pos)
            sleep(1.5)

            # 2. 点击弹窗内固定点位（有 touch 则用 touch，否则用 666,431）
            popup_btn = (info[4] if len(info) > 4 else None) or POPUP_BTN
            touch(popup_btn)
            sleep(1.2)

            # 3. 换页
            if exists(TPL_HUAN_YE):
                touch(TPL_HUAN_YE)
                sleep(0.8)

            # 4. 分享
            if exists(TPL_FEN_XIANG):
                touch(TPL_FEN_XIANG)
                sleep(0.8)

            # 5. 打开聊天
            if exists(TPL_LIAO_TIAN):
                touch(TPL_LIAO_TIAN)
                sleep(1.2)
            else:
                print(f"  [WARN] 未找到聊天按钮，跳过")
                touch(MAP_OVERVIEW_BTN)
                sleep(1.5)
                failed.append(cid)
                break

            # 6. OCR 聊天页城池文字
            name = ocr_region(CHAT_CITY_OCR_REGION)
            name = name.replace("速来", "").strip()
      
            # 判断是否被限制：与上次识别结果一致，说明分享未成功、仍停留在同一页
            if name and last_ocr_name and name == last_ocr_name:
                print(f"  [检测] 与上次相同 [{name}]，疑似分享被限制，等待 {SHARE_COOLDOWN} 秒后重试...")
                if exists(TPL_GUAN_BI):
                    touch(TPL_GUAN_BI)
                    sleep(0.8)
                touch(MAP_OVERVIEW_BTN)
                sleep(1.5)
                sleep(SHARE_COOLDOWN)
                continue  # 重试当前城池

            last_ocr_name = name

            if name:
                print(f"  OCR结果: [{name}]")
                tup = (info[0], info[1], info[2], name)
                if len(info) > 4:
                    tup = tup + (info[4],)
                CITIES[cid] = tup
                collected += 1
            else:
                print(f"  [WARN] 识别为空，跳过")
                tup = (info[0], info[1], info[2], "")
                if len(info) > 4:
                    tup = tup + (info[4],)
                CITIES[cid] = tup
                failed.append(cid)

            # 识别到就立即写回
            save_city_data()

            # 7. 关闭聊天
            if exists(TPL_GUAN_BI):
                touch(TPL_GUAN_BI)
                sleep(0.8)

            # 8. 返回地图概览
            touch(MAP_OVERVIEW_BTN)
            sleep(1.5)
            break


    print(f"\n{'='*50}")
    print(f"  采集完成!")
    print(f"  成功: {collected} 个")
    print(f"  失败: {len(failed)} 个")
    if failed:
        print(f"  失败ID: {failed}")
    print(f"{'='*50}")


def collect_single_city(cid):
    """手动采集单个城池名称（调试用）"""
    if cid not in CITIES:
        print(f"城池 #{cid} 不存在")
        return

    info = CITIES[cid]
    pos = (info[0], info[1])
    print(f"点击城池 #{cid} 坐标{pos}...")

    touch(MAP_OVERVIEW_BTN)
    sleep(2)

    touch(pos)
    sleep(1.5)

    name = ocr_region(OCR_REGION)
    print(f"OCR结果: [{name}]")

    if name:
        tup = (info[0], info[1], info[2], name)
        if len(info) > 4:
            tup = tup + (info[4],)
        CITIES[cid] = tup
        save_city_data()
        print(f"已保存: #{cid} → {name}")

    touch(MAP_OVERVIEW_BTN)
    sleep(1)


# ==================== 交界城池分析 ====================

def find_attackable_cities(my_kingdom=MY_KINGDOM):
    """找出所有可攻击的交界敌方城池"""
    targets = get_border_targets(my_kingdom)
    print(f"\n{'='*50}")
    print(f"  {KINGDOM_LABEL[my_kingdom]}国 可攻击交界城池")
    print(f"{'='*50}")
    print(f"  共 {len(targets)} 个可攻击敌方城池\n")

    by_kingdom = {}
    for t in targets:
        by_kingdom.setdefault(t['kingdom'], []).append(t)
    for k, lst in by_kingdom.items():
        print(f"  -> {KINGDOM_LABEL[k]}国: {len(lst)} 个")

    print(f"\n{'序号':>4}  {'ID':>4}  {'阵营':>4}  {'名称':>8}  {'屏幕坐标':>14}")
    print("-" * 55)
    for i, t in enumerate(targets, 1):
        lbl = KINGDOM_LABEL[t['kingdom']]
        nm = t.get('name', '') or '?'
        print(f"{i:>4}  {t['id']:>4}  {lbl+'国':>4}  {nm:>8}  {str(t['pos']):>14}")
    return targets


def get_attack_path(target_id, my_kingdom=MY_KINGDOM):
    """BFS 找到到达目标城池的最短路径"""
    my_ids = {cid for cid, v in CITIES.items() if v[2] == my_kingdom}
    if target_id in my_ids:
        return [target_id]

    from collections import deque
    queue = deque([target_id])
    visited = {target_id}
    parent = {}

    while queue:
        cur = queue.popleft()
        for nb in NEIGHBORS.get(cur, []):
            if nb in visited:
                continue
            visited.add(nb)
            parent[nb] = cur
            if nb in my_ids:
                path = [nb]
                node = nb
                while node in parent:
                    node = parent[node]
                    path.append(node)
                return path
            queue.append(nb)
    return []


def attack_city(target_id):
    """点击指定城池"""
    if target_id not in CITIES:
        print(f"城池ID {target_id} 不存在")
        return
    info = CITIES[target_id]
    pos = (info[0], info[1])
    name = info[3] if len(info) > 3 else ""
    lbl = KINGDOM_LABEL.get(info[2], info[2])
    print(f"点击 {lbl}国 [{name or '未命名'}] #{target_id} -> {pos}")
    touch(pos)


def show_city_info(city_id):
    """显示指定城池的信息和邻居"""
    if city_id not in CITIES:
        print(f"城池ID {city_id} 不存在")
        return
    info = CITIES[city_id]
    lbl = KINGDOM_LABEL.get(info[2], info[2])
    name = info[3] if len(info) > 3 else ""
    nbs = NEIGHBORS.get(city_id, [])
    print(f"\n城池 #{city_id}: {lbl}国 [{name or '未命名'}]  坐标({info[0]}, {info[1]})")
    print(f"  邻居 ({len(nbs)}个):")
    for nb in nbs:
        ni = CITIES[nb]
        nl = KINGDOM_LABEL.get(ni[2], ni[2])
        nn = ni[3] if len(ni) > 3 else ""
        print(f"    #{nb} {nl}国 [{nn or '?'}] ({ni[0]}, {ni[1]})")

def attack_flow(my_kingdom=MY_KINGDOM, target_index=1):
    """
    完整攻击流程：打开世界地图 → 识别可攻击城池 → 点击第 target_index 个目标进行攻击。
    target_index 从 1 开始。
    """
    targets = find_attackable_cities_on_screen(my_kingdom)
    if not targets:
        print("无可攻击城池")
        return
    idx = max(0, min(target_index - 1, len(targets) - 1))
    t = targets[idx]
    print(f"选择第 {idx + 1} 个目标: #{t['id']} {t.get('name', '')}")
    attack_city_from_world_map(t['id'])


def _run_after_dan_tiao():
    """
    点击单挑之后的子流程：
    - OCR 判断 SINGLE_OR_GUO_REGION：若为单字则先点 BTN_66_177；若为“国”则不点
    - 循环 OCR 自动/手动（自/手）并点击中心切换
    - 退出改为 OCR：EXIT_TUI_REGION 出现“退”则点击中心
    """
    sleep(1.2)
    txt = ocr_cn_text_in_region(SINGLE_OR_GUO_REGION)
    if txt:
        if txt == "国":
            print("    [OCR] 检测到[国]，直接进入自动/手动流程")
        elif len(txt) == 1:
            print(f"    [OCR] 检测到单字[{txt}]，点击 66,177 后进入自动/手动流程")
            touch(BTN_66_177)
            sleep(1)
        else:
            print(f"    [OCR] SINGLE_OR_GUO_REGION 识别到[{txt}]，继续进入自动/手动流程")
    else:
        print("    [OCR] SINGLE_OR_GUO_REGION 未识别到，直接进入自动/手动流程")

    for _ in range(180):
        # 退出：区域出现“退”则点中心
        if click_center_if_ocr_has_any_of(EXIT_TUI_REGION, ("退",)):
            print("    已点击退出，子流程结束")
            return
        # 自动/手动：区域出现“自/手”则点中心切换
        if click_center_if_ocr_has_any_of(AUTO_MANUAL_OCR_REGION, ("自", "手")):
            sleep(1.2)
            continue
        sleep(1)


def attack_loop(my_kingdom=MY_KINGDOM, wait_sec=None):
    """
    攻击流程（只攻击一个城池）：
    1. 查找可攻击点位，取第一个攻击
    2. 点击目标 → 点击 POPUP_BTN → 在 (648,433,681,455) 范围内查找并点击
    3. 等待 30 秒 → 点击 (66,177)
    4. 检测「单挑」→ 点击 → 子流程：展开 → 无撤退则点66,177 → 循环点手动/自动直到退出 → 点退出
    5. 若无单挑则关闭弹窗并重复找攻击城池
    """
    wait_sec = wait_sec if wait_sec is not None else ATTACK_LOOP_WAIT_SEC
    while True:
        targets = find_attackable_cities_on_screen(my_kingdom)
        if not targets:
            print("无可攻击城池，等待下一轮")
            sleep(wait_sec)
            continue
        succeeded = False
        for idx, t in enumerate(targets):
            print(f"\n--- 攻击候选 [{idx+1}/{len(targets)}] #{t['id']} {t.get('name', '')} ---")
            # 每次都从世界地图重新点，避免停留在详情页导致坐标错位
            open_world_map()
            attack_city_from_world_map(t['id'])
            sleep(1.8)

            if not _find_and_click_template_in_region(TPL_CLICK_AFTER_POPUP, TPL_CLICK_REGION):
                print("  未找到点击目标 (648,433,681,455)，尝试下一个城池")
                continue

            if is_city_unreachable_by_ocr():
                print("  检测到“不”，该城池不可前往，尝试下一个城池")
                continue

            # 不再固定等待：改为轮询 OCR 状态区域（识别到“国”或任意单字才进入后续流程）
            if not wait_status_ready(timeout_sec=wait_sec, interval_sec=1.0):
                print("  状态未就绪，尝试下一个城池")
                continue

            touch(BTN_66_177)
            sleep(1.5)
            # 单挑不再找图：改为 OCR 在指定范围内识别到任意单字则点击中心
            if click_center_if_ocr_has_any_single_char(SINGLE_DUEL_OCR_REGION):
                print("  已点击单挑入口")
                _run_after_dan_tiao()
                print("  本流程完成")
                succeeded = True
                break

            print("  未找到单挑，关闭弹窗后尝试下一个城池")
            touch(BTN_66_177)
            sleep(1)

        # 成功完成一次单挑流程后不退出脚本，继续轮询找城池任务
        if succeeded:
            sleep(1)
            continue

        print("本轮所有城池均不可前往/未就绪/未匹配成功，重新查找其它城池继续")


# ==================== 执行入口 ====================

print("start...")

# ---------- 世界地图攻击流程 ----------
# 打开世界地图，识别可攻击城池（蓝=魏, 绿=吴, 红=蜀，仅交界且可达）
# targets = find_attackable_cities_on_screen(MY_KINGDOM)
# 攻击第 1 个可攻击城池：
# attack_flow(MY_KINGDOM, target_index=1)

# ---------- OCR 采集城池名称 ----------
# 采集所有未命名城池（从头开始）
# collect_city_names()

# 从指定ID断点续传
# get_border_targets("wei")
# ocr_changsha()

# 采集单个城池（调试用）


# ---------- 循环攻击流程 ----------
# 查找可攻击 → 点击目标 → 范围内点击模板 → 等30秒 → 点66,177 → 检测单挑，有则点击并完成，无则重复
attack_loop(MY_KINGDOM)

# 仅查看可攻击列表（不攻击）：
# targets = find_attackable_cities_on_screen(MY_KINGDOM)

# ---------- 其他功能 ----------
# show_city_info(50)
# attack_city(40)

