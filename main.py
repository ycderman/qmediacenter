#!/usr/bin/env python3
"""QMediaCenter — a Qt6/libmpv media center (IPTV + local/network library)."""
import importlib.resources
import locale
import logging
import os
import sys


def _get_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version
        try:
            return version("qmediacenter")
        except PackageNotFoundError:
            pass
    except ImportError:
        pass
    return "0.0.0+dev"


def _parse_args():
    """Handle --version / --help before touching Qt so they work without a display."""
    import argparse

    p = argparse.ArgumentParser(
        prog="qmediacenter",
        description="Qt6/libmpv media center — IPTV, Emby, Plex and local media",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {_get_version()}")
    # parse_known_args lets Qt-specific flags pass through unchanged
    _args, remaining = p.parse_known_args()
    return remaining


# ---------------------------------------------------------------------------
# Icon helpers
# ---------------------------------------------------------------------------

def _rounded_icon_from_pixmap(pixmap, size: int = 256):
    """Return a QIcon with rounded corners built from *pixmap*."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPixmap

    src = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    out = QPixmap(src.size())
    out.fill(Qt.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    r = src.width() * 0.22
    path.addRoundedRect(0, 0, src.width(), src.height(), r, r)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, src)
    painter.end()
    return QIcon(out)


def _app_icon():
    """Return a QIcon for the application window.

    Tries three strategies in order so the icon works across all install types:

    1. Read PNG bytes via importlib.resources from the ``data`` package.
       This is the correct path for both wheel installs and editable installs —
       no temporary file is involved, so there is no race condition with context
       managers closing.

    2. Repo-relative ``data/qmediacenter.png`` (plain ``python main.py`` from
       the source tree without installing).

    3. XDG icon theme look-up by app ID (distro packages install the icon into
       ``/usr/share/icons/hicolor/``; Qt finds it automatically).
    """
    from PySide6.QtGui import QIcon, QPixmap

    # 1. Package data — bytes read directly, no temp file
    try:
        ref = importlib.resources.files("data").joinpath("qmediacenter.png")
        png_bytes = ref.read_bytes()
        pixmap = QPixmap()
        if pixmap.loadFromData(png_bytes, "PNG") and not pixmap.isNull():
            return _rounded_icon_from_pixmap(pixmap)
    except Exception:
        pass

    # 2. Repo-relative fallback (dev / editable install without package data)
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in ("data/qmediacenter.png", "qmediacenter.png"):
        path = os.path.join(here, cand)
        if os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                return _rounded_icon_from_pixmap(pixmap)
            return QIcon(path)

    # 3. System icon theme (distro packages)
    return QIcon.fromTheme("io.github.ycderman.qmediacenter")


# ---------------------------------------------------------------------------
# Profile helpers
# ---------------------------------------------------------------------------

def _auto_profile():
    """Return (profile, client) for the last-used Xtream profile, or (None, None)."""
    from iptv import config
    from iptv.xtream import XtreamClient

    profiles = config.load_profiles()
    if not profiles:
        return None, None
    last = config.load_settings().get("last_profile")
    profile = next((p for p in profiles if p.get("name") == last), profiles[-1])
    client = XtreamClient(profile["host"], profile["username"], profile["password"])
    if client.authenticate():
        return profile, client
    return None, None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # --version / --help are handled here, before Qt is imported
    extra_args = _parse_args()

    from PySide6.QtWidgets import QApplication

    app = QApplication([sys.argv[0]] + extra_args)
    app.setApplicationName("QMediaCenter")
    app.setApplicationVersion(_get_version())
    app.setDesktopFileName("io.github.ycderman.qmediacenter")
    app.setWindowIcon(_app_icon())

    # Qt resets LC_NUMERIC from the environment; libmpv requires "C".
    locale.setlocale(locale.LC_NUMERIC, "C")

    from iptv import config
    from ui.theme_manager import get_manager as get_theme_manager

    _settings = config.load_settings()
    get_theme_manager().apply(_settings.get("theme", "breeze-light"))

    profile, client = _auto_profile()

    from media.mpris import MprisAdapter, ScreenInhibitor
    from ui.main_window import MainWindow

    win = MainWindow(profile, client)
    win.mpris = MprisAdapter(win.player, initial_volume=win.settings.get("volume", 100))
    win.inhibitor = ScreenInhibitor()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
