#!/bin/bash
# 快速发布脚本 - 微博逃生舱
# 使用方法: bash release.sh 1.0.0

set -e

VERSION=${1:-"1.0.0"}

echo "=========================================="
echo "  微博逃生舱 发布脚本"
echo "  版本: v${VERSION}"
echo "=========================================="
echo

# 检查是否有未提交的更改
if [[ -n $(git status -s) ]]; then
    echo "❌ 错误：有未提交的更改"
    echo "请先提交所有更改："
    echo "  git add ."
    echo "  git commit -m 'your message'"
    exit 1
fi

# 确认发布
echo "📦 准备发布 v${VERSION}"
echo
echo "将执行以下操作："
echo "  1. 创建 tag: v${VERSION}"
echo "  2. 推送到 GitHub"
echo "  3. 触发 GitHub Actions 自动打包"
echo
read -p "确认继续? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 已取消"
    exit 1
fi

# 创建 tag
echo
echo "[1/3] 创建 tag..."
git tag -a "v${VERSION}" -m "Release version ${VERSION}"

# 推送代码
echo
echo "[2/3] 推送到 GitHub..."
git push origin main

# 推送 tag
echo
echo "[3/3] 推送 tag..."
git push origin "v${VERSION}"

echo
echo "✅ 完成！"
echo
echo "📊 GitHub Actions 正在自动构建..."
echo "   预计需要 5-10 分钟"
echo
echo "🔗 查看进度:"
echo "   https://github.com/$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/actions"
echo
echo "🎉 构建完成后，访问 Releases 页面下载:"
echo "   https://github.com/$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/releases"
echo

