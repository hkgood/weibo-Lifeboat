#!/bin/bash
# 创建 macOS DMG 安装包（优化版）

APP_NAME="WeiboLifeboat"
APP_VERSION="1.0.0"
DMG_NAME="微博逃生舱-${APP_VERSION}-lite"

echo "📀 创建 DMG 安装包..."

# 检查应用是否存在
if [ ! -d "dist/${APP_NAME}.app" ]; then
    echo "❌ 应用不存在，请先运行 ./build_macos.sh"
    exit 1
fi

# 创建临时目录
rm -rf dmg_temp
mkdir dmg_temp

# 复制应用
cp -r "dist/${APP_NAME}.app" dmg_temp/

# 创建应用程序快捷方式
ln -s /Applications dmg_temp/Applications

# 创建 DMG
hdiutil create -volname "${APP_NAME}" \
    -srcfolder dmg_temp \
    -ov -format UDZO \
    "dist/${DMG_NAME}.dmg"

# 清理
rm -rf dmg_temp

if [ $? -eq 0 ]; then
    echo "✅ DMG 创建成功！"
    echo ""
    echo "📦 文件: dist/${DMG_NAME}.dmg"
    echo "💾 大小: $(du -sh "dist/${DMG_NAME}.dmg" | cut -f1)"
    echo ""
    echo "🎉 打包完成！文件体积已优化（不包含 WebEngine）"
else
    echo "❌ DMG 创建失败"
    exit 1
fi

