@echo off
chcp 65001 >nul
echo.
echo ================================================
echo   微博逃生舱 - Windows 打包脚本
echo   Weibo Lifeboat - Windows Build Script
echo ================================================
echo.

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误：未找到 Python
    echo    请先安装 Python 3.9+ 并添加到 PATH
    pause
    exit /b 1
)

echo [1/4] 激活虚拟环境...
if not exist .venv (
    echo ⚠️  虚拟环境不存在，正在创建...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo.
echo [2/4] 安装/更新依赖...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [3/4] 开始打包（使用原生 Edge WebView）...
echo      - 不包含 QtWebEngine（体积优化）
echo      - 使用系统 Edge WebView2 控件
pyinstaller WeiboLifeboat.spec --clean --noconfirm

if %errorlevel% neq 0 (
    echo ❌ 打包失败
    pause
    exit /b 1
)

echo.
echo [4/4] 创建安装程序（可选）...
echo.
echo 💡 提示：你可以使用以下工具创建安装程序：
echo    - Inno Setup: https://jrsoftware.org/isinfo.php
echo    - NSIS: https://nsis.sourceforge.io/
echo    - 或者直接分发 dist\WeiboLifeboat 目录（压缩为 .zip）
echo.

echo ✅ 打包完成！
echo.
echo 📦 输出目录: dist\WeiboLifeboat\
echo 📝 主程序: dist\WeiboLifeboat\WeiboLifeboat.exe
echo.
echo 💾 估计大小: ~200MB
echo.
echo 🎉 现在可以将 dist\WeiboLifeboat 目录打包为 ZIP 分发，
echo    或使用安装程序创建工具制作安装包。
echo.
pause
