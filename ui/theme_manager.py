"""ThemeManager — loads QSS themes and applies desktop accent colour.

QSS files are read via importlib.resources so the wheel install path works
correctly: the `themes` package ships *.qss as package-data and is looked up
through the standard import machinery regardless of install location.
"""
from __future__ import annotations

import importlib.resources
import logging
from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

log = logging.getLogger(__name__)

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


def _read_qss(filename: str) -> str | None:
    """Read a QSS file from the `themes` package via importlib.resources.

    Works both in editable installs (source tree) and real wheel/sdist installs
    because setuptools ships themes/*.qss as package-data inside the `themes`
    package.
    """
    try:
        ref = importlib.resources.files("themes").joinpath(filename)
        return ref.read_text(encoding="utf-8")
    except Exception as exc:
        log.error("ThemeManager: cannot read %s via importlib.resources: %s", filename, exc)
        return None


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
        raw = _read_qss(meta["file"])
        if raw is None:
            return False

        resolved_accent = accent or self._detect_desktop_accent(meta["default_accent"])
        qss = raw.replace(_ACCENT_PLACEHOLDER, resolved_accent)

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


# Module-level singleton
_manager: ThemeManager | None = None


def get_manager() -> ThemeManager:
    global _manager
    if _manager is None:
        _manager = ThemeManager()
    return _manager
