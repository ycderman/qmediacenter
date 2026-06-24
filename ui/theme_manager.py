"""ThemeManager — loads QSS themes and applies desktop accent colour."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

log = logging.getLogger(__name__)

_THEMES_DIR = Path(__file__).parent.parent / "themes"

THEMES: dict[str, dict] = {
    "breeze-light": {
        "id": "breeze-light",
        "name": "Breeze Light",
        "variant": "light",
        "file": "breeze-light.qss",
        "default_accent": "#3daee9",
        "preview_bg": "#eff0f1",
        "preview_fg": "#232629",
    },
    "breeze-dark": {
        "id": "breeze-dark",
        "name": "Breeze Dark",
        "variant": "dark",
        "file": "breeze-dark.qss",
        "default_accent": "#3daee9",
        "preview_bg": "#31363b",
        "preview_fg": "#eff0f1",
    },
}

_DEFAULT_THEME = "breeze-light"
_ACCENT_PLACEHOLDER = "@ACCENT@"


class ThemeManager:
    """Manages QSS theme loading and accent colour injection."""

    def __init__(self):
        self._current_id: str = _DEFAULT_THEME
        self._accent: str = THEMES[_DEFAULT_THEME]["default_accent"]

    # ---- public API -------------------------------------------------------

    def available_themes(self) -> list[dict]:
        return list(THEMES.values())

    def current_theme_id(self) -> str:
        return self._current_id

    def current_accent(self) -> str:
        return self._accent

    def apply(self, theme_id: str, accent: str | None = None) -> bool:
        if theme_id not in THEMES:
            log.warning("ThemeManager: unknown theme %r, falling back to %s", theme_id, _DEFAULT_THEME)
            theme_id = _DEFAULT_THEME

        meta = THEMES[theme_id]
        qss_path = _THEMES_DIR / meta["file"]

        if not qss_path.exists():
            log.error("ThemeManager: QSS file missing: %s", qss_path)
            return False

        resolved_accent = accent or self._detect_desktop_accent(meta["default_accent"])
        qss = qss_path.read_text(encoding="utf-8").replace(_ACCENT_PLACEHOLDER, resolved_accent)

        app = QApplication.instance()
        if app is None:
            log.error("ThemeManager.apply called before QApplication exists")
            return False

        app.setStyleSheet(qss)
        self._current_id = theme_id
        self._accent = resolved_accent
        log.info("ThemeManager: applied %s (accent %s)", theme_id, resolved_accent)
        return True

    def reapply_accent(self, accent: str) -> bool:
        return self.apply(self._current_id, accent=accent)

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def _detect_desktop_accent(default: str) -> str:
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
                while hasattr(v, "variant"):
                    v = v.variant()
                r, g, b = list(v)[:3]
                return QColor.fromRgbF(r, g, b).name()
        except Exception:
            pass
        return default

    @staticmethod
    def load_qss_for_style_py(accent: str = "#3daee9") -> str:
        """Compatibility shim so style.py callers still work during migration."""
        path = _THEMES_DIR / "breeze-light.qss"
        if path.exists():
            return path.read_text(encoding="utf-8").replace(_ACCENT_PLACEHOLDER, accent)
        return ""


# Module-level singleton
_manager: ThemeManager | None = None


def get_manager() -> ThemeManager:
    global _manager
    if _manager is None:
        _manager = ThemeManager()
    return _manager
