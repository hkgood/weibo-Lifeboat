#!/bin/bash
# 微博逃生舱启动脚本
# Weibo Lifeboat Launcher

echo "🚀 微博逃生舱 · Weibo Lifeboat"
echo "================================"
echo ""

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "⚠️  虚拟环境不存在，正在创建..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "❌ 虚拟环境创建失败"
        exit 1
    fi
    echo "✓ 虚拟环境创建成功"
fi

# 激活虚拟环境
echo "📦 激活虚拟环境..."
source .venv/bin/activate

# 检查依赖
if ! python3 -c "import PySide6" 2>/dev/null; then
    echo "⚠️  缺少依赖包，正在安装..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ 依赖安装失败"
        exit 1
    fi
    echo "✓ 依赖安装完成"
fi

# 启动 GUI
echo "🎨 启动图形界面..."
echo ""
python3 run_gui.py

# 退出时提示
echo ""
echo "👋 感谢使用微博逃生舱！"

