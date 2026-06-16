#!/usr/bin/env python3
"""QPlayer — a Qt6/libmpv IPTV player with Xtream Codes support."""
import sys
import locale
import logging

from PySide6.QtWidgets import QApplication

from iptv import config
from iptv.xtream import XtreamClient
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow


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
    app.setApplicationName("QPlayer")
    app.setDesktopFileName("io.github.ycderman.qplayer")
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
