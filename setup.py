#!/usr/bin/env python3
"""
微博逃生舱 / Weibo Lifeboat - 微博备份工具

Setup script for packaging and distribution.
"""

from pathlib import Path
from setuptools import setup, find_packages

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip()
        for line in requirements_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="weibo-lifeboat",
    version="1.0.0",
    author="weibo-lifeboat contributors",
    author_email="",
    description="微博逃生舱 - 优雅的微博个人数据备份工具 / Weibo Lifeboat - An elegant Weibo backup tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/weibo-backup",
    project_urls={
        "Bug Tracker": "https://github.com/yourusername/weibo-backup/issues",
        "Documentation": "https://github.com/yourusername/weibo-backup#readme",
        "Source Code": "https://github.com/yourusername/weibo-backup",
    },
    packages=find_packages(exclude=["tests", "tests.*", "docs", "docs.*"]),
    package_data={
        "": ["*.json", "*.md"],
    },
    include_package_data=True,
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pytest>=7.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "weibo-lifeboat=src.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: System :: Archiving :: Backup",
        "Topic :: Utilities",
    ],
    keywords="weibo backup archiving data-backup social-media lifeboat",
    license="MIT",
)

