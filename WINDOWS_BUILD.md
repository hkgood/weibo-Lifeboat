# Windows 打包指南

## 📋 前置要求

1. **Python 3.9+** (推荐 3.9 或 3.10)
2. **Git**（用于克隆代码）
3. **Windows 10/11**（需要 Edge WebView2 运行时，系统通常已预装）

## 🚀 快速开始

### 方法一：使用自动化脚本（推荐）

```cmd
# 1. 克隆或下载项目到 Windows 机器

# 2. 在项目根目录打开命令提示符

# 3. 运行打包脚本
build_windows.bat
```

脚本会自动：
- 创建虚拟环境
- 安装依赖
- 运行 PyInstaller
- 生成可执行文件

### 方法二：手动打包

```cmd
# 1. 创建虚拟环境
python -m venv .venv

# 2. 激活虚拟环境
.venv\Scripts\activate.bat

# 3. 安装依赖
pip install -r requirements.txt
pip install pyinstaller

# 4. 打包
pyinstaller WeiboLifeboat.spec --clean --noconfirm
```

## 📦 输出

打包完成后，会生成：

```
dist/
└── WeiboLifeboat/
    ├── WeiboLifeboat.exe    # 主程序
    ├── assets/              # 资源文件（图标等）
    ├── config.example.json  # 配置模板
    └── ... (其他依赖库)
```

**文件大小**：约 200MB

## 🎯 分发方式

### 选项 1：ZIP 压缩包（最简单）

```cmd
# 在 dist 目录中，右键 WeiboLifeboat 文件夹
# 选择"发送到" -> "压缩(zipped)文件夹"
```

用户解压后直接运行 `WeiboLifeboat.exe` 即可。

### 选项 2：安装程序（推荐）

使用 **Inno Setup** 创建专业的安装程序：

1. 下载 Inno Setup: https://jrsoftware.org/isdl.php
2. 创建 `installer.iss` 脚本：

```iss
[Setup]
AppName=微博逃生舱
AppVersion=1.0.0
DefaultDirName={pf}\WeiboLifeboat
DefaultGroupName=微博逃生舱
OutputDir=installer_output
OutputBaseFilename=WeiboLifeboat-Setup-1.0.0
Compression=lzma2
SolidCompression=yes
SetupIconFile=assets\app_icon.ico

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"

[Files]
Source: "dist\WeiboLifeboat\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\微博逃生舱"; Filename: "{app}\WeiboLifeboat.exe"
Name: "{group}\卸载微博逃生舱"; Filename: "{uninstallexe}"
Name: "{commondesktop}\微博逃生舱"; Filename: "{app}\WeiboLifeboat.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\WeiboLifeboat.exe"; Description: "运行微博逃生舱"; Flags: nowait postinstall skipifsilent
```

3. 编译生成 `WeiboLifeboat-Setup-1.0.0.exe`

## 🔧 技术说明

### 原生 WebView 实现

Windows 版本使用以下技术获取 Cookie：

- **QAxWidget** + IE WebBrowser 控件（内置，无需额外下载）
- 备选方案会自动检测系统 Edge WebView2

### 体积优化

相比使用 QtWebEngine（+800MB），我们的方案：

- ✅ 使用系统原生浏览器控件（~0MB 额外）
- ✅ 排除不需要的 Qt 模块
- ✅ 最终大小：~200MB

## 🐛 调试

如果应用启动失败，查看日志：

```
%USERPROFILE%\AppData\Local\WeiboLifeboat\Logs\app.log
```

常见问题：

1. **缺少 VCRUNTIME140.dll**
   - 安装 [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)

2. **WebView 无法加载**
   - 确保已安装 Edge 浏览器（Windows 10/11 默认已安装）

3. **防火墙拦截**
   - 允许应用访问网络

## 📝 注意事项

- Windows 版本使用 IE WebBrowser 控件或 Edge WebView2
- 首次运行可能需要管理员权限
- 建议在打包前测试开发版本：`python run_gui.py`

## 🎉 完成

打包成功后，你可以：

1. 在 GitHub Releases 发布
2. 分享给其他用户
3. 创建离线安装包

祝使用愉快！🚀

