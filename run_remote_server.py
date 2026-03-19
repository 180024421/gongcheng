# -*- coding: utf-8 -*-
"""
远程控制服务入口 - 必须从项目根目录运行，确保使用本地的 gongcheng.py 和 city_data.py。
用法: cd D:\project\gongcheng && python run_remote_server.py
"""
import os
import sys

# 项目根目录 = 本文件所在目录（包含 gongcheng.py、city_data.py）
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# remote 模块所在目录
REMOTE_DIR = os.path.join(PROJECT_ROOT, "apk_control", "remote")
if REMOTE_DIR not in sys.path:
    sys.path.insert(0, REMOTE_DIR)

# 验证必需文件存在
_gongcheng_py = os.path.join(PROJECT_ROOT, "gongcheng.py")
_city_data_py = os.path.join(PROJECT_ROOT, "city_data.py")
if not os.path.isfile(_gongcheng_py):
    print(f"错误: 找不到 gongcheng.py，期望路径: {_gongcheng_py}")
    sys.exit(1)
if not os.path.isfile(_city_data_py):
    print(f"错误: 找不到 city_data.py，期望路径: {_city_data_py}")
    sys.exit(1)
print(f"[远程] 使用项目根目录: {PROJECT_ROOT}")
print(f"[远程] gongcheng.py: {_gongcheng_py}")
print(f"[远程] city_data.py: {_city_data_py}")

# 导入并启动 remote_server（来自 apk_control/remote/）
import remote_server
remote_server.main()
