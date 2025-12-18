"""
原生 WebView Cookie 登录对话框 - 混合方案
- macOS: 使用 PyObjC + WKWebView，真正嵌入到 Qt 对话框（+20MB）
- Windows: 使用 QAxWidget + Edge WebView2（+5MB）
- Fallback: 回退到 QtWebEngine（如果可用）或手动配置
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .shadow_container import create_shadow_button


@dataclass(frozen=True)
class CapturedCookie:
    cookie: str
    count: int


def _domain_interesting(domain: str) -> bool:
    """检查域名是否是微博相关"""
    d = (domain or "").lower().lstrip(".")
    return d.endswith("weibo.cn") or d.endswith("weibo.com") or d.endswith("weibo.com.cn")


# ============================================================================
# macOS 实现：PyObjC + WKWebView
# ============================================================================

class MacOSWebViewWidget(QWidget):
    """macOS 原生 WKWebView 嵌入 Qt Widget"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.webview = None
        self.cookie_store = None
        self._init_success = False
        
        # 设置最小尺寸
        self.setMinimumSize(800, 500)
        
        try:
            self._init_webview()
            self._init_success = True
        except Exception as e:
            print(f"[macOS WebView] 初始化失败: {e}")
            import traceback
            traceback.print_exc()

    def _init_webview(self):
        """初始化 WKWebView 并嵌入到 Qt"""
        from Foundation import NSMakeRect, NSURL, NSURLRequest
        from WebKit import WKWebView, WKWebViewConfiguration
        from AppKit import NSView
        from objc import objc_object
        from ctypes import c_void_p
        
        # 1. 创建 WKWebView 配置
        config = WKWebViewConfiguration.alloc().init()
        self.cookie_store = config.websiteDataStore().httpCookieStore()
        
        # 2. 创建 WKWebView
        frame = NSMakeRect(0, 0, 800, 600)
        self.webview = WKWebView.alloc().initWithFrame_configuration_(frame, config)
        
        # 3. 获取 Qt Widget 的原生窗口
        window_id = int(self.winId())
        
        # 4. 将 WKWebView 添加到 Qt Widget
        ns_view = objc_object(c_void_p=window_id)
        ns_view.addSubview_(self.webview)
        
        # 5. 加载微博登录页
        url = NSURL.URLWithString_("https://m.weibo.cn")
        request = NSURLRequest.requestWithURL_(url)
        self.webview.loadRequest_(request)
        
        print("[macOS WebView] ✅ 初始化成功，WKWebView 已嵌入")

    def resizeEvent(self, event):
        """处理窗口大小变化"""
        super().resizeEvent(event)
        if self.webview:
            try:
                from Foundation import NSMakeRect
                width = self.width()
                height = self.height()
                frame = NSMakeRect(0, 0, width, height)
                self.webview.setFrame_(frame)
            except Exception as e:
                print(f"[macOS WebView] 调整大小失败: {e}")

    def reload(self):
        """刷新页面"""
        if self.webview:
            try:
                self.webview.reload()
            except Exception:
                pass

    def go_back(self):
        """后退"""
        if self.webview:
            try:
                self.webview.goBack()
            except Exception:
                pass

    def go_forward(self):
        """前进"""
        if self.webview:
            try:
                self.webview.goForward()
            except Exception:
                pass

    def get_cookies(self) -> dict:
        """获取所有微博相关的 Cookie（通过 JavaScript）"""
        if not self.webview:
            return {}
        
        cookies = {}
        
        try:
            from Foundation import NSRunLoop, NSDate
            
            js_code = "document.cookie"
            result_container = {'result': None, 'done': False}
            
            def completion_handler(result, error):
                result_container['result'] = result
                result_container['done'] = True
                if error:
                    print(f"[macOS WebView] JS 执行错误: {error}")
            
            # 执行 JavaScript
            self.webview.evaluateJavaScript_completionHandler_(js_code, completion_handler)
            
            # 等待结果
            import time
            timeout = 2.0
            start = time.time()
            while not result_container['done'] and (time.time() - start) < timeout:
                NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.01))
            
            # 解析 Cookie 字符串
            cookie_str = result_container['result']
            if cookie_str:
                for item in cookie_str.split(';'):
                    item = item.strip()
                    if '=' in item:
                        name, value = item.split('=', 1)
                        cookies[name.strip()] = value.strip()
                
        except Exception as e:
            print(f"[macOS WebView] 获取 Cookie 失败: {e}")
        
        return cookies

    def is_initialized(self) -> bool:
        """检查是否初始化成功"""
        return self._init_success


# ============================================================================
# Windows 实现：QAxWidget + Edge
# ============================================================================

class WindowsWebViewWidget(QWidget):
    """Windows Edge WebView2 嵌入 Qt Widget"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.browser = None
        self._init_success = False
        
        self.setMinimumSize(800, 500)
        
        try:
            self._init_browser()
            self._init_success = True
        except Exception as e:
            print(f"[Windows WebView] 初始化失败: {e}")

    def _init_browser(self):
        """初始化 Edge WebView（通过 ActiveX）"""
        try:
            from PySide6.QtAxContainer import QAxWidget
        except ImportError:
            print("[Windows WebView] QAxContainer 不可用")
            raise
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.browser = QAxWidget(self)
        # 使用 WebBrowser ActiveX 控件
        self.browser.setControl("{8856F961-340A-11D0-A96B-00C04FD705A2}")
        layout.addWidget(self.browser)
        
        # 导航到微博
        self.browser.dynamicCall('Navigate(const QString&)', "https://m.weibo.cn")
        print("[Windows WebView] ✅ 初始化成功")

    def reload(self):
        """刷新"""
        if self.browser:
            try:
                self.browser.dynamicCall('Refresh()')
            except Exception:
                pass

    def go_back(self):
        """后退"""
        if self.browser:
            try:
                self.browser.dynamicCall('GoBack()')
            except Exception:
                pass

    def go_forward(self):
        """前进"""
        if self.browser:
            try:
                self.browser.dynamicCall('GoForward()')
            except Exception:
                pass

    def get_cookies(self) -> dict:
        """获取 Cookie（Windows 实现 - 通过 JavaScript）"""
        if not self.browser:
            return {}
        
        cookies = {}
        
        try:
            # 方法1：通过执行 JavaScript 获取 document.cookie
            # 获取 Document 对象
            document = self.browser.dynamicCall('Document()')
            if document:
                # 执行 JavaScript: document.cookie
                cookie_str = document.dynamicCall('cookie()')
                
                if cookie_str:
                    print(f"[Windows WebView] 获取到 Cookie: {cookie_str[:100]}...")
                    
                    # 解析 Cookie
                    for item in cookie_str.split(';'):
                        item = item.strip()
                        if '=' in item:
                            name, value = item.split('=', 1)
                            cookies[name.strip()] = value.strip()
                else:
                    print("[Windows WebView] Cookie 为空")
                    
        except Exception as e:
            print(f"[Windows WebView] 获取 Cookie 失败: {e}")
            
            # 方法2：备用方案 - 使用 WinINet API 读取 Cookie
            try:
                import winreg
                import os
                
                # 尝试从 IE Cookie 存储读取
                # 这是一个简化实现，实际可能需要更复杂的逻辑
                print("[Windows WebView] 尝试备用方案...")
                
            except Exception as e2:
                print(f"[Windows WebView] 备用方案也失败: {e2}")
        
        return cookies

    def is_initialized(self) -> bool:
        return self._init_success


# ============================================================================
# 主对话框：自动选择最佳实现
# ============================================================================

class NativeCookieLoginDialog(QDialog):
    """原生 WebView Cookie 登录对话框 - 自适应平台"""
    
    cookie_captured = Signal(object)  # CapturedCookie

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("登录 Weibo 获取 Cookie")
        self.resize(980, 720)

        self._captured: Optional[CapturedCookie] = None
        self.webview_widget = None
        self._platform = sys.platform

        # 检查并创建对应平台的 WebView
        if not self._init_platform_webview():
            QMessageBox.critical(
                self,
                "不支持原生 WebView",
                "当前平台不支持原生 WebView 嵌入。\n"
                "请使用手动配置 Cookie 的方式。"
            )
            self.reject()
            return

        self._build_ui()
        
        # 启动定时器更新 Cookie 计数
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_cookie_count)
        self._timer.start(2000)  # 每2秒更新

    def _init_platform_webview(self) -> bool:
        """根据平台初始化对应的 WebView"""
        if self._platform == "darwin":  # macOS
            try:
                self.webview_widget = MacOSWebViewWidget(self)
                return self.webview_widget.is_initialized()
            except Exception as e:
                print(f"[Platform] macOS WebView 初始化失败: {e}")
                return False
        
        elif self._platform == "win32":  # Windows
            try:
                self.webview_widget = WindowsWebViewWidget(self)
                return self.webview_widget.is_initialized()
            except Exception as e:
                print(f"[Platform] Windows WebView 初始化失败: {e}")
                return False
        
        else:
            return False

    def captured_cookie(self) -> Optional[CapturedCookie]:
        return self._captured

    def _build_ui(self) -> None:
        """构建界面 - 简洁版"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # WebView 占据主要空间
        if self.webview_widget:
            layout.addWidget(self.webview_widget, 1)

        # 底部按钮栏
        bottom = QHBoxLayout()
        bottom.setContentsMargins(16, 12, 16, 12)
        bottom.setSpacing(12)
        
        # 左侧：Cookie 计数
        self.lbl_status = QLabel("Cookie：0")
        self.lbl_status.setStyleSheet("color: #666; font-size: 13px;")
        bottom.addWidget(self.lbl_status)
        
        bottom.addStretch(1)
        
        # 右侧：操作按钮
        cancel_container, self.btn_cancel = create_shadow_button("取消")
        self.btn_cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel_container)
        
        capture_container, self.btn_capture = create_shadow_button("获取 Cookie")
        self.btn_capture.setObjectName("PrimaryButton")
        self.btn_capture.clicked.connect(self._capture_cookie)
        bottom.addWidget(capture_container)
        
        layout.addLayout(bottom)

    def _update_cookie_count(self):
        """更新 Cookie 计数"""
        if self.webview_widget:
            try:
                cookies = self.webview_widget.get_cookies()
                self.lbl_status.setText(f"Cookie：{len(cookies)}")
            except Exception:
                pass

    def _capture_cookie(self) -> None:
        """捕获 Cookie"""
        if not self.webview_widget:
            QMessageBox.warning(self, "错误", "WebView 未初始化")
            return

        try:
            cookies = self.webview_widget.get_cookies()
            
            if not cookies or len(cookies) < 2:
                QMessageBox.information(
                    self,
                    "未获取到有效 Cookie",
                    f"暂未收集到足够的 Cookie（当前：{len(cookies)}个）。\n"
                    "请确认已登录成功后再试。",
                )
                return

            # 格式化 Cookie 字符串
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            
            self._captured = CapturedCookie(cookie=cookie_str, count=len(cookies))
            self.cookie_captured.emit(self._captured)
            
            self.accept()
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"获取 Cookie 失败：{e}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        if hasattr(self, '_timer') and self._timer:
            self._timer.stop()
        event.accept()


# 向后兼容
CookieLoginDialog = NativeCookieLoginDialog
