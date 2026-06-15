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
    return f"""
    * {{
        font-size: 14px;
        color: #e6e6ea;
    }}
    QMainWindow, QDialog, QWidget {{
        background-color: #16161e;
    }}
    QLabel {{ background: transparent; }}
    QLabel#Header {{ font-size: 15px; font-weight: 600; color: #c8c8d4; padding: 2px 0; }}
    QLabel#Title {{ font-size: 20px; font-weight: 700; color: #ffffff; }}
    QLabel#Meta {{ color: #9a9ab0; font-size: 13px; }}
    QLabel#Plot {{ color: #c4c4d2; font-size: 13px; }}

    /* nav + action buttons */
    QPushButton {{
        background-color: #24242f;
        border: 1px solid #2f2f3d;
        border-radius: 8px;
        padding: 8px 14px;
        color: #e6e6ea;
    }}
    QPushButton:hover {{ background-color: #2e2e3c; }}
    QPushButton:pressed {{ background-color: {accent}; color: #ffffff; }}
    QPushButton:checked {{
        background-color: {accent};
        border-color: {accent};
        color: #ffffff;
        font-weight: 600;
    }}
    QPushButton:disabled {{ color: #6a6a7a; background-color: #1d1d27; }}

    /* search / inputs */
    QLineEdit {{
        background-color: #1d1d27;
        border: 1px solid #2f2f3d;
        border-radius: 8px;
        padding: 7px 10px;
        selection-background-color: {accent};
    }}
    QLineEdit:focus {{ border: 1px solid {accent}; }}

    /* lists (category list, live list) */
    QListWidget {{
        background-color: #1a1a23;
        border: 1px solid #26263180;
        border-radius: 10px;
        padding: 4px;
        outline: 0;
    }}
    QListWidget::item {{
        padding: 8px 10px;
        border-radius: 7px;
        margin: 1px 2px;
    }}
    QListWidget::item:hover {{ background-color: #25252f; }}
    QListWidget::item:selected {{ background-color: {accent}; color: #ffffff; }}

    /* poster grid */
    QListWidget#Grid {{ background-color: #16161e; border: none; }}
    QListWidget#Grid::item {{
        margin: 8px; padding: 6px;
        border-radius: 10px;
        background-color: #1c1c26;
        color: #d4d4de;
    }}
    QListWidget#Grid::item:hover {{ background-color: #26263a; }}
    QListWidget#Grid::item:selected {{ background-color: {accent}; color: #ffffff; }}

    /* info card */
    QFrame#InfoCard {{
        background-color: #1b1b25;
        border: 1px solid #2a2a38;
        border-radius: 12px;
    }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: #3a3a4a; border-radius: 5px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {accent}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

    QSlider::groove:horizontal {{ height: 5px; background: #2c2c3a; border-radius: 3px; }}
    QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 3px; }}
    QSlider::handle:horizontal {{
        background: #ffffff; width: 14px; height: 14px;
        margin: -5px 0; border-radius: 7px;
    }}
    QProgressBar {{
        background: #1d1d27; border: none; border-radius: 6px;
        text-align: center; color: #e6e6ea; height: 18px;
    }}
    QProgressBar::chunk {{ background-color: {accent}; border-radius: 6px; }}

    QSplitter::handle {{ background: #20202a; }}
    QComboBox {{
        background: #1d1d27; border: 1px solid #2f2f3d; border-radius: 8px;
        padding: 6px 10px;
    }}
    """
