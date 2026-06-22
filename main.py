#!/usr/bin/env python3
"""QMediaCenter — a Qt6/libmpv media center (IPTV + local/network library)."""
import os
import sys
import locale
import logging

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPainterPath
from PySide6.QtCore import Qt

from iptv import config
from iptv.xtream import XtreamClient
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow


def _rounded_icon(path, size=256):
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
    profiles = config.load_profiles()
    if not profiles:
        return None, None
    last = config.load_settings().get("last_profile")
    profile = next((p for p in profiles if p.get("name") == last), profiles[-1])
    client = XtreamClient(profile["host"], profile["username"], profile["password"])
    if client.authenticate():
        return profile, client
    return None, None


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("QMediaCenter")
    app.setDesktopFileName("io.github.ycderman.qmediacenter")
    _here = os.path.dirname(os.path.abspath(__file__))
    for _cand in ("data/qmediacenter.png", "qmediacenter.png"):
        _icon = os.path.join(_here, _cand)
        if os.path.exists(_icon):
            app.setWindowIcon(_rounded_icon(_icon))
            break
    # Qt resets LC_NUMERIC from the environment; libmpv requires "C".
    locale.setlocale(locale.LC_NUMERIC, "C")

    # Open straight into the last-used source; only prompt if that fails.
    profile, client = _auto_profile()
    if profile is None:
        login = LoginDialog()
        if login.exec() != LoginDialog.Accepted:
            return 0
        profile, client = login.profile, login.client

    win = MainWindow(profile, client)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
