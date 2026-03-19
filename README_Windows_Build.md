# Windows 打包与运行指南 (Airtest + 远程 OCR)

因为直接在手机上运行 PaddleOCR / RapidOCR 会面临严重的库依赖冲突和超大体积的问题，我们采用了 **手机截图 + PC 识别** 的架构。

## 架构说明
1. **PC 端 (Windows)**: 运行一个轻量级的 Web 服务器 (`flask_ocr_server.py`)，负责接收手机发来的截图，调用 `PaddleOCR` / `RapidOCR` 识别并返回结果。
2. **手机端 (Android)**: 打包出的 APK，它提供了一个简单的 UI (`main.py`)，启动后运行你的核心脚本 `gongcheng.py`。
3. **网络通讯**: 手机端的 `ocr_manager.py` 已经被改写为客户端，会将需要识别的区域发送给 PC 端的服务。

---

## 1. 运行前准备

### 第一步：在 PC 端启动 OCR 服务
请在你的 Windows 电脑上打开终端，运行：
```bash
pip install flask rapidocr-onnxruntime opencv-python numpy
python e:\jiaoben1\gongcheng\flask_ocr_server.py
```
> **注意**: 服务默认运行在 `0.0.0.0:5000`。请查看你电脑的局域网 IP (例如 `192.168.1.100`)，并确保手机和电脑在同一个局域网下（或者连接同一个 WiFi）。

### 第二步：手机开启“无线调试”
因为 Airtest 需要 ADB 支持，你需要在手机的“开发者选项”中打开 **无线调试 (Wireless Debugging)**。
1. 在手机上打开无线调试，找到你的手机 IP 和端口（例如 `192.168.1.101:5555`）。
2. （可选）如果你就在电脑前，用数据线连着手机也是可以的，设备 URI 就写 `android:///`。

---

## 2. 如何在 Windows 下打包 APK

由于 `Buildozer` 工具不支持在纯 Windows (CMD/PowerShell) 下直接打包，我为你配置了两种极其简单的方法：

### 方案 A：使用 GitHub Actions（推荐，全自动免配置）
我已经帮你写好了 `.github/workflows/build-apk.yml`。
1. 在 GitHub 上新建一个代码仓库。
2. 将 `e:\jiaoben1\gongcheng` 目录下的所有文件上传（Push）到该仓库。
3. GitHub Actions 会自动触发并在云端 Linux 环境下为你打包。
4. 大约 10 分钟后，在仓库的 **Actions** 标签页中，你可以直接下载生成的 `.apk` 文件。

### 方案 B：使用 Windows 的 WSL (Ubuntu 子系统)
如果你懂一点 WSL，可以在 WSL 终端里执行：
```bash
sudo apt update
sudo apt install -y git zip unzip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev python3-pip
pip3 install buildozer
cd /mnt/e/jiaoben1/gongcheng
buildozer android debug
```
打包成功后，APK 将出现在 `bin/` 文件夹中。

---

## 3. 在手机上运行

1. 将打包好的 APK 安装到手机上并打开。
2. 在 App 界面的 `OCR Server URL` 中，填入你 PC 的局域网 IP 地址（例如 `http://192.168.1.100:5000/ocr`）。
3. 在 `Airtest Device` 中填入你的设备 URI（如果你开启了无线调试，填入类似 `android://127.0.0.1:5555` 或者你手机自身的无线调试端口）。
4. 点击 **Start Script** 按钮，App 就会在后台启动 `gongcheng.py`，并将截图请求发往电脑的 OCR 服务。
