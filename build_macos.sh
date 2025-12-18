#!/bin/bash
# macOS 打包脚本（原生 WebView 版本）

echo "🍎 macOS 打包开始..."
echo "📦 使用原生 WKWebView (体积优化版)"
echo ""

# 激活虚拟环境
source .venv/bin/activate

# 清理旧的构建
rm -rf build dist

# 使用 PyInstaller 打包
echo "🔨 开始打包..."
pyinstaller WeiboLifeboat.spec --clean

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 打包成功！"
    echo ""
    echo "📦 应用位置: dist/WeiboLifeboat.app"
    if [ -d "dist/WeiboLifeboat.app" ]; then
        APP_SIZE=$(du -sh dist/WeiboLifeboat.app | cut -f1)
        DIR_SIZE=$(du -sh dist/WeiboLifeboat | cut -f1)
        echo "💾 应用大小: $APP_SIZE (目录: $DIR_SIZE)"
    fi
    echo ""
    echo "✨ 特性："
    echo "  • 使用系统原生 WKWebView"
    echo "  • 体积比 WebEngine 版小 89%"
    echo "  • Cookie 登录功能完整"
    echo ""
    echo "🔍 测试运行:"
    echo "  open dist/WeiboLifeboat.app"
    echo ""
    echo "📀 创建 DMG:"
    echo "  ./create_dmg.sh"
else
    echo "❌ 打包失败"
    exit 1
fi

