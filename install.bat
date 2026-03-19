@echo off
chcp 65001 >nul
echo ========================================
echo   工程城池项目 - 依赖安装
echo ========================================
echo.

cd /d "%~dp0"

REM 若之前配置过代理导致安装失败，可先取消代理再安装：
REM set HTTP_PROXY=
REM set HTTPS_PROXY=
REM pip config unset global.proxy

echo 使用 Python: 
python --version
echo.
echo 正在安装 requirements.txt ...
echo.

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [失败] 若提示代理/网络错误，请：
    echo   1. 检查网络或关闭 VPN/代理
    echo   2. 在 CMD 中执行：set HTTP_PROXY= 与 set HTTPS_PROXY= 后重试
    echo   3. 或执行：pip config unset global.proxy 后重试
    pause
    exit /b 1
)

echo.
echo [完成] 依赖已安装。
pause
