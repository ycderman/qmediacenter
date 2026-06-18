"""Modern dark Qt stylesheet. Accent follows the desktop (KDE) if available."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor


def desktop_accent(default="#3daee9"):
    """Read the XDG appearance accent colour (KDE Breeze etc.); fallback default."""
    try:
        from PySide6.QtDBus import QDBusInterface, QDBusReply
        iface = QDBusInterface(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Settings",
        )
        msg = iface.call("Read", "org.freedesktop.appearance", "accent-color")
        reply = QDBusReply(msg)
        if reply.isValid():
            v = reply.value()
            # nested variants -> (r,g,b) floats
            while hasattr(v, "variant"):
                v = v.variant()
            try:
                r, g, b = list(v)[:3]
                return QColor.fromRgbF(r, g, b).name()
            except Exception:
                pass
    except Exception:
        pass
    return default


def build_qss(accent="#3daee9"):
    # KDE Breeze Light palette: window #eff0f1, view #ffffff, text #232629,
    # borders #bcc0c4, disabled #9aa0a3. Accent comes from the desktop portal.
    return f"""
    * {{
        font-size: 14px;
        color: #232629;
    }}
    QMainWindow, QDialog, QWidget {{
        background-color: #eff0f1;
    }}
    QLabel {{ background: transparent; }}
    QLabel#Header {{ font-size: 15px; font-weight: 600; color: #31363b; padding: 2px 0; }}
    QLabel#Title {{ font-size: 20px; font-weight: 700; color: #1a1d1f; }}
    QLabel#Meta {{ color: #7f8c8d; font-size: 13px; }}
    QLabel#Plot {{ color: #4d5256; font-size: 13px; }}

    /* nav + action buttons */
    QPushButton {{
        background-color: #fcfcfc;
        border: 1px solid #bcc0c4;
        border-radius: 8px;
        padding: 8px 14px;
        color: #232629;
    }}
    QPushButton:hover {{ background-color: #e8f2fb; border-color: {accent}; }}
    QPushButton:pressed {{ background-color: {accent}; color: #ffffff; }}
    QPushButton:checked {{
        background-color: {accent};
        border-color: {accent};
        color: #ffffff;
        font-weight: 600;
    }}
    QPushButton:disabled {{ color: #b3b8bb; background-color: #f3f4f5; border-color: #d4d7da; }}

    /* transport buttons (play / pause / stop) — big readable glyphs */
    QPushButton#Transport {{
        font-size: 18px;
        min-width: 38px;
        padding: 6px 10px;
        background-color: #fcfcfc;
    }}
    QPushButton#Transport:hover {{ background-color: #e8f2fb; }}
    QPushButton#Transport:disabled {{ color: {accent}; background-color: #f3f4f5; }}

    /* controls bar overlaid on the video (translucent light) */
    QWidget#ControlsBar {{
        background-color: rgba(239, 240, 241, 0.92);
        border-top: 1px solid #d4d7da;
    }}

    /* search / inputs */
    QLineEdit {{
        background-color: #ffffff;
        border: 1px solid #bcc0c4;
        border-radius: 8px;
        padding: 7px 10px;
        color: #232629;
        selection-background-color: {accent};
        selection-color: #ffffff;
    }}
    QLineEdit:focus {{ border: 1px solid {accent}; }}

    /* lists (category list, live list) */
    QListWidget {{
        background-color: #ffffff;
        border: 1px solid #c4c9cd;
        border-radius: 10px;
        padding: 4px;
        outline: 0;
    }}
    QListWidget::item {{
        padding: 8px 10px;
        border-radius: 7px;
        margin: 1px 2px;
    }}
    QListWidget::item:hover {{ background-color: #e8f2fb; }}
    QListWidget::item:selected {{ background-color: {accent}; color: #ffffff; }}

    /* poster grid */
    QListWidget#Grid {{ background-color: #eff0f1; border: none; }}
    QListWidget#Grid::item {{
        margin: 8px; padding: 6px;
        border-radius: 10px;
        background-color: #ffffff;
        border: 1px solid #e0e3e6;
        color: #232629;
    }}
    QListWidget#Grid::item:hover {{ background-color: #e8f2fb; border-color: {accent}; }}
    QListWidget#Grid::item:selected {{ background-color: {accent}; color: #ffffff; }}

    /* home page rows */
    QScrollArea#HomeScroll {{ background-color: #eff0f1; border: none; }}
    QListWidget#Strip {{ background-color: transparent; border: none; outline: 0; }}
    QListWidget#Strip::item {{
        margin: 4px 6px; padding: 6px;
        border-radius: 10px;
        background-color: #ffffff;
        border: 1px solid #e0e3e6;
        color: #232629;
    }}
    QListWidget#Strip::item:hover {{ background-color: #e8f2fb; border-color: {accent}; }}
    QListWidget#Strip::item:selected {{ background-color: #e8f2fb; border-color: {accent}; color: #232629; }}

    /* info card */
    QFrame#InfoCard {{
        background-color: #f7f8f9;
        border: 1px solid #d4d7da;
        border-radius: 12px;
    }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: #bcc0c4; border-radius: 5px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {accent}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

    QSlider::groove:horizontal {{ height: 5px; background: #c4c9cd; border-radius: 3px; }}
    QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 3px; }}
    QSlider::handle:horizontal {{
        background: {accent}; width: 14px; height: 14px;
        margin: -5px 0; border-radius: 7px; border: 1px solid #ffffff;
    }}
    QProgressBar {{
        background: #d4d7da; border: none; border-radius: 6px;
        text-align: center; color: #232629; height: 18px;
    }}
    QProgressBar::chunk {{ background-color: {accent}; border-radius: 6px; }}

    QSplitter::handle {{ background: #d4d7da; }}
    QComboBox {{
        background: #ffffff; border: 1px solid #bcc0c4; border-radius: 8px;
        padding: 6px 10px; color: #232629;
    }}
    QComboBox QAbstractItemView {{
        background: #ffffff; color: #232629;
        selection-background-color: {accent}; selection-color: #ffffff;
    }}
    QTabWidget::pane {{ border: 1px solid #c4c9cd; border-radius: 8px; }}
    QTabBar::tab {{
        background: #e4e6e8; color: #232629;
        padding: 7px 14px; border: 1px solid #c4c9cd;
        border-top-left-radius: 7px; border-top-right-radius: 7px; margin-right: 2px;
    }}
    QTabBar::tab:selected {{ background: #ffffff; border-bottom-color: #ffffff; }}
    """
