from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, QUrl, QThread, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QCheckBox,
    QPlainTextEdit,
    QProgressBar,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QStackedWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .config_store import (
    AppPrefs,
    ensure_config_shape,
    get_nested,
    load_config,
    load_prefs,
    save_config,
    save_prefs,
    safe_float,
    safe_int,
    set_nested,
)
from .pipeline_process import PipelineLaunchSpec, PipelineProcess
from .sidebar_delegate import SidebarItemDelegate
from .shadow_container import create_shadow_button


class CustomMessageDialog(QDialog):
    """自定义消息对话框 - 替代QMessageBox，保持视觉一致性"""
    
    def __init__(
        self, 
        title: str, 
        message: str, 
        buttons: List[tuple[str, str]] = None,  # [(text, objectName), ...]
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._message = message
        self._buttons = buttons or [("确定", "PrimaryButton")]
        self._result = 0
        self._build_ui()
        
    def _build_ui(self) -> None:
        self.setWindowTitle(self._title)
        self.setMinimumWidth(480)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel(self._title)
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # 消息内容
        message = QLabel(self._message)
        message.setWordWrap(True)
        message.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(message)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch(1)
        
        for idx, (text, obj_name) in enumerate(self._buttons):
            container, btn = create_shadow_button(text)
            if obj_name:
                btn.setObjectName(obj_name)
            # 使用 lambda 捕获索引值
            btn.clicked.connect(lambda checked=False, i=idx: self._on_button_clicked(i))  # type: ignore[attr-defined]
            button_layout.addWidget(container)
        
        layout.addLayout(button_layout)
    
    def _on_button_clicked(self, index: int) -> None:
        self._result = index
        self.accept()
    
    def get_result(self) -> int:
        """返回点击的按钮索引"""
        return self._result


@dataclass
class UiState:
    current_phase: str = ""
    list_page: int = 0
    list_new_total: int = 0
    detail_done: int = 0
    detail_total: int = 0
    media_images_done: int = 0
    media_images_total: int = 0
    media_videos_done: int = 0
    media_videos_total: int = 0


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("微博逃生舱 · Weibo Lifeboat")
        self.resize(1100, 720)
        
        # Set window background to match app background (helps macOS title bar color)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#ECECEC"))
        self.setPalette(palette)

        self._prefs: AppPrefs = load_prefs()
        self._config_path: Path = Path(self._prefs.last_config_path).expanduser()
        self._config: Dict[str, Any] = {}
        self._state = UiState()

        self._pipeline = PipelineProcess()
        self._pipeline.started.connect(self._on_pipeline_started)  # type: ignore[attr-defined]
        self._pipeline.finished.connect(self._on_pipeline_finished)  # type: ignore[attr-defined]
        self._pipeline.log_line.connect(self._append_log)  # type: ignore[attr-defined]
        self._pipeline.event.connect(self._on_event)  # type: ignore[attr-defined]

        self._build_ui()
        self._load_config_into_form(best_effort=True)
        self._update_run_buttons()
        
        # Set macOS title bar color after window is created
        self._set_macos_titlebar_color()

    # ---------------------------
    # UI build
    # ---------------------------
    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(220)
        self.sidebar.setSpacing(8)  # Reduced spacing
        self.sidebar.setUniformItemSizes(True)
        # Use custom delegate for top-aligned text and shadow rendering
        self.sidebar.setItemDelegate(SidebarItemDelegate(self.sidebar))

        self.stack = QStackedWidget()
        self.stack.setContentsMargins(0, 0, 0, 0)

        self._page_tasks = self._build_tasks_page()
        self._page_settings = self._build_settings_page()

        self.stack.addWidget(self._page_tasks)
        self.stack.addWidget(self._page_settings)

        # Keep the app simple: Cookie is configured within Settings only.
        for title in ["开始逃生", "逃生设置"]:
            self.sidebar.addItem(QListWidgetItem(title))

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)  # type: ignore[attr-defined]
        self.sidebar.setCurrentRow(0)

        root_layout.addWidget(self.sidebar)

        content = QWidget()
        content.setObjectName("ContentArea")
        content_layout = QVBoxLayout(content)
        # No horizontal margins here - let scrollbar reach the edge
        content_layout.setContentsMargins(0, 16, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.stack, 1)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

        # Menu
        file_menu = self.menuBar().addMenu("文件")
        act_open_cfg = QAction("打开配置…", self)
        act_open_cfg.triggered.connect(self._choose_config_path)  # type: ignore[attr-defined]
        file_menu.addAction(act_open_cfg)

        act_save_cfg = QAction("保存配置", self)
        act_save_cfg.triggered.connect(self._save_config_from_form)  # type: ignore[attr-defined]
        file_menu.addAction(act_save_cfg)

        file_menu.addSeparator()
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(QApplication.quit)  # type: ignore[attr-defined]
        file_menu.addAction(act_quit)

        run_menu = self.menuBar().addMenu("任务")
        self._act_start = QAction("开始", self)
        self._act_start.triggered.connect(self._start_pipeline)  # type: ignore[attr-defined]
        run_menu.addAction(self._act_start)
        self._act_stop = QAction("停止", self)
        self._act_stop.triggered.connect(self._stop_pipeline)  # type: ignore[attr-defined]
        
        # Create empty toolbar to unify title bar on macOS
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setVisible(False)  # Hide but keep for title bar integration
        self.addToolBar(toolbar)
        self.setUnifiedTitleAndToolBarOnMac(True)
        run_menu.addAction(self._act_stop)

    def _page_header(self, title: str, subtitle: str) -> QWidget:
        box = QWidget()
        box.setObjectName("PageHeader")
        layout = QVBoxLayout(box)
        # B: header aligns to the card border start (no extra indent beyond page inset).
        layout.setContentsMargins(0, 0, 0, 0)
        # Spacing between title/subtitle is controlled via QSS margins for pixel-perfect consistency.
        layout.setSpacing(0)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        s = QLabel(subtitle)
        s.setObjectName("PageSubtitle")
        s.setWordWrap(True)
        layout.addWidget(t)
        layout.addWidget(s)
        return box

    def _card(self, title: str, hint: str = "") -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        # Web-like cards (openai.fm-inspired): a bit more whitespace than the macOS-native look.
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)
        # IMPORTANT: Do NOT use QGraphicsEffect (e.g. DropShadow) on macOS native style.
        # It can trigger Qt painting recursion / crashes in libqmacstyle.
        card.setGraphicsEffect(None)

        header = QWidget()
        hl = QVBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(2)
        lt = QLabel(title)
        lt.setObjectName("CardTitle")
        hl.addWidget(lt)
        if hint:
            lh = QLabel(hint)
            lh.setObjectName("CardHint")
            lh.setWordWrap(True)
            hl.addWidget(lh)
        card_layout.addWidget(header)
        return card, card_layout

    def _fix_form_label_width(self, form: QFormLayout, fields: List[QWidget], width: int) -> None:
        # Make left column consistent across cards (avoid misalignment between sections).
        for w in fields:
            lab = form.labelForField(w)
            if lab:
                lab.setFixedWidth(width)
                lab.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def _build_settings_page(self) -> QWidget:
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Header with horizontal padding
        header_container = QWidget()
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(16, 0, 16, 14)
        header_layout.setSpacing(0)
        header_layout.addWidget(self._page_header("逃生设置", "配置逃生账号、逃生节奏与导出路径。或者使用内置浏览器登录来自动获取 Cookie。"))
        outer_layout.addWidget(header_container)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        w = QWidget()
        # IMPORTANT: the scroll content should not paint an opaque default background
        # (otherwise it covers the app's page background).
        w.setObjectName("ScrollBody")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 0, 16, 16)
        layout.setSpacing(14)

        # Config path row (card)
        card_cfg, cl = self._card("配置文件", "GUI 会记住你上次打开的 config.json。")
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.lbl_cfg_path = QLabel("")
        choose_cfg_container, self.btn_choose_cfg = create_shadow_button("选择…")
        self.btn_choose_cfg.clicked.connect(self._choose_config_path)  # type: ignore[attr-defined]
        row.addWidget(QLabel("当前："))
        row.addWidget(self.lbl_cfg_path, 1)
        row.addWidget(choose_cfg_container)
        cl.addLayout(row)
        layout.addWidget(card_cfg)

        # Weibo card
        card_weibo, clw = self._card("微博账号", "手动粘贴 Cookie，或通过内置浏览器登录后自动获取。")
        form_weibo = QFormLayout()
        form_weibo.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_weibo.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form_weibo.setHorizontalSpacing(12)
        form_weibo.setVerticalSpacing(12)

        self.ed_user_id = QLineEdit()
        self.ed_user_agent = QLineEdit()
        self.ed_cookie = QPlainTextEdit()
        self.ed_cookie.setPlaceholderText("Cookie 字符串（将写入 config.json；如需更安全可后续改 Keychain）")
        self.ed_cookie.setMaximumBlockCount(2000)
        self.ed_cookie.setFixedHeight(120)

        self.lbl_cookie_preview = QLabel("当前 Cookie：未设置")
        self.lbl_cookie_preview.setWordWrap(True)
        self.lbl_cookie_preview.setObjectName("CardHint")

        btns = QHBoxLayout()
        btns.setSpacing(10)
        login_cookie_container, self.btn_login_cookie = create_shadow_button("登录并自动获取 Cookie…")
        self.btn_login_cookie.setObjectName("PrimaryButton")
        self.btn_login_cookie.clicked.connect(self._open_cookie_login)  # type: ignore[attr-defined]
        open_profile_container, self.btn_open_profile = create_shadow_button("打开用户主页")
        self.btn_open_profile.clicked.connect(self._open_profile_link)  # type: ignore[attr-defined]
        btns.addWidget(login_cookie_container)
        btns.addWidget(open_profile_container)
        btns.addStretch(1)

        form_weibo.addRow("用户 ID", self.ed_user_id)
        form_weibo.addRow("User-Agent", self.ed_user_agent)
        form_weibo.addRow("Cookie", self.ed_cookie)
        self._fix_form_label_width(form_weibo, [self.ed_user_id, self.ed_user_agent, self.ed_cookie], width=160)
        clw.addLayout(form_weibo)
        clw.addWidget(self.lbl_cookie_preview)
        clw.addLayout(btns)
        layout.addWidget(card_weibo)

        # Crawler card
        card_crawler, clc = self._card("抓取策略（轻量）", "并发/重试策略，注意：并发过多、过频容易触发反爬虫机制，影响逃生")
        form_crawler = QFormLayout()
        form_crawler.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_crawler.setHorizontalSpacing(12)
        form_crawler.setVerticalSpacing(12)

        self.sb_request_delay = QDoubleSpinBox()
        self.sb_request_delay.setRange(0.0, 30.0)
        self.sb_request_delay.setSingleStep(0.2)
        self.sb_request_delay.setSuffix(" 秒")

        self.sb_timeout = QSpinBox()
        self.sb_timeout.setRange(5, 300)
        self.sb_timeout.setSuffix(" 秒")

        form_crawler.addRow("请求间隔", self.sb_request_delay)
        form_crawler.addRow("超时", self.sb_timeout)
        self._fix_form_label_width(form_crawler, [self.sb_request_delay, self.sb_timeout], width=160)
        clc.addLayout(form_crawler)
        layout.addWidget(card_crawler)

        # Storage card
        card_storage, cls = self._card("存储与导出", "可以在 Finder 中直接打开输出目录查看生成的 HTML。")
        form_storage = QFormLayout()
        form_storage.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_storage.setHorizontalSpacing(12)
        form_storage.setVerticalSpacing(12)

        self.ed_db_path = QLineEdit()
        self.ed_images_dir = QLineEdit()
        self.ed_videos_dir = QLineEdit()
        self.ed_output_dir = QLineEdit()

        form_storage.addRow("数据库路径", self.ed_db_path)
        form_storage.addRow("图片目录", self.ed_images_dir)
        form_storage.addRow("视频目录", self.ed_videos_dir)
        form_storage.addRow("输出目录", self.ed_output_dir)
        self._fix_form_label_width(form_storage, [self.ed_db_path, self.ed_images_dir, self.ed_videos_dir, self.ed_output_dir], width=160)
        cls.addLayout(form_storage)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        open_output_container, self.btn_open_output = create_shadow_button("打开输出目录")
        self.btn_open_output.clicked.connect(self._open_output_dir)  # type: ignore[attr-defined]
        save_cfg_container, self.btn_save_cfg = create_shadow_button("保存配置")
        self.btn_save_cfg.clicked.connect(self._save_config_from_form)  # type: ignore[attr-defined]
        btn_row.addWidget(open_output_container)
        btn_row.addStretch(1)
        btn_row.addWidget(save_cfg_container)
        cls.addLayout(btn_row)
        layout.addWidget(card_storage)

        layout.addStretch(1)
        scroll.setWidget(w)

        outer_layout.addWidget(scroll, 1)
        return outer

    def _build_tasks_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 0, 16, 16)
        layout.setSpacing(14)

        header_container = QWidget()
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        header_layout.addWidget(self._page_header("开始逃生", "选择需要逃生的乘客，点击开始按钮进行逃生"))
        layout.addWidget(header_container)

        card_run, clr = self._card("本次运行", "建议全选，以保证所有数据都可以保存到本地。")
        run_row = QHBoxLayout()
        run_row.setSpacing(12)

        self.cb_list = QCheckBox("微博列表（不含全文）")
        self.cb_detail = QCheckBox("微博全文抓取")
        self.cb_media = QCheckBox("图片下载")
        self.cb_html = QCheckBox("生成 HTML")
        for cb in [self.cb_list, self.cb_detail, self.cb_media, self.cb_html]:
            cb.setChecked(True)
        run_row.addWidget(self.cb_list)
        run_row.addWidget(self.cb_detail)
        run_row.addWidget(self.cb_media)
        run_row.addWidget(self.cb_html)
        run_row.addStretch(1)

        # Create shadow buttons (container draws shadow, button is standard QPushButton)
        stop_container, self.btn_stop = create_shadow_button("停止")
        self.btn_stop.clicked.connect(self._stop_pipeline)  # type: ignore[attr-defined]
        self.btn_stop.setEnabled(False)
        
        start_container, self.btn_start = create_shadow_button("开始")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_start.clicked.connect(self._start_pipeline)  # type: ignore[attr-defined]

        run_row.addWidget(stop_container)
        run_row.addWidget(start_container)
        clr.addLayout(run_row)
        layout.addWidget(card_run)

        card_prog, clp = self._card("逃生进度", "")
        self.lbl_phase = QLabel("阶段：-")
        self.lbl_phase.setObjectName("CardHint")
        self.lbl_list = QLabel("列表：-")
        self.lbl_list.setObjectName("CardHint")

        # Progress bars with labels on the left
        detail_row = QHBoxLayout()
        detail_row.setSpacing(8)
        lbl_detail = QLabel("详情")
        lbl_detail.setObjectName("CardHint")
        lbl_detail.setFixedWidth(40)
        self.pb_detail = QProgressBar()
        self.pb_detail.setFormat("%p%")
        self.pb_detail.setRange(0, 100)
        self.pb_detail.setValue(0)
        detail_row.addWidget(lbl_detail)
        detail_row.addWidget(self.pb_detail)

        images_row = QHBoxLayout()
        images_row.setSpacing(8)
        lbl_images = QLabel("图片")
        lbl_images.setObjectName("CardHint")
        lbl_images.setFixedWidth(40)
        self.pb_media_images = QProgressBar()
        self.pb_media_images.setFormat("%p%")
        self.pb_media_images.setRange(0, 100)
        self.pb_media_images.setValue(0)
        images_row.addWidget(lbl_images)
        images_row.addWidget(self.pb_media_images)

        videos_row = QHBoxLayout()
        videos_row.setSpacing(8)
        lbl_videos = QLabel("视频")
        lbl_videos.setObjectName("CardHint")
        lbl_videos.setFixedWidth(40)
        self.pb_media_videos = QProgressBar()
        self.pb_media_videos.setFormat("%p%")
        self.pb_media_videos.setRange(0, 100)
        self.pb_media_videos.setValue(0)
        videos_row.addWidget(lbl_videos)
        videos_row.addWidget(self.pb_media_videos)

        clp.addWidget(self.lbl_phase)
        clp.addWidget(self.lbl_list)
        clp.addLayout(detail_row)
        clp.addLayout(images_row)
        clp.addLayout(videos_row)
        layout.addWidget(card_prog)

        card_log, cll = self._card("逃生日志", "完整日志（用于诊断）。")
        self.log_full = QPlainTextEdit()
        self.log_full.setObjectName("LogView")
        self.log_full.setReadOnly(True)
        self.log_full.setMaximumBlockCount(15000)
        cll.addWidget(self.log_full)

        btns = QHBoxLayout()
        btns.addStretch(1)
        clear_container, btn_clear = create_shadow_button("清空")
        btn_clear.clicked.connect(lambda: self.log_full.setPlainText(""))  # type: ignore[attr-defined]
        btns.addWidget(clear_container)
        cll.addLayout(btns)

        layout.addWidget(card_log, 1)

        return w

    # ---------------------------
    # Config load/save
    # ---------------------------
    def _choose_config_path(self) -> None:
        start_dir = str(self._config_path.parent if self._config_path else Path.cwd())
        path, _ = QFileDialog.getOpenFileName(self, "选择 config.json", start_dir, "JSON (*.json)")
        if not path:
            return
        self._config_path = Path(path)
        self._prefs.last_config_path = str(self._config_path)
        save_prefs(self._prefs)
        self._load_config_into_form(best_effort=False)

    def _load_config_into_form(self, *, best_effort: bool) -> None:
        self.lbl_cfg_path.setText(str(self._config_path))
        try:
            self._config = ensure_config_shape(load_config(self._config_path))
        except Exception as e:
            self._config = ensure_config_shape({})
            if not best_effort:
                dialog = CustomMessageDialog("无法加载配置", f"读取失败：{e}", [("确定", "PrimaryButton")], self)
                dialog.exec()

        # Populate form controls
        self.ed_user_id.setText(str(get_nested(self._config, ["weibo", "user_id"], "")))
        self.ed_user_agent.setText(str(get_nested(self._config, ["weibo", "user_agent"], "")))
        self.ed_cookie.setPlainText(str(get_nested(self._config, ["weibo", "cookie"], "")))

        self.sb_request_delay.setValue(safe_float(get_nested(self._config, ["crawler", "request_delay"], 1.0), 1.0))
        self.sb_timeout.setValue(safe_int(get_nested(self._config, ["crawler", "timeout"], 30), 30))

        self.ed_db_path.setText(str(get_nested(self._config, ["storage", "database_path"], "data/weibo.db")))
        self.ed_images_dir.setText(str(get_nested(self._config, ["storage", "images_dir"], "data/images")))
        self.ed_videos_dir.setText(str(get_nested(self._config, ["storage", "videos_dir"], "data/videos")))
        self.ed_output_dir.setText(str(get_nested(self._config, ["storage", "output_dir"], "data/output")))
        self._refresh_cookie_preview()

    def _save_config_from_form(self) -> None:
        if not self._config_path:
            dialog = CustomMessageDialog("缺少配置", "请先选择 config.json", [("确定", "PrimaryButton")], self)
            dialog.exec()
            return

        cfg = ensure_config_shape(dict(self._config or {}))
        set_nested(cfg, ["weibo", "user_id"], self.ed_user_id.text().strip())
        set_nested(cfg, ["weibo", "user_agent"], self.ed_user_agent.text().strip())
        set_nested(cfg, ["weibo", "cookie"], self.ed_cookie.toPlainText().strip())

        set_nested(cfg, ["crawler", "request_delay"], float(self.sb_request_delay.value()))
        set_nested(cfg, ["crawler", "timeout"], int(self.sb_timeout.value()))

        set_nested(cfg, ["storage", "database_path"], self.ed_db_path.text().strip())
        set_nested(cfg, ["storage", "images_dir"], self.ed_images_dir.text().strip())
        set_nested(cfg, ["storage", "videos_dir"], self.ed_videos_dir.text().strip())
        set_nested(cfg, ["storage", "output_dir"], self.ed_output_dir.text().strip())

        try:
            save_config(self._config_path, cfg)
            self._config = cfg
            self._append_log(f"[ui] 已保存配置：{self._config_path}")
            self._refresh_cookie_preview()
        except Exception as e:
            dialog = CustomMessageDialog("保存失败", f"写入失败：{e}", [("确定", "PrimaryButton")], self)
            dialog.exec()

    # ---------------------------
    # Actions
    # ---------------------------
    def _open_profile_link(self) -> None:
        uid = self.ed_user_id.text().strip()
        if not uid:
            dialog = CustomMessageDialog("缺少用户 ID", "请先填写用户 ID", [("确定", "PrimaryButton")], self)
            dialog.exec()
            return
        QDesktopServices.openUrl(QUrl(f"https://weibo.cn/{uid}"))

    def _open_output_dir(self) -> None:
        out = self.ed_output_dir.text().strip()
        if not out:
            return
        p = (self._config_path.parent / out) if self._config_path else Path(out)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.resolve())))

    def _open_cookie_login(self) -> None:
        # Lazy import to avoid paying WebEngine startup cost unless user actually needs it.
        # 使用原生 WebView（优先）或回退到旧的 WebEngine 实现
        try:
            from .cookie_login_native import CookieLoginDialog  # noqa: WPS433
        except Exception:
            from .cookie_login import CookieLoginDialog  # noqa: WPS433

        dlg = CookieLoginDialog(self)
        if dlg.exec() != dlg.DialogCode.Accepted:  # type: ignore[attr-defined]
            return
        captured = dlg.captured_cookie()
        if not captured:
            return
        self._apply_captured_cookie(cookie=captured.cookie, count=int(captured.count))

    def _apply_captured_cookie(self, *, cookie: str, count: int) -> None:
        self.ed_cookie.setPlainText(cookie)
        self._append_log(f"[ui] 已获取 Cookie（{count} 项）")
        self._refresh_cookie_preview()
        # Save immediately to reduce accidental loss.
        self._save_config_from_form()

    def _refresh_cookie_preview(self) -> None:
        try:
            c = (self.ed_cookie.toPlainText() or "").strip()
        except Exception:
            c = ""
        if not c:
            self.lbl_cookie_preview.setText("当前 Cookie：未设置")
            return
        # Do not show full cookie to avoid leaking; show a short preview.
        preview = c[:120].replace("\n", " ").strip()
        if len(c) > 120:
            preview += "…"
        self.lbl_cookie_preview.setText(f"当前 Cookie：{preview}")

    def _selected_phases(self) -> List[str]:
        phases: List[str] = []
        if self.cb_list.isChecked():
            phases.append("list")
        if self.cb_detail.isChecked():
            phases.append("detail")
        if self.cb_media.isChecked():
            phases.append("media")
        if self.cb_html.isChecked():
            phases.append("html")
        return phases

    def _start_pipeline(self) -> None:
        if self._pipeline.is_running():
            return

        self._save_config_from_form()
        phases = self._selected_phases()
        if not phases:
            dialog = CustomMessageDialog("请选择阶段", "至少选择一个阶段（list/detail/media/html）", [("确定", "PrimaryButton")], self)
            dialog.exec()
            return

        # Reset UI state
        self._state = UiState()
        self._render_state()

        spec = PipelineLaunchSpec(
            config_path=self._config_path,
            phases=phases,
        )
        self._append_log(f"[ui] 启动任务 phases={','.join(phases)}")
        self._pipeline.start(spec)
        self._update_run_buttons()

    def _stop_pipeline(self) -> None:
        if not self._pipeline.is_running():
            return
        self._append_log("[ui] 请求停止…")
        self._pipeline.terminate()
        # If still running after a short grace period, kill it.
        QTimer.singleShot(2500, self._kill_if_still_running)  # type: ignore[arg-type]

    def _kill_if_still_running(self) -> None:
        if self._pipeline.is_running():
            self._append_log("[ui] 强制停止（kill）")
            self._pipeline.kill()

    # ---------------------------
    # Process callbacks
    # ---------------------------
    def _on_pipeline_started(self) -> None:
        self._append_log("[ui] 任务已启动")
        self._update_run_buttons()

    def _on_pipeline_finished(self, code: int) -> None:
        self._append_log(f"[ui] 任务已结束 exit_code={code}")
        self._update_run_buttons()

    def _on_event(self, payload: Dict[str, Any]) -> None:
        ev = str(payload.get("event") or "")
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            data = {}

        # High-signal state updates
        if ev == "phase_started":
            self._state.current_phase = str(data.get("phase") or "")
        elif ev == "list_page":
            self._state.list_page = int(data.get("page") or 0)
            self._state.list_new_total = int(data.get("new_total") or 0)
        elif ev == "detail_batch_progress":
            self._state.detail_done = int(data.get("done") or 0)
            self._state.detail_total = int(data.get("total") or 0)
        elif ev == "media_images_progress":
            self._state.media_images_done = int(data.get("done") or 0)
            self._state.media_images_total = int(data.get("total") or 0)
        elif ev == "media_videos_progress":
            self._state.media_videos_done = int(data.get("done") or 0)
            self._state.media_videos_total = int(data.get("total") or 0)

        # Pretty event line
        try:
            brief = json.dumps({"event": ev, "data": data}, ensure_ascii=False)
        except Exception:
            brief = f"{ev} {data}"
        self._append_log(brief)
        self._render_state()

    # ---------------------------
    # Rendering + logs
    # ---------------------------
    def _update_run_buttons(self) -> None:
        running = self._pipeline.is_running()
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self._act_start.setEnabled(not running)
        self._act_stop.setEnabled(running)

    def _append_log(self, line: str) -> None:
        if not line:
            return
        self.log_full.appendPlainText(line)

    def _pct(self, done: int, total: int) -> int:
        if total <= 0:
            return 0
        return max(0, min(100, int(done * 100 / total)))

    def _render_state(self) -> None:
        phase = self._state.current_phase or "-"
        self.lbl_phase.setText(f"阶段：{phase}")

        if self._state.list_page > 0:
            self.lbl_list.setText(f"列表：页 {self._state.list_page}（累计新增 {self._state.list_new_total}）")
        else:
            self.lbl_list.setText("列表：-")

        self.pb_detail.setValue(self._pct(self._state.detail_done, self._state.detail_total))
        self.pb_media_images.setValue(self._pct(self._state.media_images_done, self._state.media_images_total))
        self.pb_media_videos.setValue(self._pct(self._state.media_videos_done, self._state.media_videos_total))
    
    def _set_macos_titlebar_color(self) -> None:
        """Set macOS native title bar color to match app background"""
        import platform
        if platform.system() != "Darwin":
            return
        
        def set_color():
            try:
                import ctypes
                import ctypes.util
                
                # Load Objective-C runtime
                objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
                objc.objc_getClass.restype = ctypes.c_void_p
                objc.sel_registerName.restype = ctypes.c_void_p
                objc.objc_msgSend.restype = ctypes.c_void_p
                
                # Get NSView from Qt window
                win_id = int(self.winId())
                nsview = ctypes.c_void_p(win_id)
                
                # Get NSWindow
                window_sel = objc.sel_registerName(b"window")
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
                nswindow = objc.objc_msgSend(nsview, window_sel)
                
                if not nswindow:
                    return
                
                # Create NSColor (#ECECEC)
                NSColor = objc.objc_getClass(b"NSColor")
                colorWithRed_sel = objc.sel_registerName(b"colorWithRed:green:blue:alpha:")
                objc.objc_msgSend.argtypes = [
                    ctypes.c_void_p, ctypes.c_void_p,
                    ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double
                ]
                bg_color = objc.objc_msgSend(
                    NSColor, colorWithRed_sel,
                    ctypes.c_double(0xEC / 255.0),
                    ctypes.c_double(0xEC / 255.0),
                    ctypes.c_double(0xEC / 255.0),
                    ctypes.c_double(1.0)
                )
                
                # Set window background color
                setBackgroundColor_sel = objc.sel_registerName(b"setBackgroundColor:")
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
                objc.objc_msgSend(nswindow, setBackgroundColor_sel, bg_color)
                
            except Exception:
                # macOS titlebar color setting failed, continue silently
                pass
        
        # Defer to ensure window is fully initialized
        QTimer.singleShot(100, set_color)
        QTimer.singleShot(500, set_color)

