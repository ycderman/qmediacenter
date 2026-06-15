#!/usr/bin/env python3
"""QtIPTV — a Qt6/libmpv IPTV player with Xtream Codes support."""
import sys
import locale
import logging

from PySide6.QtWidgets import QApplication

from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("QtIPTV")
    # Qt resets LC_NUMERIC from the environment; libmpv requires "C".
    locale.setlocale(locale.LC_NUMERIC, "C")

    login = LoginDialog()
    if login.exec() != LoginDialog.Accepted:
        return 0

    win = MainWindow(login.profile, login.client)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
