# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# 排除不需要的大型模块
excludes = [
    'PySide6.QtWebEngine',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebChannel',
    'PySide6.Qt3D',
    'PySide6.QtCharts',
    'PySide6.QtDataVisualization',
    'PySide6.QtQuick',
    'PySide6.QtQuick3D',
    'PySide6.QtQml',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtOpenGL',
    'PySide6.QtOpenGLWidgets',
    'PySide6.QtPositioning',
    'PySide6.QtSql',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
    'PySide6.QtTest',
    'PySide6.QtBluetooth',
    'PySide6.QtNfc',
    'matplotlib',
    'numpy',
    'scipy',
    'pandas',
    'PIL',
    'tkinter',
]

a = Analysis(
    ['run_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('config.example.json', '.'),
    ],
    hiddenimports=[
        'src',
        'src.gui',
        'src.gui.app',
        'src.gui.main_window',
        'src.gui.style',
        'src.gui.config_store',
        'src.gui.cookie_login',
        'src.gui.cookie_login_native',
        'src.gui.pipeline_process',
        'src.gui.shadow_button',
        'src.gui.shadow_container',
        'src.gui.sidebar_delegate',
        'src.gui.title_bar',
        'src.database',
        'src.weibo_fetcher',
        'src.media_downloader',
        'src.html_generator',
        'src.main',
        'src.pipeline',
        'src.pipeline.runner',
        'src.pipeline.weibo_cn_parser',
        'src.pipeline.http_utils',
        'src.pipeline.events',
        # macOS 原生 WebView
        'Foundation',
        'WebKit',
        'AppKit',
        'objc',
        # Windows 原生 WebView
        'PySide6.QtAxContainer',
        'win32com',
        'winreg',
        # pywebview
        'webview',
        'bottle',
        'proxy_tools',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WeiboLifeboat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app_icon.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WeiboLifeboat',
)

# macOS 应用包
app = BUNDLE(
    coll,
    name='WeiboLifeboat.app',
    icon='assets/app_icon.png',
    bundle_identifier='com.weibolifeboat.app',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'CFBundleName': 'Weibo Lifeboat',
        'CFBundleDisplayName': '微博逃生舱',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'LSMinimumSystemVersion': '10.13.0',
    },
)

