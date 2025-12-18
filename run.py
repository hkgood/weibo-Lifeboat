#!/usr/bin/env python3
"""
快速启动脚本
"""
import subprocess
import sys
from pathlib import Path

def main():
    """运行微博备份"""
    # 检查依赖
    try:
        import httpx
        import aiofiles
        import bs4
        from loguru import logger
    except ImportError:
        print("缺少依赖，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("依赖安装完成\n")
    
    # 检查配置文件
    if not Path("config.json").exists():
        print("配置文件不存在！")
        print("请复制 config.example.json 为 config.json 并填写配置")
        sys.exit(1)
    
    # 运行增量 pipeline（可按阶段执行、不会重复抓取已完成的项）
    subprocess.run([sys.executable, "-m", "src.pipeline.runner", *sys.argv[1:]])

if __name__ == "__main__":
    main()

