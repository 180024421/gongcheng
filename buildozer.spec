[app]
title = GongCheng Auto
package.name = gongcheng
package.domain = org.gongcheng
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt,bat
version = 0.1

# 不包含复杂的 paddleocr/rapidocr, 仅包含客户端所需的轻量库
requirements = python3,kivy,pillow,numpy,opencv,requests,airtest

orientation = landscape
android.archs = arm64-v8a
fullscreen = 1
android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.wakelock = True
android.enable_androidx = True

[buildozer]
log_level = 2
warn_on_root = 1
