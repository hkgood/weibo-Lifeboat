from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory
import os
import platform


@dataclass(frozen=True)
class Theme:
    is_dark: bool
    bg: str
    base: str
    text: str
    secondary_text: str
    card_bg: str
    border: str
    sidebar_bg: str
    sidebar_sel_bg: str
    sidebar_sel_text: str
    sidebar_hover_bg: str
    primary: str
    primary_btn: str
    primary_btn_hover: str
    primary_btn_pressed: str


def _hex(c: QColor) -> str:
    return c.name(QColor.NameFormat.HexRgb)


def _alpha(c: QColor, a: float) -> QColor:
    c2 = QColor(c)
    c2.setAlphaF(max(0.0, min(1.0, a)))
    return c2


def build_theme(p: QPalette) -> Theme:
    window = p.color(QPalette.ColorRole.Window)
    text = p.color(QPalette.ColorRole.WindowText)
    base = p.color(QPalette.ColorRole.Base)
    highlight = p.color(QPalette.ColorRole.Highlight)

    # Rough but reliable: dark theme tends to have bright text on dark window.
    is_dark = text.lightnessF() > window.lightnessF()

    if is_dark:
        card_bg = _hex(QColor(35, 35, 38))
        # NOTE: QSS doesn't accept hex alpha reliably across Qt versions; use rgba().
        border = "rgba(235,235,245,0.16)"
        sidebar_bg = _hex(QColor(28, 28, 30))
        secondary_text = _hex(QColor(235, 235, 245, 153))
        sidebar_sel_text = _hex(QColor(255, 255, 255))
    else:
        card_bg = "#EFEFEF"
        # macOS-like subtle separator
        border = "rgba(60,60,67,0.18)"
        sidebar_bg = _hex(QColor(246, 246, 247))
        secondary_text = _hex(QColor(60, 60, 67, 153))
        sidebar_sel_text = _hex(QColor(255, 255, 255))

    # Base accent from system highlight, but primary buttons should be a touch deeper and opaque.
    # On macOS, the default accent button looks close to #007AFF.
    primary = _hex(highlight)
    # Prefer a stable, opaque macOS-like blue regardless of palette quirks.
    # (Some palettes/highlight colors can be too light, making the button look translucent.)
    primary_btn = "#007AFF"
    primary_btn_hover = "#006FE6"
    primary_btn_pressed = "#005FCC"
    # Sidebar selection / hover:
    # - Light mode: subtle tint + dark text (macOS sidebar style)
    # - Dark mode: a bit stronger tint + white text
    try:
        r, g, b = highlight.red(), highlight.green(), highlight.blue()
    except Exception:
        r, g, b = 0, 122, 255
    # Make selection a bit stronger so it's clearly readable, but still "tinted"
    # (macOS sidebar selection is not a hard filled button).
    # Per request: make hover/selected far less transparent (more visible).
    sidebar_sel_bg = f"rgba({r},{g},{b},0.50)"
    sidebar_hover_bg = f"rgba({r},{g},{b},0.35)"
    if not is_dark:
        sidebar_sel_text = _hex(text)

    return Theme(
        is_dark=is_dark,
        bg=_hex(window),
        base=_hex(base),
        text=_hex(text),
        secondary_text=secondary_text,
        card_bg=card_bg,
        border=border,
        sidebar_bg=sidebar_bg,
        sidebar_sel_bg=sidebar_sel_bg,
        sidebar_sel_text=sidebar_sel_text,
        sidebar_hover_bg=sidebar_hover_bg,
        primary=primary,
        primary_btn=primary_btn,
        primary_btn_hover=primary_btn_hover,
        primary_btn_pressed=primary_btn_pressed,
    )


def build_theme_openai_fm() -> Theme:
    """
    Light-only, web-like theme inspired by https://www.openai.fm/
    """
    # Neutrals
    bg = "#ECECEC"  # page background
    base = "#FFFFFF"
    text = "#111827"
    secondary_text = "#6B7280"
    card_bg = "#EFEFEF"
    border = "#E5E7EB"

    # Sidebar: blend into page, minimal contrast
    sidebar_bg = bg
    sidebar_hover_bg = "#EAECEF"
    sidebar_sel_bg = "#E5E7EB"
    sidebar_sel_text = text

    # Accent (primary action)
    primary = "#FF4A00"
    primary_btn = "#FF4A00"
    primary_btn_hover = "#E54300"
    primary_btn_pressed = "#CC3C00"

    return Theme(
        is_dark=False,
        bg=bg,
        base=base,
        text=text,
        secondary_text=secondary_text,
        card_bg=card_bg,
        border=border,
        sidebar_bg=sidebar_bg,
        sidebar_sel_bg=sidebar_sel_bg,
        sidebar_sel_text=sidebar_sel_text,
        sidebar_hover_bg=sidebar_hover_bg,
        primary=primary,
        primary_btn=primary_btn,
        primary_btn_hover=primary_btn_hover,
        primary_btn_pressed=primary_btn_pressed,
    )


def _pick_font() -> QFont:
    # Prefer a clean, web-like sans. On macOS, SF is usually available.
    for family in ["SF Pro Text", "SF Pro Display", "Inter", "Helvetica Neue", "Arial"]:
        f = QFont(family)
        if f.exactMatch():
            f.setPointSize(13)
            return f
    f = QFont()
    f.setPointSize(13)
    return f


def apply_app_style(app: QApplication) -> Theme:
    """
    Apply a macOS-friendly, precise layout + QSS skin.

    We keep it subtle so Qt can still use native rendering on macOS where possible,
    but we tighten spacing/typography and make the UI feel intentional.
    """
    # IMPORTANT: Qt's native "macos" style (libqmacstyle) has been observed to segfault
    # on newer macOS versions in some widget paint paths (e.g. QCheckBox).
    #
    # To keep the app stable, default to the more robust "Fusion" style on macOS 26+,
    # while keeping an escape hatch to force styles for debugging.
    #
    # Env override:
    #   WEIBO_GUI_STYLE=auto|macos|fusion
    style_pref = (os.environ.get("WEIBO_GUI_STYLE") or "auto").strip().lower()
    # Theme override:
    #   WEIBO_GUI_THEME=openai_fm|system
    theme_pref = (os.environ.get("WEIBO_GUI_THEME") or "openai_fm").strip().lower()

    mac_ver = platform.mac_ver()[0] or ""
    major = 0
    try:
        major = int(mac_ver.split(".", 1)[0])
    except Exception:
        major = 0

    if style_pref == "macos":
        st = QStyleFactory.create("macos")
        if st is not None:
            app.setStyle(st)
    elif style_pref == "fusion":
        st = QStyleFactory.create("Fusion")
        if st is not None:
            app.setStyle(st)
    else:
        # auto: prefer Fusion for consistent QSS rendering (web-like).
        st = QStyleFactory.create("Fusion")
        if st is not None:
            app.setStyle(st)
        else:
            # Fallback to macos where available (older Qt builds).
            st2 = QStyleFactory.create("macos")
            if st2 is not None:
                app.setStyle(st2)

    app.setFont(_pick_font())

    if theme_pref in {"system", "auto", "native"}:
        theme = build_theme(app.palette())
    else:
        theme = build_theme_openai_fm()
    # Let widgets (e.g. cards) query this without passing Theme everywhere.
    app.setProperty("weibo_is_dark", bool(theme.is_dark))

    # Depth helpers:
    # Qt QSS doesn't support CSS box-shadow (including inset), and "different border sides"
    # (e.g. a darker/bolder border-bottom) causes dark 1px seams on rounded corners due to
    # anti-aliasing. So we keep borders uniform and express depth via subtle fills/gradients.
    elev_border = theme.border
    # Reduce roundness (openai.fm is a bit tighter than the current UI)
    # User tweak: slightly increase card radius by ~2-4px for a softer look.
    card_radius = 8
    control_radius = 6
    small_radius = 2
    tab_radius = 8
    btn_bg_top = ("rgba(255,255,255,0.10)" if theme.is_dark else "#F4F4F4")
    btn_bg_bot = ("rgba(255,255,255,0.06)" if theme.is_dark else "#F8FAFC")
    input_bg_top = ("rgba(255,255,255,0.06)" if theme.is_dark else "#FFFFFF")
    input_bg_bot = ("rgba(255,255,255,0.03)" if theme.is_dark else "#F9FAFB")
    # Input fill (light gray like the reference page; not pure white)
    input_fill = ("rgba(255,255,255,0.05)" if theme.is_dark else "#F8FAFC")
    input_fill_bottom = ("rgba(255,255,255,0.03)" if theme.is_dark else "#F3F4F6")
    # "Inset shadow" simulation for inputs (avoid near-black at the very edge)
    input_inset_top = ("rgba(0,0,0,0.18)" if theme.is_dark else "#EEF2F7")

    qss = f"""
    /* Global */
    QMainWindow {{
      background: {theme.bg};
    }}
    QWidget {{
      color: {theme.text};
      font-size: 13px;
    }}
    QWidget#ContentArea {{
      background: {theme.bg};
    }}
    QStackedWidget {{
      background: {theme.bg};
    }}
    QScrollArea {{
      background: transparent;
    }}
    QScrollArea::viewport {{
      background: transparent;
    }}
    QScrollArea > QWidget#qt_scrollarea_viewport {{
      background: transparent;
    }}
    QWidget#ScrollBody {{
      background: transparent;
    }}
    QMenuBar {{
      background: {theme.bg};
      color: {theme.text};
    }}
    QMenu {{
      background: {theme.card_bg};
      border: 1px solid {theme.border};
      padding: 6px;
    }}
    QMenu::item {{
      padding: 6px 10px;
      border-radius: 8px;
    }}
    QMenu::item:selected {{
      background: {theme.sidebar_hover_bg};
    }}
    QLabel#PageTitle {{
      font-size: 20px;
      font-weight: 600;
      color: {theme.text};
      padding: 0px;
      margin: 0px 0px 8px 0px;
      margin-left: -4px;
    }}
    QLabel#PageSubtitle {{
      font-size: 13px;
      color: {theme.secondary_text};
      padding: 0px;
      margin: 0px;
      line-height: 18px;
    }}
    QWidget#PageHeader {{
      padding: 0px;
      margin: 0px;
    }}
    /* Page header: no margin hacks. The header/cards insets are handled per-page in layouts. */

    /* Sidebar */
    QListWidget#Sidebar {{
      background: {theme.sidebar_bg};
      border: none;
      border-right: 1px solid {theme.border};
      padding: 8px;  /* Reduced padding */
      outline: none;
    }}
    QListWidget#Sidebar::item {{
      /* openai.fm-like "tab cards" - shadow drawn by delegate */
      background-color: transparent;  /* Delegate draws everything */
      border: none;  /* Delegate draws border */
      /* Text positioning handled by SidebarItemDelegate for precise top-left alignment */
      /* Padding here only affects background/border rendering, not text */
      padding: 0px;
      border-radius: {tab_radius}px;
      margin: 0px;  /* Margin doesn't affect spacing; QListWidget.setSpacing() controls it */
      color: {theme.text};
      font-size: 14px;
      min-height: 80px;  /* Increased from 60px to 80px (added 20px) */
    }}
    QListWidget#Sidebar::item:hover {{
      background: transparent;
    }}
    QListWidget#Sidebar::item:selected {{
      background-color: transparent;
      color: {theme.text};
      font-weight: 600;
    }}

    /* Cards */
    QFrame#Card {{
      background: #F8F8F8;
      border: 1px solid {elev_border};
      border-radius: {card_radius}px;
    }}
    QLabel#CardTitle {{
      font-size: 15px;
      font-weight: 600;
      color: {theme.text};
      padding: 0px;
      margin: 0px 0px 2px 0px;
      margin-left: -4px;
    }}
    QLabel#CardHint {{
      font-size: 12px;
      color: {theme.secondary_text};
      line-height: 16px;
    }}

    /* Inputs */
    QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
      border: 1px solid {elev_border};
      border-radius: {control_radius}px;
      padding: 9px 12px;
      background: #F9F9F9;
      selection-background-color: {theme.primary};
      font-size: 13px;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
      border: 2px solid {theme.primary};
    }}
    QPlainTextEdit {{
      padding-top: 8px;
      padding-bottom: 8px;
    }}

    /* SpinBox steppers: soften (still usable) */
    QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
      subcontrol-origin: border;
      background: transparent;
      border-left: 1px solid {theme.border};
      width: 22px;
    }}
    QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow {{
      width: 10px;
      height: 10px;
    }}
    QSpinBox, QDoubleSpinBox {{
      padding-right: 28px; /* keep text away from steppers */
    }}
    QAbstractSpinBox::up-button {{
      subcontrol-position: top right;
      border-top-right-radius: {control_radius}px;
    }}
    QAbstractSpinBox::down-button {{
      subcontrol-position: bottom right;
      border-bottom-right-radius: {control_radius}px;
    }}
    QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{
      background: rgba(0,0,0,0.04);
    }}
    QAbstractSpinBox::up-arrow {{
      image: url({("assets/chevron_up_light.svg" if theme.is_dark else "assets/chevron_up_dark.svg")});
    }}
    QAbstractSpinBox::down-arrow {{
      image: url({("assets/chevron_down_light.svg" if theme.is_dark else "assets/chevron_down_dark.svg")});
    }}

    /* Checkboxes */
    QCheckBox {{
      font-size: 13px;
      spacing: 8px;
    }}
    QCheckBox::indicator {{
      width: 14px;
      height: 14px;
      border-radius: {small_radius}px;
      border: 1px solid {elev_border};
      background: {input_bg_top};
    }}
    QCheckBox::indicator:hover {{
      border: 1px solid {theme.primary};
    }}
    QCheckBox::indicator:checked {{
      border: 1px solid {theme.primary_btn};
      background: {theme.primary_btn};
      image: url(assets/checkmark.svg);
    }}
    QCheckBox::indicator:checked:disabled {{
      background: rgba(255,74,0,0.40);
    }}

    /* Buttons */
    QPushButton {{
      border: none;
      border-radius: {control_radius}px;
      padding: 8px 14px;
      background: #FCFCFC;
      font-size: 13px;
      min-height: 26px;
      min-width: 100px;
    }}
    QPushButton:hover {{
      background: {("#FFFFFF" if not theme.is_dark else "rgba(255,255,255,0.08)")};
    }}
    QPushButton:pressed {{
      /* pressed = slightly darker fill */
      background: {("#EEF2F7" if not theme.is_dark else "rgba(0,0,0,0.22)")};
    }}
    QPushButton:disabled {{
      color: rgba(60,60,67,0.50);
      background: #E8E8E8;
    }}
    QPushButton#PrimaryButton {{
      border: none;
      color: white;
      background: {theme.primary_btn};
      padding: 9px 16px;
      font-weight: 600;
      font-size: 13px;
      min-height: 26px;
      min-width: 100px;
      border-radius: {control_radius}px;
    }}
    QPushButton#PrimaryButton:hover {{
      background: {theme.primary_btn_hover};
    }}
    QPushButton#PrimaryButton:pressed {{
      background: {theme.primary_btn_pressed};
    }}

    /* Progress */
    QProgressBar {{
      border: 1px solid {theme.border};
      border-radius: 8px;
      background: rgba(17,24,39,0.05);
      height: 16px;
      text-align: center;
      color: {theme.text};
      font-size: 11px;
      font-weight: 500;
    }}
    QProgressBar::chunk {{
      border-radius: 7px;
      background: rgba(255, 74, 0, 0.25);
    }}

    /* Toolbars */
    QToolBar {{
      border: none;
      background: transparent;
      spacing: 8px;
      padding: 6px 8px;
    }}
    QToolButton {{
      border: none;
      border-radius: {control_radius}px;
      padding: 8px 12px;
      background: {btn_bg_top};
      font-size: 13px;
    }}
    QToolButton:hover {{
      background: {("rgba(255,255,255,0.14)" if theme.is_dark else "rgba(17,24,39,0.04)")};
    }}
    QToolButton:checked {{
      background: rgba(17,24,39,{22 if theme.is_dark else 7});
    }}

    /* Log views: avoid nested borders ("all lines" look) */
    QPlainTextEdit#LogView {{
      border: none;
      background: transparent;
      padding: 0px;
      font-size: 12px;
    }}

    /* Scrollbars: macOS-like rounded overlay handle */
    QScrollBar:vertical {{
      background: transparent;
      width: 14px;
      margin: 4px 4px 4px 4px;
    }}
    QScrollBar::handle:vertical {{
      background: rgba({255 if theme.is_dark else 17},{255 if theme.is_dark else 24},{255 if theme.is_dark else 39},{28 if theme.is_dark else 46});
      min-height: 30px;
      border-radius: {small_radius}px;
    }}
    QScrollBar::handle:vertical:hover {{
      background: rgba({255 if theme.is_dark else 17},{255 if theme.is_dark else 24},{255 if theme.is_dark else 39},{38 if theme.is_dark else 64});
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
      height: 0px;
      background: transparent;
      border: none;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
      background: transparent;
    }}

    QScrollBar:horizontal {{
      background: transparent;
      height: 10px;
      margin: 1px 2px 1px 2px;
    }}
    QScrollBar::handle:horizontal {{
      background: rgba({255 if theme.is_dark else 17},{255 if theme.is_dark else 24},{255 if theme.is_dark else 39},{28 if theme.is_dark else 46});
      min-width: 30px;
      border-radius: {small_radius}px;
    }}
    QScrollBar::handle:horizontal:hover {{
      background: rgba({255 if theme.is_dark else 17},{255 if theme.is_dark else 24},{255 if theme.is_dark else 39},{38 if theme.is_dark else 64});
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
      width: 0px;
      background: transparent;
      border: none;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
      background: transparent;
    }}
    """
    app.setStyleSheet(qss)
    return theme


