"""Main window: Live TV / Movies / Series with poster grid, info card and player."""
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLineEdit, QLabel, QSlider, QSplitter, QMessageBox,
    QProgressBar, QFrame, QScrollArea, QSizePolicy, QStackedWidget, QComboBox,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer, QEvent, QByteArray
from PySide6.QtGui import QPixmap, QIcon, QShortcut, QKeySequence, QPainter
from PySide6.QtSvg import QSvgRenderer

from iptv import config
from iptv.mpv_widget import MpvWidget
from iptv.downloader import DownloadManager
from iptv.image_loader import ImageLoader
from ui.style import build_qss, desktop_accent
from ui.sources_dialog import SourcesDialog
from media.library_db import LibraryDB
from media.metadata import MetadataProvider
from media.local_scanner import LibraryScanner
from media.imdb_ratings import ImdbRatings

ROLE = Qt.UserRole
POSTER = QSize(132, 198)

_EMBY_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="50" fill="#52B54B"/>
  <polygon points="35,25 35,75 80,50" fill="white"/>
</svg>"""

_PLEX_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" rx="14" fill="#1F1F1F"/>
  <polygon points="35,25 35,75 80,50" fill="#E5A00D"/>
</svg>"""

_MYMEDIA_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect x="4" y="12" width="92" height="62" rx="7" fill="#546E7A"/>
  <rect x="12" y="20" width="76" height="46" rx="4" fill="#263238"/>
  <polygon points="38,31 38,57 66,44" fill="white" opacity="0.9"/>
  <rect x="37" y="74" width="26" height="7" rx="2" fill="#546E7A"/>
  <rect x="27" y="81" width="46" height="7" rx="3" fill="#546E7A"/>
</svg>"""

_IPTV_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect x="5" y="16" width="90" height="58" rx="7" fill="#37474F"/>
  <rect x="13" y="24" width="74" height="42" rx="4" fill="#0D47A1"/>
  <line x1="34" y1="16" x2="18" y2="4" stroke="#37474F" stroke-width="8" stroke-linecap="round"/>
  <line x1="66" y1="16" x2="82" y2="4" stroke="#37474F" stroke-width="8" stroke-linecap="round"/>
  <rect x="40" y="74" width="20" height="8" rx="2" fill="#37474F"/>
  <rect x="30" y="82" width="40" height="7" rx="3" fill="#37474F"/>
</svg>"""


class Worker(QThread):
    done = Signal(object)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            self.done.emit(self._fn())
        except Exception as e:
            self.done.emit(e)


class SeekSlider(QSlider):
    """Horizontal slider that jumps to the clicked position (click-to-seek)
    instead of stepping a page, then emits sliderReleased to trigger the seek."""

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.maximum() > self.minimum():
            x = ev.position().x() if hasattr(ev, "position") else ev.x()
            span = self.maximum() - self.minimum()
            val = self.minimum() + round(span * max(0.0, min(1.0, x / max(1, self.width()))))
            self.setValue(int(val))
            ev.accept()
            self.sliderReleased.emit()
            return
        super().mousePressEvent(ev)


class MainWindow(QMainWindow):
    def __init__(self, profile, client):
        super().__init__()
        self.profile = profile
        self.client = client
        self.settings = config.load_settings()
        self.images = ImageLoader(self)
        self.mode = "live"
        self.category_id = None
        self.viewing_series = None
        self._all_streams = {}          # mode -> full catalog (cached for name search)
        self._workers = []
        self._fs = False
        self._lib_source = None
        self.mpris = None
        self.inhibitor = None

        self.downloads = DownloadManager(
            self.settings.get("download_dir") or config.download_dir(), self)
        self.downloads.started.connect(self._on_dl_started)
        self.downloads.progress.connect(self._on_dl_progress)
        self.downloads.finished_ok.connect(self._on_dl_done)
        self.downloads.failed.connect(self._on_dl_failed)

        # media-center backend: local library DB + metadata + scanner
        self.db = LibraryDB()
        self.imdb = ImdbRatings()      # official IMDb ratings dataset (downloaded on scan)
        mc = config.media_config()
        self.meta = MetadataProvider(self.db, mc.get("tmdb_key"), mc.get("omdb_key"),
                                     imdb=self.imdb)
        self.scanner = LibraryScanner(self.db, self.meta)
        self._scanning = False

        self.accent = desktop_accent()
        self.setStyleSheet(build_qss(self.accent))
        self.setWindowTitle(f"QMediaCenter — {profile['name']}")
        self.resize(1320, 820)
        self._build_ui()
        self._show_home()

    # ---- UI ------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(8, 8, 8, 8)

        # Navigation stays visible; the selections themselves are separate pages.
        self.nav_bar = QWidget()
        nav = QHBoxLayout(self.nav_bar)
        nav.setContentsMargins(4, 4, 4, 4)
        self.btn_home = QPushButton("🏠 Home"); self.btn_home.setCheckable(True)
        self.btn_home.clicked.connect(self._show_home)
        nav.addWidget(self.btn_home)
        self.btn_mymedia = QPushButton(" MyMedia"); self.btn_mymedia.setCheckable(True)
        self.btn_mymedia.setIcon(self._svg_icon(_MYMEDIA_SVG, 18))
        self.btn_mymedia.setIconSize(QSize(18, 18))
        self.btn_mymedia.clicked.connect(self._show_mymedia)
        nav.addWidget(self.btn_mymedia)
        self.btn_emby = QPushButton(" Emby"); self.btn_emby.setCheckable(True)
        self.btn_emby.setIcon(self._svg_icon(_EMBY_SVG, 18))
        self.btn_emby.setIconSize(QSize(18, 18))
        self.btn_emby.clicked.connect(self._show_emby)
        nav.addWidget(self.btn_emby)
        self.btn_plex = QPushButton(" Plex"); self.btn_plex.setCheckable(True)
        self.btn_plex.setIcon(self._svg_icon(_PLEX_SVG, 18))
        self.btn_plex.setIconSize(QSize(18, 18))
        self.btn_plex.clicked.connect(self._show_plex)
        nav.addWidget(self.btn_plex)
        self.btn_iptv = QPushButton(" IPTV"); self.btn_iptv.setCheckable(True)
        self.btn_iptv.setIcon(self._svg_icon(_IPTV_SVG, 18))
        self.btn_iptv.setIconSize(QSize(18, 18))
        self.btn_iptv.clicked.connect(self._show_iptv)
        nav.addWidget(self.btn_iptv)
        nav.addStretch()
        self.btn_sources = QPushButton("⚙ Sources")
        self.btn_sources.clicked.connect(self._open_sources)
        nav.addWidget(self.btn_sources)
        outer.addWidget(self.nav_bar)

        # IPTV sub-navigation — shown only when IPTV is active
        self.iptv_subnav = QWidget()
        iptv_sub = QHBoxLayout(self.iptv_subnav)
        iptv_sub.setContentsMargins(20, 2, 4, 2)
        iptv_name_lbl = QLabel(f"● {self.profile['name']}")
        iptv_name_lbl.setObjectName("Meta")
        iptv_sub.addWidget(iptv_name_lbl)
        self.btn_live = QPushButton("📡 Live")
        self.btn_vod = QPushButton("🎬 Movies")
        self.btn_series = QPushButton("📺 Series")
        for b, m in ((self.btn_live, "live"), (self.btn_vod, "vod"), (self.btn_series, "series")):
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, mm=m: self._set_mode(mm))
            iptv_sub.addWidget(b)
        self.btn_downloads = QPushButton("⬇ Downloads"); self.btn_downloads.setCheckable(True)
        self.btn_downloads.clicked.connect(self._show_downloads)
        iptv_sub.addWidget(self.btn_downloads)
        iptv_sub.addStretch()
        self.iptv_subnav.setVisible(False)
        outer.addWidget(self.iptv_subnav)

        self.pages = QStackedWidget()
        outer.addWidget(self.pages, 1)

        # --- categories page ---
        self.left = QWidget()
        lv = QVBoxLayout(self.left)
        lv.setContentsMargins(4, 4, 4, 4)
        hdr = QLabel("Categories"); hdr.setObjectName("Header")
        lv.addWidget(hdr)
        self.cat_search = QLineEdit(); self.cat_search.setPlaceholderText("Filter categories…")
        self.cat_search.textChanged.connect(self._on_cat_search)
        lv.addWidget(self.cat_search)
        self.cat_list = QListWidget()
        self.cat_list.currentItemChanged.connect(self._on_category)
        lv.addWidget(self.cat_list)
        self.pages.addWidget(self.left)

        # --- content page (poster grid / list) ---
        self.center = QWidget()
        cv = QVBoxLayout(self.center)
        cv.setContentsMargins(4, 4, 4, 4)
        content_top = QHBoxLayout()
        self.btn_categories = QPushButton("←  Categories")
        self.btn_categories.clicked.connect(self._content_back)
        content_top.addWidget(self.btn_categories)
        self.content_header = QLabel("Content"); self.content_header.setObjectName("Header")
        content_top.addWidget(self.content_header)
        content_top.addStretch()
        cv.addLayout(content_top)
        self.content_search = QLineEdit(); self.content_search.setPlaceholderText("Search…")
        self.content_search.textChanged.connect(lambda t: self._filter(self.content_list, t))
        cv.addWidget(self.content_search)
        self.content_list = QListWidget()
        self.content_list.setObjectName("Grid")
        self.content_list.setUniformItemSizes(True)
        self.content_list.currentItemChanged.connect(self._on_content_selected)
        self.content_list.itemActivated.connect(self._on_content_activated)
        cv.addWidget(self.content_list)
        self.pages.addWidget(self.center)

        # --- watch page: info card (top) + player (bottom) ---
        self.watch_page = QWidget()
        watch_layout = QVBoxLayout(self.watch_page)
        watch_layout.setContentsMargins(4, 4, 4, 4)
        self.watch_layout = watch_layout
        self.btn_content = QPushButton("←  Content")
        self.btn_content.clicked.connect(self._on_back)
        watch_layout.addWidget(self.btn_content, 0, Qt.AlignLeft)
        self.right = QSplitter(Qt.Vertical)
        self.info_card = self._build_info_card()
        self.right.addWidget(self.info_card)

        player_box = QWidget()
        pv = QVBoxLayout(player_box)
        pv.setContentsMargins(0, 0, 0, 0)
        self.player = MpvWidget()
        self.player.setMinimumHeight(220)
        self.player.setMouseTracking(True)       # get MouseMove without a pressed button
        self.player.position_changed.connect(self._on_position)
        self.player.duration_changed.connect(self._on_duration)
        self.player.pause_changed.connect(self._on_pause_changed)
        self.player.installEventFilter(self)
        self.player.info_changed.connect(self._on_player_info)
        self.player.tracks_changed.connect(self._on_tracks_changed)
        pv.addWidget(self.player, 1)
        # Controls overlay the video (pinned to the bottom of the player surface),
        # so they can fade away in fullscreen and re-appear on mouse movement.
        self.controls_bar = self._build_controls()
        self.controls_bar.setParent(self.player)
        self.controls_bar.setMouseTracking(True)
        self.controls_bar.installEventFilter(self)
        self._controls_timer = QTimer(self)
        self._controls_timer.setSingleShot(True)
        self._controls_timer.setInterval(2500)
        self._controls_timer.timeout.connect(self._hide_controls)
        self._base_title = f"QMediaCenter — {self.profile['name']}"
        self.right.addWidget(player_box)
        self.right.setSizes([300, 500])
        watch_layout.addWidget(self.right, 1)
        self.pages.addWidget(self.watch_page)

        # --- library page: scanned local/network media as a poster grid ---
        self.library_page = self._build_library_page()
        self.pages.addWidget(self.library_page)

        # --- home page: rows (Continue Watching / Favorites / Recently Added) ---
        self.home_page = self._build_home_page()
        self.pages.addWidget(self.home_page)

        # --- detail page: info card for a library/home item, with Play ---
        self.detail_page = self._build_detail_page()
        self.pages.addWidget(self.detail_page)
        self._detail_item = None
        self._detail_return = self.home_page

        # --- downloads page: one row per download with progress + speed ---
        self._dl_widgets = {}          # id -> {row, bar, speed, status, stop}
        self.downloads_page = self._build_downloads_page()
        self.pages.addWidget(self.downloads_page)

        self._duration = 0
        self._current_key = None
        self._current_title = ""
        self._current_url = ""
        self._current_poster = ""
        self._current_kind = "movie"
        self._resume_target = 0.0
        self._last_save = 0.0
        self.player.set_volume(self.vol.value())

        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._exit_fullscreen)
        QShortcut(QKeySequence(Qt.Key_F), self, activated=self._toggle_fullscreen)
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.player.toggle_pause)

    def _build_info_card(self):
        card = QFrame(); card.setObjectName("InfoCard")
        h = QHBoxLayout(card)
        self.info_poster = QLabel()
        self.info_poster.setFixedSize(150, 225)
        self.info_poster.setScaledContents(True)
        self.info_poster.setStyleSheet("border-radius:8px; background:#e0e3e6;")
        h.addWidget(self.info_poster)

        right = QVBoxLayout()
        self.info_title = QLabel("Select something to watch"); self.info_title.setObjectName("Title")
        self.info_title.setWordWrap(True)
        right.addWidget(self.info_title)
        self.info_meta = QLabel(""); self.info_meta.setObjectName("Meta")
        self.info_meta.setWordWrap(True)
        right.addWidget(self.info_meta)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        self.info_plot = QLabel(""); self.info_plot.setObjectName("Plot")
        self.info_plot.setWordWrap(True); self.info_plot.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.info_plot)
        right.addWidget(scroll, 1)

        btns = QHBoxLayout()
        self.btn_play_info = QPushButton("▶  Play")
        self.btn_play_info.clicked.connect(lambda: self._on_content_activated(self.content_list.currentItem()))
        self.btn_dl_info = QPushButton("⬇  Download")
        self.btn_dl_info.clicked.connect(self._download_selected)
        self.btn_back_info = QPushButton("←  Back")
        self.btn_back_info.clicked.connect(self._on_back)
        btns.addWidget(self.btn_play_info); btns.addWidget(self.btn_dl_info)
        btns.addWidget(self.btn_back_info); btns.addStretch()
        right.addLayout(btns)
        h.addLayout(right, 1)
        return card

    # ---- library (own scanned media) ----------------------------------
    def _build_library_page(self):
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(4, 4, 4, 4)
        top = QHBoxLayout()
        self.lib_header = QLabel("Library"); self.lib_header.setObjectName("Header")
        top.addWidget(self.lib_header)
        top.addStretch()
        self.lib_kind = QComboBox()
        self.lib_kind.addItem("🎬 Movies", "movie")
        self.lib_kind.addItem("📺 TV", "episode")
        self.lib_kind.addItem("🎵 Music", "music")
        self.lib_kind.addItem("🖼 Photos", "photo")
        self.lib_kind.currentIndexChanged.connect(self._populate_library)
        top.addWidget(self.lib_kind)
        self.btn_scan = QPushButton("↻ Scan"); self.btn_scan.clicked.connect(self._start_scan)
        top.addWidget(self.btn_scan)
        v.addLayout(top)
        self.lib_search = QLineEdit(); self.lib_search.setPlaceholderText("Filter library…")
        self.lib_search.textChanged.connect(lambda t: self._filter(self.lib_list, t))
        v.addWidget(self.lib_search)
        self.lib_list = QListWidget(); self.lib_list.setObjectName("Grid")
        self.lib_list.setViewMode(QListWidget.IconMode)
        self.lib_list.setIconSize(POSTER)
        self.lib_list.setGridSize(QSize(POSTER.width() + 24, POSTER.height() + 52))
        self.lib_list.setResizeMode(QListWidget.Adjust)
        self.lib_list.setMovement(QListWidget.Static)
        self.lib_list.setUniformItemSizes(True)
        self.lib_list.setWordWrap(True)
        self.lib_list.itemClicked.connect(self._show_detail)        # single click -> info
        self.lib_list.itemActivated.connect(self._on_library_activated)  # double click -> play
        v.addWidget(self.lib_list, 1)
        return page

    def _nav_select(self, active_btn):
        for b in (self.btn_home, self.btn_mymedia, self.btn_iptv,
                  self.btn_emby, self.btn_plex, self.btn_downloads):
            b.setChecked(b is active_btn)
        self.iptv_subnav.setVisible(active_btn in (self.btn_iptv, self.btn_downloads))

    def _show_mymedia(self):
        self._nav_select(self.btn_mymedia)
        self.pages.setCurrentWidget(self.library_page)
        self._populate_library(source="local")

    def _show_emby(self):
        self._nav_select(self.btn_emby)
        self.pages.setCurrentWidget(self.library_page)
        self._populate_library(source="emby")

    def _show_plex(self):
        self._nav_select(self.btn_plex)
        self.pages.setCurrentWidget(self.library_page)
        self._populate_library(source="plex")

    def _show_iptv(self):
        self._nav_select(self.btn_iptv)
        if self.mode not in ("live", "vod", "series"):
            self.mode = "live"
        self._set_mode(self.mode)

    def _populate_library(self, source=None):
        if source is not None:
            self._lib_source = source
        source = getattr(self, "_lib_source", None)
        kind = self.lib_kind.currentData()
        items = self.db.media(kind=kind, source=source, order="title")
        self.lib_list.clear()
        src_names = {"local": "MyMedia", "emby": "Emby", "plex": "Plex"}
        hdr = src_names.get(source, "Library") if source else "Library"
        self.lib_header.setText(f"{hdr} — {len(items)} items")
        for d in items:
            label = d.get("title") or "?"
            if d.get("year"):
                label += f"  ({d['year']})"
            if d.get("rating"):
                label += f"  ⭐{d['rating']:.1f}"
            it = QListWidgetItem(label)
            it.setData(ROLE, d)
            it.setSizeHint(QSize(POSTER.width() + 24, POSTER.height() + 52))
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            poster = d.get("poster")
            if poster:
                if poster.startswith(("http://", "https://")):
                    self._load_poster(it, poster)
                elif os.path.exists(poster):
                    it.setIcon(QIcon(QPixmap(poster)))
            self.lib_list.addItem(it)

    def _on_library_activated(self, item):
        if not item:
            return
        d = item.data(ROLE)
        if d.get("kind") == "photo":
            return  # photo viewer comes later
        self._play(d.get("path"), d.get("title"), item_key=d.get("item_key"))

    def _open_sources(self):
        dlg = SourcesDialog(self)
        dlg.exec()
        # apply possibly-changed metadata keys live
        mc = config.media_config()
        self.meta = MetadataProvider(self.db, mc.get("tmdb_key"), mc.get("omdb_key"),
                                     imdb=self.imdb)
        self.scanner = LibraryScanner(self.db, self.meta)
        if dlg.scan_requested:
            self._start_scan()

    def _start_scan(self):
        if self._scanning:
            return
        mc = config.media_config()
        paths = mc.get("library_paths", [])
        emby_cfg = mc.get("emby", {})
        plex_cfg = mc.get("plex", {})
        has_emby = bool(emby_cfg.get("url") and emby_cfg.get("api_key"))
        has_plex = bool(plex_cfg.get("url") and plex_cfg.get("token"))
        if not paths and not has_emby and not has_plex:
            QMessageBox.information(self, "No sources",
                                   "Add folders, an Emby or a Plex server first via ⚙ Sources.")
            return
        self._scanning = True
        # When a TMDb key is set, refresh the official IMDb ratings dataset first
        # (downloads ~25 MB the first time / weekly), then scan — both off-thread.
        need_imdb = bool(mc.get("tmdb_key")) and not self.imdb.is_fresh()
        self.lib_header.setText("Updating IMDb ratings…" if need_imdb else "Scanning…")
        self.btn_scan.setEnabled(False)

        def job():
            if need_imdb:
                self.imdb.ensure()
            result = self.scanner.scan(paths) if paths else (0, 0)
            if has_emby:
                from media.emby import sync_emby
                sync_emby(self.db, emby_cfg)
            if has_plex:
                from media.plex import sync_plex
                sync_plex(self.db, plex_cfg)
            return result

        worker = Worker(job, self)
        worker.done.connect(self._on_scan_done)
        worker.done.connect(lambda _=None, w=worker:
                            self._workers.remove(w) if w in self._workers else None)
        self._workers.append(worker)
        worker.start()

    def _on_scan_done(self, result):
        self._scanning = False
        self.btn_scan.setEnabled(True)
        if isinstance(result, Exception):
            QMessageBox.warning(self, "Scan failed", str(result))
        self._populate_library()

    # ---- home (rowed landing page) ------------------------------------
    def _build_home_page(self):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setObjectName("HomeScroll"); scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        self.home_vbox = QVBoxLayout(container)
        self.home_vbox.setContentsMargins(8, 8, 8, 8)
        self.home_vbox.setSpacing(6)
        scroll.setWidget(container)
        return scroll

    def _show_home(self):
        self._nav_select(self.btn_home)
        self.pages.setCurrentWidget(self.home_page)
        self._populate_home()

    def _populate_home(self):
        # clear previous rows
        while self.home_vbox.count():
            it = self.home_vbox.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        from collections import defaultdict
        all_movies = self.db.media(kind="movie", limit=40)
        movies_by_src = defaultdict(list)
        for item in all_movies:
            movies_by_src[item.get("source", "local")].append(item)
        src_names = {"local": "MyMedia", "emby": "Emby", "plex": "Plex"}

        rows = [
            ("▶  Continue Watching", self.db.continue_watching(20)),
            ("⭐  Favorites", self.db.favorites(40)),
            ("🆕  Recently Added", self.db.media(order="recent", limit=40)),
        ]
        for src, items in movies_by_src.items():
            rows.append((f"🎬  Movies — {src_names.get(src, src.title())}", items))
        rows.append(("📺  TV", self.db.media(kind="episode", limit=40)))

        any_row = False
        for title, items in rows:
            if items:
                any_row = True
                self.home_vbox.addWidget(self._home_row(title, items))
        if not any_row:
            hint = QLabel("Your home screen fills up as you add content.\n"
                          "Add folders via ⚙ Sources, scan your library, and start watching.")
            hint.setObjectName("Meta"); hint.setAlignment(Qt.AlignCenter)
            self.home_vbox.addWidget(hint)
        self.home_vbox.addStretch()

    def _home_row(self, title, items):
        box = QWidget(); v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0); v.setSpacing(2)
        lbl = QLabel(title); lbl.setObjectName("Header")
        v.addWidget(lbl)
        strip = QListWidget(); strip.setObjectName("Strip")
        strip.setViewMode(QListWidget.IconMode)
        strip.setFlow(QListWidget.LeftToRight)
        strip.setWrapping(False)
        strip.setMovement(QListWidget.Static)
        strip.setIconSize(POSTER)
        strip.setFixedHeight(POSTER.height() + 54)
        strip.setHorizontalScrollMode(QListWidget.ScrollPerPixel)
        strip.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        strip.setUniformItemSizes(True)
        strip.setWordWrap(True)
        _src_badge = {"emby": " [Emby]", "plex": " [Plex]", "xtream": " [IPTV]"}
        for d in items:
            label = d.get("title") or "?"
            extra = d.get("extra") or {}
            src = d.get("source", "")
            if src and src != "local":
                label += _src_badge.get(src, f" [{src.title()}]")
            if d.get("year"):
                label += f"  ({d['year']})"
            pos, dur = (d.get("position"), d.get("duration"))
            if pos and dur:
                label = f"%{int(pos / dur * 100)} · " + label
            elif d.get("rating"):
                label += f"  ⭐{d['rating']:.1f}"
            it = QListWidgetItem(label)
            it.setData(ROLE, d)
            it.setSizeHint(QSize(POSTER.width() + 18, POSTER.height() + 50))
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            poster = d.get("poster")
            if poster and poster.startswith(("http://", "https://")):
                self._load_poster(it, poster)
            elif poster and os.path.exists(poster):
                it.setIcon(QIcon(QPixmap(poster)))
            strip.addItem(it)
        strip.itemClicked.connect(self._show_detail)        # single click -> info card
        v.addWidget(strip)
        return box

    @staticmethod
    def _svg_icon(svg_bytes: bytes, size: int = 24) -> QIcon:
        renderer = QSvgRenderer(QByteArray(svg_bytes))
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        renderer.render(painter)
        painter.end()
        return QIcon(pm)

    @staticmethod
    def _track_pill(icon_text, combo):
        pill = QFrame(); pill.setObjectName("TrackPill")
        h = QHBoxLayout(pill)
        h.setContentsMargins(8, 0, 6, 0); h.setSpacing(2)
        lbl = QLabel(icon_text); lbl.setObjectName("TrackIcon")
        h.addWidget(lbl); h.addWidget(combo)
        return pill

    def _build_controls(self):
        bar = QWidget()
        bar.setObjectName("ControlsBar")
        ctl = QHBoxLayout(bar)
        ctl.setContentsMargins(10, 6, 10, 6); ctl.setSpacing(6)

        self.btn_play = QPushButton("▶"); self.btn_play.setObjectName("Transport")
        self.btn_play.setToolTip("Play")
        self.btn_play.clicked.connect(lambda: self.player.set_pause(False))
        self.btn_pause = QPushButton("⏸"); self.btn_pause.setObjectName("Transport")
        self.btn_pause.setToolTip("Pause")
        self.btn_pause.clicked.connect(lambda: self.player.set_pause(True))
        self.btn_stop = QPushButton("⏹"); self.btn_stop.setObjectName("Transport")
        self.btn_stop.setToolTip("Stop")
        self.btn_stop.clicked.connect(self._stop_playback)
        ctl.addWidget(self.btn_play); ctl.addWidget(self.btn_pause); ctl.addWidget(self.btn_stop)

        self.pos_slider = SeekSlider(Qt.Horizontal); self.pos_slider.setRange(0, 1000)
        self.pos_slider.sliderReleased.connect(self._seek)
        ctl.addWidget(self.pos_slider, 1)

        self.time_lbl = QLabel("00:00 / 00:00"); self.time_lbl.setObjectName("TimeLabel")
        ctl.addWidget(self.time_lbl)

        self.audio_combo = QComboBox(); self.audio_combo.setObjectName("TrackCombo")
        self.audio_combo.setToolTip("Audio track"); self.audio_combo.setMinimumWidth(110)
        self.audio_combo.setMaximumWidth(160); self.audio_combo.activated.connect(self._on_audio_pick)
        ctl.addWidget(self._track_pill("🔉", self.audio_combo))

        self.sub_combo = QComboBox(); self.sub_combo.setObjectName("TrackCombo")
        self.sub_combo.setToolTip("Subtitles"); self.sub_combo.setMinimumWidth(110)
        self.sub_combo.setMaximumWidth(160); self.sub_combo.activated.connect(self._on_sub_pick)
        ctl.addWidget(self._track_pill("💬", self.sub_combo))

        vol_pill = QFrame(); vol_pill.setObjectName("TrackPill")
        vh = QHBoxLayout(vol_pill); vh.setContentsMargins(8, 0, 8, 0); vh.setSpacing(6)
        vh.addWidget(QLabel("🔊"))
        self.vol = QSlider(Qt.Horizontal); self.vol.setRange(0, 150); self.vol.setFixedWidth(90)
        self.vol.setValue(self.settings.get("volume", 100))
        self.vol.valueChanged.connect(self._set_volume)
        vh.addWidget(self.vol)
        ctl.addWidget(vol_pill)

        self.btn_fs = QPushButton("⛶"); self.btn_fs.setObjectName("Transport")
        self.btn_fs.setToolTip("Fullscreen")
        self.btn_fs.clicked.connect(self._toggle_fullscreen)
        ctl.addWidget(self.btn_fs)
        return bar

    # ---- mode / categories --------------------------------------------
    def _set_mode(self, mode):
        self.mode = mode
        self.viewing_series = None
        self._nav_select(self.btn_iptv)
        for b, m in ((self.btn_live, "live"), (self.btn_vod, "vod"), (self.btn_series, "series")):
            b.setChecked(m == mode)
        grid = mode in ("vod", "series")
        self.content_list.setViewMode(QListWidget.IconMode if grid else QListWidget.ListMode)
        self.content_list.setIconSize(POSTER if grid else QSize(0, 0))
        self.content_list.setGridSize(QSize(POSTER.width() + 24, POSTER.height() + 52) if grid else QSize())
        self.content_list.setWordWrap(grid)
        self.content_list.setMovement(QListWidget.Static)
        self.btn_dl_info.setEnabled(mode in ("vod", "series"))
        self.cat_search.blockSignals(True)
        self.cat_search.clear()
        self.cat_search.setPlaceholderText(
            {"live": "Search channels…", "vod": "Search movies…",
             "series": "Search series…"}.get(mode, "Search…"))
        self.cat_search.blockSignals(False)
        self.cat_list.clear(); self.content_list.clear()
        self.pages.setCurrentWidget(self.left)
        self.content_header.setText("Loading categories…")
        fetch = {"live": self.client.live_categories,
                 "vod": self.client.vod_categories,
                 "series": self.client.series_categories}[mode]
        self._run(fetch, self._populate_categories)

    def _populate_categories(self, cats):
        self.cat_list.clear()
        if isinstance(cats, Exception) or not cats:
            self.content_header.setText("No categories"); return
        for c in cats:
            it = QListWidgetItem(c.get("category_name", "?"))
            it.setData(ROLE, c.get("category_id"))
            self.cat_list.addItem(it)
        self.content_header.setText("Select a category")

    # ---- name search (live/vod/series) -----------------------------------
    def _on_cat_search(self, text):
        text = text.strip()
        if not text:
            self.pages.setCurrentWidget(self.left)
            return
        cached = self._all_streams.get(self.mode)
        if cached is not None:
            self._apply_search(cached, text)
            return
        self.content_list.clear()
        self.content_header.setText("Loading catalog…")
        self.pages.setCurrentWidget(self.center)
        if self.mode == "live":
            self._run(self.client.live_streams, self._cache_and_search)
        elif self.mode == "vod":
            self._run(self.client.vod_streams, self._cache_and_search)
        else:
            self._run(self.client.series, self._cache_and_search)

    def _cache_and_search(self, items):
        if isinstance(items, Exception) or not items:
            items = []
        self._all_streams[self.mode] = items
        q = self.cat_search.text().strip()
        if q:
            self._apply_search(items, q)

    def _apply_search(self, items, text):
        q = text.lower()
        matched = [d for d in items
                   if q in (d.get("name") or d.get("title") or "").lower()]
        self._populate_content(matched)
        self.content_header.setText(
            f"{len(matched)} result(s) · “{text}”" if matched
            else f"No results · “{text}”")
        self.pages.setCurrentWidget(self.center)

    def _on_category(self, item, _prev=None):
        if not item:
            return
        self.category_id = item.data(ROLE)
        self.viewing_series = None
        self.content_list.clear()
        self.content_header.setText("Loading…")
        self.pages.setCurrentWidget(self.center)
        cid = self.category_id
        fn = {"live": lambda: self.client.live_streams(cid),
              "vod": lambda: self.client.vod_streams(cid),
              "series": lambda: self.client.series(cid)}[self.mode]
        self._run(fn, self._populate_content)

    def _populate_content(self, items):
        self.content_list.clear()
        if isinstance(items, Exception) or not items:
            self.content_header.setText("Empty"); return
        if self.mode in ("vod", "series"):
            items = sorted(items, key=lambda d: (d.get("name") or d.get("title") or "").lower())
        self.content_header.setText(f"{len(items)} items")
        grid = self.mode in ("vod", "series")
        for d in items:
            name = d.get("name") or d.get("title") or "?"
            it = QListWidgetItem(name)
            it.setData(ROLE, d)
            if grid:
                it.setSizeHint(QSize(POSTER.width() + 24, POSTER.height() + 52))
                it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
                url = d.get("stream_icon") or d.get("cover")
                self._load_poster(it, url)
            self.content_list.addItem(it)

    def _load_poster(self, item, url):
        if not url:
            return
        def apply(pm, it=item):
            try:
                it.setIcon(QIcon(pm))
            except RuntimeError:
                pass
        self.images.load(url, apply)

    # ---- selection -> info card ---------------------------------------
    def _on_content_selected(self, item, _prev=None):
        if not item:
            return
        d = item.data(ROLE)
        if d == "__back__":
            return
        # Live channels play straight away on selection (no Play click needed).
        if self.mode == "live":
            self._play(self.client.live_url(d.get("stream_id")), d.get("name"))
            self.info_title.setText(d.get("name") or "?")
            self.info_meta.setText(""); self.info_plot.setText("")
            self.info_poster.clear()
            url = d.get("stream_icon")
            if url:
                self.images.load(url, lambda pm: self.info_poster.setPixmap(pm))
            self.pages.setCurrentWidget(self.watch_page)
            return
        name = d.get("name") or d.get("title") or "?"
        self.info_title.setText(name)
        self.info_poster.clear()
        url = d.get("stream_icon") or d.get("cover")
        if url:
            self.images.load(url, lambda pm: self.info_poster.setPixmap(pm))
        meta_bits, plot = self._meta_from(d)
        self.info_meta.setText("  ·  ".join(b for b in meta_bits if b))
        self.info_plot.setText(plot or "")
        # movies: fetch full info (plot) lazily
        if self.mode == "vod" and not plot:
            sid = d.get("stream_id")
            self._run(lambda: self.client.vod_info(sid),
                      lambda info, n=name: self._fill_vod_info(info, n))
        self.pages.setCurrentWidget(self.watch_page)

    @staticmethod
    def _meta_from(d):
        info = d if isinstance(d, dict) else {}
        bits = []
        year = info.get("year") or (str(info.get("releaseDate") or info.get("release_date") or "")[:4])
        if year:
            bits.append(str(year))
        rating = info.get("rating")
        if rating:
            bits.append(f"★ {rating}")
        genre = info.get("genre")
        if genre:
            bits.append(str(genre))
        return bits, info.get("plot") or info.get("description") or ""

    def _fill_vod_info(self, info, name):
        if isinstance(info, Exception) or not info:
            return
        i = info.get("info", {})
        bits = []
        if i.get("releasedate"): bits.append(str(i["releasedate"])[:4])
        if i.get("rating"): bits.append(f"★ {i['rating']}")
        if i.get("genre"): bits.append(str(i["genre"]))
        if i.get("duration"): bits.append(str(i["duration"]))
        if self.info_title.text() == name:
            self.info_meta.setText("  ·  ".join(b for b in bits if b))
            self.info_plot.setText(i.get("plot") or i.get("description") or "")
            if i.get("movie_image"):
                self.images.load(i["movie_image"], lambda pm: self.info_poster.setPixmap(pm))

    # ---- activation ---------------------------------------------------
    def _on_content_activated(self, item):
        if not item:
            return
        d = item.data(ROLE)
        if self.mode == "live":
            self._play(self.client.live_url(d.get("stream_id")), d.get("name"),
                       poster=d.get("stream_icon", ""))
            self.pages.setCurrentWidget(self.watch_page)
        elif self.mode == "vod":
            ext = d.get("container_extension") or "mp4"
            self._play(self.client.movie_url(d.get("stream_id"), ext), d.get("name"),
                       poster=d.get("stream_icon") or d.get("cover", ""))
            self.pages.setCurrentWidget(self.watch_page)
        elif self.mode == "series":
            if d == "__back__":
                self._on_category(self.cat_list.currentItem())
            elif self.viewing_series is None:
                self._open_series(d)
            else:
                ext = d.get("container_extension") or "mp4"
                cover = self.viewing_series.get("cover", "")
                self._play(self.client.series_url(d.get("id"), ext), d.get("title"),
                           poster=cover)
                self.pages.setCurrentWidget(self.watch_page)

    def _show_categories(self):
        self.pages.setCurrentWidget(self.left)

    def _show_content(self):
        self.pages.setCurrentWidget(self.center)

    def _content_back(self):
        if self.mode == "series" and self.viewing_series is not None:
            self.viewing_series = None
            self._on_category(self.cat_list.currentItem())
        else:
            self._show_categories()

    def _on_back(self):
        self.player.stop()
        self._current_key = None
        self.setWindowTitle(self._base_title)
        if self.mpris:
            self.mpris.on_stop()
        if self.inhibitor:
            self.inhibitor.uninhibit()
        self._show_content()

    def _open_series(self, series):
        self.viewing_series = series
        self.pages.setCurrentWidget(self.center)
        self.content_header.setText("Loading episodes…")
        self.content_list.clear()
        self.content_list.setViewMode(QListWidget.ListMode)
        self.content_list.setIconSize(QSize(0, 0))
        self.content_list.setGridSize(QSize())
        sid = series.get("series_id")
        self._run(lambda: self.client.series_info(sid), self._populate_episodes)

    def _populate_episodes(self, info):
        self.content_list.clear()
        back = QListWidgetItem("⬅  Back to series"); back.setData(ROLE, "__back__")
        self.content_list.addItem(back)
        episodes = (info or {}).get("episodes") or {} if not isinstance(info, Exception) else {}
        count = 0
        for season in sorted(episodes.keys(), key=lambda s: int(s) if str(s).isdigit() else 0):
            for ep in episodes[season]:
                title = ep.get("title") or f"S{season}E{ep.get('episode_num')}"
                it = QListWidgetItem(f"S{int(season):02d} · {title}")
                it.setData(ROLE, ep)
                self.content_list.addItem(it)
                count += 1
        nm = self.viewing_series.get("name", "Series")
        self.content_header.setText(f"{nm} — {count} episodes")

    # ---- playback ------------------------------------------------------
    def _play(self, url, title=None, item_key=None, poster="", kind="movie"):
        if not url:
            return
        self.pages.setCurrentWidget(self.watch_page)
        if title:
            self._base_title = f"QMediaCenter — {title}"
            self.setWindowTitle(self._base_title)
        self._duration = 0
        self._current_key = item_key
        self._current_title = title or ""
        self._current_url = url
        self._current_poster = poster or ""
        self._current_kind = kind or "movie"
        self._last_save = 0.0
        # Resume from the saved position once the duration is known.
        pos, _dur = self.db.get_progress(item_key) if item_key else (0.0, 0.0)
        self._resume_target = pos if pos > 5 else 0.0
        self.pos_slider.setValue(0)
        self.player.play(url)
        self._show_controls()
        if self.mpris:
            self.mpris.on_play(title, self._current_poster)
        if self.inhibitor:
            self.inhibitor.inhibit()

    def _play_item(self, d):
        """Play a media/progress/favorite row dict from the home screen."""
        if not d:
            return
        url = d.get("path") or (d.get("extra") or {}).get("url")
        key = d.get("item_key", "")
        if not url and key.startswith("local:"):
            url = key[len("local:"):]
        self._play(url, d.get("title"), item_key=key or None,
                   poster=d.get("poster", ""), kind=d.get("kind", "movie"))

    # ---- detail view (info card for library/home items) ----------------
    def _build_detail_page(self):
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(8, 8, 8, 8)
        top = QHBoxLayout()
        back = QPushButton("←  Back"); back.clicked.connect(self._detail_back)
        top.addWidget(back); top.addStretch()
        v.addLayout(top)
        card = QFrame(); card.setObjectName("InfoCard")
        h = QHBoxLayout(card)
        self.detail_poster = QLabel(); self.detail_poster.setFixedSize(260, 390)
        self.detail_poster.setScaledContents(True)
        self.detail_poster.setStyleSheet("border-radius:8px; background:#e0e3e6;")
        h.addWidget(self.detail_poster)
        right = QVBoxLayout()
        self.detail_title = QLabel(); self.detail_title.setObjectName("Title")
        self.detail_title.setWordWrap(True)
        right.addWidget(self.detail_title)
        self.detail_meta = QLabel(); self.detail_meta.setObjectName("Meta")
        self.detail_meta.setWordWrap(True)
        right.addWidget(self.detail_meta)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        self.detail_plot = QLabel(); self.detail_plot.setObjectName("Plot")
        self.detail_plot.setWordWrap(True); self.detail_plot.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.detail_plot)
        right.addWidget(scroll, 1)
        btns = QHBoxLayout()
        self.btn_detail_play = QPushButton("▶  Play")
        self.btn_detail_play.clicked.connect(lambda: self._play_item(self._detail_item))
        self.btn_detail_fav = QPushButton("⭐ Favorite")
        self.btn_detail_fav.clicked.connect(self._toggle_detail_fav)
        btns.addWidget(self.btn_detail_play); btns.addWidget(self.btn_detail_fav)
        btns.addStretch()
        right.addLayout(btns)
        h.addLayout(right, 1)
        v.addWidget(card, 1)
        return page

    def _show_detail(self, item):
        d = item.data(ROLE) if item else None
        if not d:
            return
        self._detail_item = d
        self.detail_title.setText(d.get("title", "?"))
        meta = []
        if d.get("year"):
            meta.append(str(d["year"]))
        if d.get("rating"):
            meta.append(f"⭐ {d['rating']:.1f} IMDb")
        genres = d.get("genres") or []
        if isinstance(genres, list) and genres:
            meta.append(", ".join(genres))
        extra = d.get("extra") or {}
        if extra.get("season") and extra.get("episode"):
            meta.append(f"S{extra['season']:02d}E{extra['episode']:02d}")
        self.detail_meta.setText("   ·   ".join(meta))
        self.detail_plot.setText(d.get("overview") or "No description available.")
        key = d.get("item_key", "")
        fav = self.db.is_favorite(key) if key else False
        self.btn_detail_fav.setText("★ Favorited" if fav else "⭐ Favorite")
        self.detail_poster.clear()
        poster = d.get("poster")
        if poster and poster.startswith(("http://", "https://")):
            self.images.load(poster, lambda pm: self.detail_poster.setPixmap(pm))
        elif poster and os.path.exists(poster):
            self.detail_poster.setPixmap(QPixmap(poster))
        self._detail_return = self.pages.currentWidget()
        self.pages.setCurrentWidget(self.detail_page)

    def _detail_back(self):
        self.pages.setCurrentWidget(self._detail_return or self.home_page)

    def _toggle_detail_fav(self):
        d = self._detail_item
        if not d or not d.get("item_key"):
            return
        now = self.db.toggle_favorite(
            d["item_key"], source=d.get("source", "local"), title=d.get("title", ""),
            kind=d.get("kind", "movie"), poster=d.get("poster", ""),
            extra={"url": d.get("path") or (d.get("extra") or {}).get("url", "")})
        self.btn_detail_fav.setText("★ Favorited" if now else "⭐ Favorite")

    # ---- download ------------------------------------------------------
    def _download_selected(self):
        item = self.content_list.currentItem()
        if not item:
            return
        d = item.data(ROLE)
        if self.mode == "vod":
            ext = d.get("container_extension") or "mp4"
            self._start_download(self.client.movie_url(d.get("stream_id"), ext), d.get("name"), ext)
        elif self.mode == "series" and self.viewing_series and isinstance(d, dict):
            ext = d.get("container_extension") or "mp4"
            self._start_download(self.client.series_url(d.get("id"), ext),
                                 d.get("title"), ext, self.viewing_series.get("name", ""))

    def _start_download(self, url, name, ext, subdir=""):
        self.downloads.start(url, name or "download", ext, subdir)
        self.btn_downloads.setStyleSheet("font-weight:bold;")   # hint: something is running

    # ---- downloads page -----------------------------------------------
    def _build_downloads_page(self):
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(8, 8, 8, 8)
        top = QHBoxLayout()
        hdr = QLabel("Downloads"); hdr.setObjectName("Header")
        top.addWidget(hdr); top.addStretch()
        btn_clear = QPushButton("Clear finished")
        btn_clear.clicked.connect(self._clear_finished_downloads)
        top.addWidget(btn_clear)
        v.addLayout(top)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        self.dl_vbox = QVBoxLayout(container)
        self.dl_vbox.setContentsMargins(0, 0, 0, 0); self.dl_vbox.setSpacing(6)
        self.dl_empty = QLabel("No downloads yet. Pick a movie or episode and hit ⬇ Download.")
        self.dl_empty.setObjectName("Meta"); self.dl_empty.setAlignment(Qt.AlignCenter)
        self.dl_vbox.addWidget(self.dl_empty)
        self.dl_vbox.addStretch()
        scroll.setWidget(container)
        v.addWidget(scroll, 1)
        return page

    def _show_downloads(self):
        self._nav_select(self.btn_downloads)
        self.btn_downloads.setStyleSheet("")   # seen
        self.pages.setCurrentWidget(self.downloads_page)

    def _dl_row(self, did, name):
        """Create (once) and return the widgets for a download row."""
        if did in self._dl_widgets:
            return self._dl_widgets[did]
        self.dl_empty.setVisible(False)
        frame = QFrame(); frame.setObjectName("InfoCard")
        h = QVBoxLayout(frame); h.setContentsMargins(8, 6, 8, 6); h.setSpacing(2)
        lbl = QLabel(name); lbl.setObjectName("Title"); lbl.setWordWrap(True)
        h.addWidget(lbl)
        row = QHBoxLayout()
        bar = QProgressBar(); bar.setMaximum(100)
        row.addWidget(bar, 1)
        speed = QLabel("—"); speed.setObjectName("Meta"); speed.setMinimumWidth(90)
        speed.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(speed)
        stop = QPushButton("⏹"); stop.setToolTip("Stop")
        stop.clicked.connect(lambda _=False, i=did: self.downloads.cancel(i))
        row.addWidget(stop)
        h.addLayout(row)
        status = QLabel(""); status.setObjectName("Meta")
        h.addWidget(status)
        # newest on top, above the trailing stretch
        self.dl_vbox.insertWidget(0, frame)
        self._dl_widgets[did] = {"frame": frame, "bar": bar, "speed": speed,
                                 "status": status, "stop": stop}
        return self._dl_widgets[did]

    def _on_dl_started(self, did, name):
        w = self._dl_row(did, name)
        w["status"].setText("Starting…")

    def _on_dl_progress(self, did, name, done, total, speed):
        w = self._dl_row(did, name)
        mb = done / (1 << 20)
        spd_txt = f"{speed/(1<<20):.1f} MB/s" if speed > 0 else "—"
        w["speed"].setText(spd_txt)
        if total > 0:
            w["bar"].setMaximum(100)
            w["bar"].setValue(int(done * 100 / total))
            w["status"].setText(f"{mb:.0f} / {total/(1<<20):.0f} MB")
        else:
            w["bar"].setMaximum(0)   # indeterminate
            w["status"].setText(f"{mb:.0f} MB")

    def _on_dl_done(self, did, name, path):
        w = self._dl_row(did, name)
        w["bar"].setMaximum(100); w["bar"].setValue(100)
        w["speed"].setText("")
        w["status"].setText(f"✓ Done → {path}")
        w["stop"].setEnabled(False)
        if not self.downloads._workers:
            self.btn_downloads.setStyleSheet("")

    def _on_dl_failed(self, did, name, err):
        w = self._dl_row(did, name)
        w["speed"].setText("")
        w["stop"].setEnabled(False)
        w["status"].setText("⏹ Stopped (resumable)" if err == "cancelled"
                            else f"✗ Failed: {err}")
        if not self.downloads._workers:
            self.btn_downloads.setStyleSheet("")

    def _clear_finished_downloads(self):
        active = set(self.downloads._workers.keys())
        for did in list(self._dl_widgets.keys()):
            if did not in active:
                self._dl_widgets.pop(did)["frame"].deleteLater()
        if not self._dl_widgets:
            self.dl_empty.setVisible(True)

    # ---- player wiring -------------------------------------------------
    def _on_position(self, pos):
        if self._duration > 0 and not self.pos_slider.isSliderDown():
            self.pos_slider.setValue(int(pos / self._duration * 1000))
        self.time_lbl.setText(f"{self._fmt(pos)} / {self._fmt(self._duration)}")
        # Persist resume position every few seconds for "Continue Watching".
        if self._current_key and self._duration > 0 and pos - self._last_save >= 5:
            self._last_save = pos
            self.db.save_progress(self._current_key, pos, self._duration,
                                  source=self._current_key.split(":", 1)[0],
                                  title=self._current_title, kind=self._current_kind,
                                  poster=self._current_poster,
                                  extra={"url": self._current_url})

    def _on_duration(self, dur):
        self._duration = dur or 0
        # Apply a pending resume seek now that the media length is known.
        if self._resume_target and self._duration > 0:
            self.player.seek(self._resume_target)
            self._resume_target = 0.0

    def _on_pause_changed(self, paused):
        self.btn_play.setEnabled(paused)
        self.btn_pause.setEnabled(not paused)
        if self.inhibitor:
            self.inhibitor.uninhibit() if paused else self.inhibitor.inhibit()

    def _on_player_info(self, info):
        # show decoder + resolution in the title so HW decode is verifiable
        self.setWindowTitle(f"{self._base_title}   [{info}]")

    # ---- audio / subtitle track selection ------------------------------
    @staticmethod
    def _track_label(t):
        bits = []
        if t.get("lang"):
            bits.append(str(t["lang"]))
        if t.get("title"):
            bits.append(str(t["title"]))
        label = " · ".join(bits) or f"Track {t.get('id')}"
        if t.get("codec"):
            label += f"  ({t['codec']})"
        return label

    def _on_tracks_changed(self, tracks):
        # Rebuild both pickers from mpv's track-list; block signals so
        # repopulating doesn't fire a spurious selection back into mpv.
        audio = [t for t in tracks if t.get("type") == "audio"]
        subs = [t for t in tracks if t.get("type") == "sub"]

        self.audio_combo.blockSignals(True)
        self.audio_combo.clear()
        cur_a = 0
        for t in audio:
            self.audio_combo.addItem(self._track_label(t), t.get("id"))
            if t.get("selected"):
                cur_a = self.audio_combo.count() - 1
        if audio:
            self.audio_combo.setCurrentIndex(cur_a)
        self.audio_combo.setEnabled(len(audio) > 1)
        self.audio_combo.blockSignals(False)

        self.sub_combo.blockSignals(True)
        self.sub_combo.clear()
        self.sub_combo.addItem("Off", "no")
        cur_s = 0
        for t in subs:
            self.sub_combo.addItem(self._track_label(t), t.get("id"))
            if t.get("selected"):
                cur_s = self.sub_combo.count() - 1
        self.sub_combo.setCurrentIndex(cur_s)
        self.sub_combo.setEnabled(bool(subs))
        self.sub_combo.blockSignals(False)

    def _on_audio_pick(self, _idx):
        aid = self.audio_combo.currentData()
        if aid is not None:
            self.player.set_audio(aid)

    def _on_sub_pick(self, _idx):
        sid = self.sub_combo.currentData()
        self.player.set_subtitle(sid if sid is not None else "no")

    def _seek(self):
        if self._duration > 0:
            self.player.seek(self.pos_slider.value() / 1000 * self._duration)

    def _set_volume(self, v):
        self.player.set_volume(v)
        self.settings["volume"] = v
        config.save_settings(self.settings)
        if self.mpris:
            self.mpris.on_volume_change(v)

    def _stop_playback(self):
        self.player.stop()
        self.pos_slider.setValue(0)
        self.time_lbl.setText("00:00 / 00:00")
        if self._fs:
            self._exit_fullscreen()
        self._on_back()

    # ---- controls overlay ----------------------------------------------
    def _position_controls(self):
        """Pin the controls bar to the bottom of the video surface."""
        h = self.controls_bar.sizeHint().height()
        self.controls_bar.setGeometry(0, max(0, self.player.height() - h),
                                      self.player.width(), h)

    def _show_controls(self):
        self._position_controls()
        self.controls_bar.show()
        self.controls_bar.raise_()
        self.player.unsetCursor()

    def _hide_controls(self):
        # Only auto-hide in fullscreen, and never while the pointer is on the bar.
        if self._fs and not self.controls_bar.underMouse():
            self.controls_bar.hide()
            self.player.setCursor(Qt.BlankCursor)

    def _wake_controls(self):
        """Mouse moved over the video: reveal controls, then arm the hide timer."""
        self._show_controls()
        if self._fs:
            self._controls_timer.start()

    # ---- fullscreen ----------------------------------------------------
    def _toggle_fullscreen(self):
        self._exit_fullscreen() if self._fs else self._enter_fullscreen()

    def _enter_fullscreen(self):
        self._fs = True
        self._iptv_subnav_was_visible = self.iptv_subnav.isVisible()
        self.pages.setCurrentWidget(self.watch_page)
        self.nav_bar.hide(); self.iptv_subnav.hide()
        self.btn_content.hide(); self.info_card.hide()
        self.centralWidget().layout().setContentsMargins(0, 0, 0, 0)
        self.watch_layout.setContentsMargins(0, 0, 0, 0)
        self.right.setHandleWidth(0)
        self.showFullScreen()
        self._wake_controls()          # show briefly, then auto-hide

    def _exit_fullscreen(self):
        if not self._fs:
            return
        self._fs = False
        self._controls_timer.stop()
        self.nav_bar.show(); self.btn_content.show(); self.info_card.show()
        if getattr(self, "_iptv_subnav_was_visible", False):
            self.iptv_subnav.show()
        self.centralWidget().layout().setContentsMargins(8, 8, 8, 8)
        self.watch_layout.setContentsMargins(4, 4, 4, 4)
        self.right.setHandleWidth(5)
        self.showNormal()
        self._show_controls()          # always visible in windowed mode

    def eventFilter(self, obj, ev):
        if obj is self.player:
            if ev.type() == QEvent.MouseButtonDblClick:
                self._toggle_fullscreen(); return True
            if ev.type() == QEvent.Resize:
                self._position_controls()
            elif ev.type() == QEvent.MouseMove:
                self._wake_controls()
        elif obj is self.controls_bar and ev.type() == QEvent.MouseMove:
            # keep the bar alive while the pointer hovers over it
            if self._fs:
                self._controls_timer.start()
        return super().eventFilter(obj, ev)

    @staticmethod
    def _fmt(s):
        s = int(s or 0)
        return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}" if s >= 3600 else f"{s//60:02d}:{s%60:02d}"

    @staticmethod
    def _filter(widget, text):
        text = text.lower()
        for i in range(widget.count()):
            it = widget.item(i)
            it.setHidden(text not in it.text().lower())

    def _run(self, fn, callback):
        w = Worker(fn, self)
        w.done.connect(callback)
        w.finished.connect(lambda ww=w: self._workers.remove(ww) if ww in self._workers else None)
        self._workers.append(w)
        w.start()

    def closeEvent(self, ev):
        self.downloads.shutdown()   # join download threads (avoids QThread abort)
        for w in list(self._workers):
            w.wait(3000)
        self.player.shutdown()
        self.db.close()
        self.imdb.close()
        super().closeEvent(ev)
