"""Sources & settings menu — lets any user wire up their own content.

A tabbed dialog covering every content source the media centre understands,
with nothing hard-coded: local/network folders, IPTV (Xtream) profiles, Emby
and Plex servers, plus the optional TMDb/OMDb metadata keys. Persisted via
config.save_media_config() and config.save_profiles().

Closing with "Save & Scan" tells the caller to (re)scan the local library.
"""
from PySide6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QListWidget, QLabel, QFileDialog, QInputDialog,
    QDialogButtonBox, QMessageBox,
)
from PySide6.QtCore import Qt

from iptv import config
from ui.login_dialog import LoginDialog


class SourcesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QPlayer — Sources & Settings")
        self.setMinimumSize(620, 520)
        self.scan_requested = False
        self._cfg = config.media_config()

        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._folders_tab(), "📁  Folders")
        self.tabs.addTab(self._iptv_tab(), "📺  IPTV")
        self.tabs.addTab(self._servers_tab(), "🖥  Emby / Plex")
        self.tabs.addTab(self._metadata_tab(), "⭐  Metadata")
        root.addWidget(self.tabs, 1)

        bb = QDialogButtonBox()
        self.btn_scan = bb.addButton("Save && Scan library", QDialogButtonBox.AcceptRole)
        btn_save = bb.addButton("Save", QDialogButtonBox.ApplyRole)
        btn_close = bb.addButton(QDialogButtonBox.Close)
        self.btn_scan.clicked.connect(lambda: self._save(scan=True))
        btn_save.clicked.connect(lambda: self._save(scan=False))
        btn_close.clicked.connect(self.reject)
        root.addWidget(bb)

    # ---- Folders ------------------------------------------------------
    def _folders_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(QLabel("Local and network folders to scan into your library "
                           "(video, music, photos):"))
        self.folder_list = QListWidget()
        self.folder_list.addItems(self._cfg.get("library_paths", []))
        v.addWidget(self.folder_list, 1)
        row = QHBoxLayout()
        b_add = QPushButton("Add folder…"); b_add.clicked.connect(self._add_folder)
        b_net = QPushButton("Add network path…"); b_net.clicked.connect(self._add_network)
        b_del = QPushButton("Remove"); b_del.clicked.connect(self._remove_folder)
        row.addWidget(b_add); row.addWidget(b_net); row.addWidget(b_del); row.addStretch()
        v.addLayout(row)
        hint = QLabel("Network shares must be mounted (NFS/SMB) — add the mount "
                      "point, e.g. /mnt/media or /run/user/1000/gvfs/…")
        hint.setObjectName("Meta"); hint.setWordWrap(True)
        v.addWidget(hint)
        return w

    def _add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select media folder")
        if d and not self._has_folder(d):
            self.folder_list.addItem(d)

    def _add_network(self):
        path, ok = QInputDialog.getText(
            self, "Add network path",
            "Mounted share path (e.g. /mnt/nfs/movies):")
        path = (path or "").strip()
        if ok and path and not self._has_folder(path):
            self.folder_list.addItem(path)

    def _remove_folder(self):
        for it in self.folder_list.selectedItems():
            self.folder_list.takeItem(self.folder_list.row(it))

    def _has_folder(self, p):
        return any(self.folder_list.item(i).text() == p
                   for i in range(self.folder_list.count()))

    # ---- IPTV ---------------------------------------------------------
    def _iptv_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(QLabel("Xtream Codes IPTV accounts:"))
        self.iptv_list = QListWidget()
        self._reload_iptv()
        v.addWidget(self.iptv_list, 1)
        row = QHBoxLayout()
        b_add = QPushButton("Add IPTV account…"); b_add.clicked.connect(self._add_iptv)
        b_del = QPushButton("Remove"); b_del.clicked.connect(self._remove_iptv)
        row.addWidget(b_add); row.addWidget(b_del); row.addStretch()
        v.addLayout(row)
        return w

    def _reload_iptv(self):
        self.iptv_list.clear()
        for p in config.load_profiles():
            self.iptv_list.addItem(p.get("name", p.get("host", "?")))

    def _add_iptv(self):
        dlg = LoginDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._reload_iptv()

    def _remove_iptv(self):
        it = self.iptv_list.currentItem()
        if not it:
            return
        name = it.text()
        profiles = [p for p in config.load_profiles() if p.get("name") != name]
        config.save_profiles(profiles)
        self._reload_iptv()

    # ---- Emby / Plex --------------------------------------------------
    def _servers_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        emby = self._cfg.get("emby", {})
        plex = self._cfg.get("plex", {})

        v.addWidget(QLabel("<b>Emby / Jellyfin</b>"))
        ef = QFormLayout()
        self.emby_url = QLineEdit(emby.get("url", "")); self.emby_url.setPlaceholderText("http://host:8096")
        self.emby_key = QLineEdit(emby.get("api_key", "")); self.emby_key.setEchoMode(QLineEdit.Password)
        self.emby_user = QLineEdit(emby.get("user_id", ""))
        ef.addRow("Server URL", self.emby_url)
        ef.addRow("API key", self.emby_key)
        ef.addRow("User ID", self.emby_user)
        v.addLayout(ef)

        v.addSpacing(12)
        v.addWidget(QLabel("<b>Plex</b>"))
        pf = QFormLayout()
        self.plex_url = QLineEdit(plex.get("url", "")); self.plex_url.setPlaceholderText("http://host:32400")
        self.plex_token = QLineEdit(plex.get("token", "")); self.plex_token.setEchoMode(QLineEdit.Password)
        pf.addRow("Server URL", self.plex_url)
        pf.addRow("X-Plex-Token", self.plex_token)
        v.addLayout(pf)
        v.addStretch()
        return w

    # ---- Metadata -----------------------------------------------------
    def _metadata_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(QLabel("Optional API keys for posters, overviews and IMDb "
                           "ratings. The library works without them — you just "
                           "won't get artwork or ratings."))
        f = QFormLayout()
        self.tmdb_key = QLineEdit(self._cfg.get("tmdb_key", ""))
        self.omdb_key = QLineEdit(self._cfg.get("omdb_key", ""))
        f.addRow("TMDb API key", self.tmdb_key)
        f.addRow("OMDb API key", self.omdb_key)
        v.addLayout(f)
        links = QLabel(
            'Free keys: <a href="https://www.themoviedb.org/settings/api">TMDb</a> '
            '(posters + metadata) · '
            '<a href="https://www.omdbapi.com/apikey.aspx">OMDb</a> (IMDb rating)')
        links.setObjectName("Meta"); links.setOpenExternalLinks(True); links.setWordWrap(True)
        v.addWidget(links)
        v.addStretch()
        return w

    # ---- save ---------------------------------------------------------
    def _collect(self):
        paths = [self.folder_list.item(i).text()
                 for i in range(self.folder_list.count())]
        return {
            "library_paths": paths,
            "tmdb_key": self.tmdb_key.text().strip(),
            "omdb_key": self.omdb_key.text().strip(),
            "emby": {"url": self.emby_url.text().strip(),
                     "api_key": self.emby_key.text().strip(),
                     "user_id": self.emby_user.text().strip()},
            "plex": {"url": self.plex_url.text().strip(),
                     "token": self.plex_token.text().strip()},
        }

    def _save(self, scan=False):
        config.save_media_config(self._collect())
        self.scan_requested = scan
        if scan:
            self.accept()
        else:
            QMessageBox.information(self, "Saved", "Settings saved.")
