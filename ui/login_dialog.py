"""Xtream profile login / selection dialog."""
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QMessageBox,
)
from PySide6.QtCore import Qt
from iptv import config
from iptv.xtream import XtreamClient


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QtIPTV — Xtream Login")
        self.setMinimumWidth(420)
        self.profile = None
        self._profiles = config.load_profiles()

        root = QVBoxLayout(self)

        if self._profiles:
            root.addWidget(QLabel("Saved profiles:"))
            self.combo = QComboBox()
            self.combo.addItem("— New profile —", None)
            for p in self._profiles:
                self.combo.addItem(p["name"], p)
            self.combo.currentIndexChanged.connect(self._on_select)
            root.addWidget(self.combo)

        form = QFormLayout()
        self.name = QLineEdit()
        self.host = QLineEdit(); self.host.setPlaceholderText("http://server:port")
        self.user = QLineEdit()
        self.pw = QLineEdit(); self.pw.setEchoMode(QLineEdit.Password)
        form.addRow("Name", self.name)
        form.addRow("Host", self.host)
        form.addRow("Username", self.user)
        form.addRow("Password", self.pw)
        root.addLayout(form)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#e06c75;")
        root.addWidget(self.status)

        btns = QHBoxLayout()
        btns.addStretch()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setDefault(True)
        self.connect_btn.clicked.connect(self._on_connect)
        btns.addWidget(self.connect_btn)
        root.addLayout(btns)

    def _on_select(self, idx):
        p = self.combo.currentData()
        if p:
            self.name.setText(p.get("name", ""))
            self.host.setText(p.get("host", ""))
            self.user.setText(p.get("username", ""))
            self.pw.setText(p.get("password", ""))

    def _on_connect(self):
        host = self.host.text().strip()
        user = self.user.text().strip()
        pw = self.pw.text().strip()
        name = self.name.text().strip() or host
        if not (host and user and pw):
            self.status.setText("Host, username and password are required.")
            return
        self.connect_btn.setEnabled(False)
        self.status.setStyleSheet("color:#999;")
        self.status.setText("Connecting…")
        self.repaint()

        client = XtreamClient(host, user, pw)
        info = client.authenticate()
        if not info:
            self.connect_btn.setEnabled(True)
            self.status.setStyleSheet("color:#e06c75;")
            self.status.setText("Authentication failed. Check credentials/host.")
            return

        profile = {"name": name, "host": client.host, "username": user, "password": pw}
        # persist (replace by name)
        self._profiles = [p for p in self._profiles if p.get("name") != name]
        self._profiles.append(profile)
        config.save_profiles(self._profiles)
        self.profile = profile
        self.client = client
        self.accept()
