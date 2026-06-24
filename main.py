#!/usr/bin/env python3
"""QMediaCenter — a Qt6/libmpv media center (IPTV + local/network library)."""
import importlib.resources
import locale
import logging
import os
import sys


def _get_version() -> str:
    try:
        from importlib.metadata import version, PackageNotFoundError
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
    # Parse only known args so Qt-specific flags are not rejected
    _args, _remaining = p.parse_known_args()
    return _remaining


def _icon_pixmap_path() -> str | None:
    """Resolve the app icon path across all install scenarios.

    Priority:
    1. importlib.resources (wheel/sdist install, data package)
    2. Repo-relative data/ dir  (editable / dev run)
    3. XDG icon theme fallback  (distro package → system-wide icon)
    """
    # 1. Python package data (wheel install)
    try:
        ref = importlib.resources.files("data").joinpath("qmediacenter.png")
        if ref.is_file():
            # Use as_file() context manager for zip-packaged resources
            with importlib.resources.as_file(ref) as p:
                return str(p)
    except Exception:
        pass

    # 2. Dev / editable install: look next to this file
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in ("data/qmediacenter.png", "qmediacenter.png"):
        path = os.path.join(here, cand)
        if os.path.exists(path):
            return path

    # 3. System-installed icon (distro packages put it in hicolor icon theme)
    return None


def _rounded_icon(path: str, size: int = 256):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPixmap

    src = QPixmap(path)
    if src.isNull():
        return QIcon(path)
    src = src.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    out = QPixmap(src.size())
    out.fill(Qt.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    r = src.width() * 0.22
    clip.addRoundedRect(0, 0, src.width(), src.height(), r, r)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, src)
    painter.end()
    return QIcon(out)


def _auto_profile():
    """Return (profile, client) for the last-used profile, or (None, None)."""
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


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Handle --version / --help without starting Qt
    extra_args = _parse_args()

    from PySide6.QtWidgets import QApplication

    app = QApplication([sys.argv[0]] + extra_args)
    app.setApplicationName("QMediaCenter")
    app.setApplicationVersion(_get_version())
    app.setDesktopFileName("io.github.ycderman.qmediacenter")

    # Icon — works from wheel, editable install, and distro package
    icon_path = _icon_pixmap_path()
    if icon_path:
        app.setWindowIcon(_rounded_icon(icon_path))
    else:
        # Distro packages install to the system icon theme; Qt picks it up by name
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon.fromTheme("io.github.ycderman.qmediacenter"))

    # Qt resets LC_NUMERIC from the environment; libmpv requires "C".
    locale.setlocale(locale.LC_NUMERIC, "C")

    from iptv import config
    from ui.theme_manager import get_manager as get_theme_manager

    # Apply saved theme before any window is created
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
