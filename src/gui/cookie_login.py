from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .shadow_container import create_shadow_button

try:
    from PySide6.QtWebEngineCore import QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView

    _WEBENGINE_OK = True
except Exception:
    QWebEngineProfile = object  # type: ignore
    QWebEngineView = object  # type: ignore
    _WEBENGINE_OK = False


@dataclass(frozen=True)
class CapturedCookie:
    cookie: str
    count: int


def _cookie_key(c: QNetworkCookie) -> Tuple[str, str, str]:
    # (domain, path, name)
    try:
        domain = (c.domain() or "").strip()
    except Exception:
        domain = ""
    try:
        path = (c.path() or "").strip()
    except Exception:
        path = ""
    try:
        name = bytes(c.name()).decode("utf-8", errors="ignore")
    except Exception:
        name = ""
    return (domain, path, name)


def _cookie_str(c: QNetworkCookie) -> str:
    try:
        name = bytes(c.name()).decode("utf-8", errors="ignore")
        val = bytes(c.value()).decode("utf-8", errors="ignore")
        if not name:
            return ""
        return f"{name}={val}"
    except Exception:
        return ""


def _domain_interesting(domain: str) -> bool:
    d = (domain or "").lower().lstrip(".")
    return d.endswith("weibo.cn") or d.endswith("weibo.com") or d.endswith("weibo.com.cn")


class CookieLoginDialog(QDialog):
    cookie_captured = Signal(object)  # CapturedCookie

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("登录 Weibo 获取 Cookie")
        self.resize(980, 720)

        if not _WEBENGINE_OK:
            QMessageBox.critical(self, "缺少 WebEngine", "当前环境未启用 QtWebEngine，无法使用内置登录。")
            self.reject()
            return

        self._cookies: Dict[Tuple[str, str, str], QNetworkCookie] = {}
        self._captured: Optional[CapturedCookie] = None

        # Dedicated profile to isolate and persist session across opens (convenient).
        self.profile = QWebEngineProfile("weibo-backup", self)  # type: ignore[call-arg]
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)  # type: ignore[attr-defined]
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)  # type: ignore[attr-defined]

        store = self.profile.cookieStore()  # type: ignore[attr-defined]
        store.cookieAdded.connect(self._on_cookie_added)  # type: ignore[attr-defined]

        self.view = QWebEngineView(self.profile, self)  # type: ignore[call-arg]
        self.view.setUrl(QUrl("https://m.weibo.cn/"))

        self._build_ui()

        # Warm up cookie load for better capture reliability.
        QTimer.singleShot(150, self._load_all_cookies)  # type: ignore[arg-type]

    def captured_cookie(self) -> Optional[CapturedCookie]:
        return self._captured

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        top = QHBoxLayout()
        title = QLabel("请在下方页面登录 `m.weibo.cn`，然后点击“获取 Cookie”")
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setWordWrap(True)
        top.addWidget(title, 1)

        self.lbl_status = QLabel("Cookie：0")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.lbl_status)
        layout.addLayout(top)

        tb = QToolBar()
        tb.setIconSize(tb.iconSize())

        btn_back = tb.addAction("后退")
        btn_back.triggered.connect(self.view.back)  # type: ignore[attr-defined]
        btn_forward = tb.addAction("前进")
        btn_forward.triggered.connect(self.view.forward)  # type: ignore[attr-defined]
        btn_reload = tb.addAction("刷新")
        btn_reload.triggered.connect(self.view.reload)  # type: ignore[attr-defined]
        layout.addWidget(tb)

        layout.addWidget(self.view, 1)

        bottom = QHBoxLayout()
        capture_container, self.btn_capture = create_shadow_button("获取 Cookie")
        self.btn_capture.setObjectName("PrimaryButton")
        self.btn_capture.clicked.connect(self._capture_cookie)  # type: ignore[attr-defined]

        cancel_container, self.btn_cancel = create_shadow_button("取消")
        self.btn_cancel.clicked.connect(self.reject)  # type: ignore[attr-defined]

        bottom.addStretch(1)
        bottom.addWidget(cancel_container)
        bottom.addWidget(capture_container)
        layout.addLayout(bottom)

    def _on_cookie_added(self, c: QNetworkCookie) -> None:
        try:
            domain = (c.domain() or "").strip()
        except Exception:
            domain = ""
        if domain and not _domain_interesting(domain):
            return
        key = _cookie_key(c)
        self._cookies[key] = QNetworkCookie(c)
        self.lbl_status.setText(f"Cookie：{len(self._cookies)}")

    def _load_all_cookies(self) -> None:
        try:
            self.profile.cookieStore().loadAllCookies()  # type: ignore[attr-defined]
        except Exception:
            return

    def _capture_cookie(self) -> None:
        # Load everything first, then snapshot shortly after.
        self._load_all_cookies()
        QTimer.singleShot(350, self._finalize_capture)  # type: ignore[arg-type]

    def _finalize_capture(self) -> None:
        items = list(self._cookies.values())
        # Prefer weibo.cn cookies if available.
        preferred = []
        fallback = []
        for c in items:
            try:
                d = (c.domain() or "").lower().lstrip(".")
            except Exception:
                d = ""
            if d.endswith("weibo.cn"):
                preferred.append(c)
            else:
                fallback.append(c)
        chosen = preferred if preferred else fallback

        parts = []
        seen_names = set()
        # Deduplicate by cookie name, keep the last-seen (often newest).
        for c in chosen:
            s = _cookie_str(c)
            if not s:
                continue
            name = s.split("=", 1)[0]
            if name in seen_names:
                continue
            seen_names.add(name)
            parts.append(s)

        cookie = "; ".join(parts)
        if not cookie or len(parts) < 2:
            QMessageBox.information(
                self,
                "未获取到有效 Cookie",
                "暂未收集到足够的 Cookie。请确认已登录成功后再试。",
            )
            return

        self._captured = CapturedCookie(cookie=cookie, count=len(parts))
        self.cookie_captured.emit(self._captured)
        self.accept()


