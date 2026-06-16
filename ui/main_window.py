"""Main window: Live TV / Movies / Series with poster grid, info card and player."""
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLineEdit, QLabel, QSlider, QSplitter, QStyle, QMessageBox,
    QProgressBar, QFrame, QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QIcon, QShortcut, QKeySequence

from iptv import config
from iptv.mpv_widget import MpvWidget
from iptv.downloader import DownloadManager
from iptv.image_loader import ImageLoader
from ui.style import build_qss, desktop_accent

ROLE = Qt.UserRole
POSTER = QSize(132, 198)


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
        self._workers = []
        self._fs = False

        self.downloads = DownloadManager(
            self.settings.get("download_dir", os.path.expanduser("~/Downloads")), self)
        self.downloads.progress.connect(self._on_dl_progress)
        self.downloads.finished_ok.connect(self._on_dl_done)
        self.downloads.failed.connect(self._on_dl_failed)

        self.accent = desktop_accent()
        self.setStyleSheet(build_qss(self.accent))
        self.setWindowTitle(f"QPlayer — {profile['name']}")
        self.resize(1320, 820)
        self._build_ui()
        self._set_mode("live")

    # ---- UI ------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(8, 8, 8, 8)
        self.splitter = QSplitter(Qt.Horizontal)
        outer.addWidget(self.splitter)

        # --- left: nav + categories ---
        self.left = QWidget()
        lv = QVBoxLayout(self.left)
        lv.setContentsMargins(4, 4, 4, 4)
        nav = QHBoxLayout()
        self.btn_live = QPushButton("📺 Live")
        self.btn_vod = QPushButton("🎬 Movies")
        self.btn_series = QPushButton("📺 Series")
        for b, m in ((self.btn_live, "live"), (self.btn_vod, "vod"), (self.btn_series, "series")):
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, mm=m: self._set_mode(mm))
            nav.addWidget(b)
        lv.addLayout(nav)
        hdr = QLabel("Categories"); hdr.setObjectName("Header")
        lv.addWidget(hdr)
        self.cat_search = QLineEdit(); self.cat_search.setPlaceholderText("Filter categories…")
        self.cat_search.textChanged.connect(lambda t: self._filter(self.cat_list, t))
        lv.addWidget(self.cat_search)
        self.cat_list = QListWidget()
        self.cat_list.currentItemChanged.connect(self._on_category)
        lv.addWidget(self.cat_list)
        self.splitter.addWidget(self.left)

        # --- center: content (poster grid / list) ---
        self.center = QWidget()
        cv = QVBoxLayout(self.center)
        cv.setContentsMargins(4, 4, 4, 4)
        self.content_header = QLabel("Content"); self.content_header.setObjectName("Header")
        cv.addWidget(self.content_header)
        self.content_search = QLineEdit(); self.content_search.setPlaceholderText("Search…")
        self.content_search.textChanged.connect(lambda t: self._filter(self.content_list, t))
        cv.addWidget(self.content_search)
        self.content_list = QListWidget()
        self.content_list.setObjectName("Grid")
        self.content_list.setUniformItemSizes(True)
        self.content_list.currentItemChanged.connect(self._on_content_selected)
        self.content_list.itemActivated.connect(self._on_content_activated)
        cv.addWidget(self.content_list)
        self.splitter.addWidget(self.center)

        # --- right: info card (top) + player (bottom) ---
        self.right = QSplitter(Qt.Vertical)
        self.info_card = self._build_info_card()
        self.right.addWidget(self.info_card)

        player_box = QWidget()
        pv = QVBoxLayout(player_box)
        pv.setContentsMargins(0, 0, 0, 0)
        self.player = MpvWidget()
        self.player.setMinimumHeight(220)
        self.player.position_changed.connect(self._on_position)
        self.player.duration_changed.connect(self._on_duration)
        self.player.pause_changed.connect(self._on_pause_changed)
        self.player.installEventFilter(self)
        self.player.info_changed.connect(self._on_player_info)
        pv.addWidget(self.player, 1)
        self.controls_bar = self._build_controls()
        pv.addWidget(self.controls_bar)
        self.dl_bar = QProgressBar(); self.dl_bar.setVisible(False)
        pv.addWidget(self.dl_bar)
        self._base_title = f"QPlayer — {self.profile['name']}"
        self.right.addWidget(player_box)
        self.right.setSizes([300, 500])
        self.splitter.addWidget(self.right)

        self.splitter.setSizes([240, 540, 540])
        self._duration = 0
        self.player.set_volume(self.vol.value())

        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._exit_fullscreen)
        QShortcut(QKeySequence(Qt.Key_F), self, activated=self._toggle_fullscreen)

    def _build_info_card(self):
        card = QFrame(); card.setObjectName("InfoCard")
        h = QHBoxLayout(card)
        self.info_poster = QLabel()
        self.info_poster.setFixedSize(150, 225)
        self.info_poster.setScaledContents(True)
        self.info_poster.setStyleSheet("border-radius:8px; background:#111118;")
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

    def _build_controls(self):
        bar = QWidget()
        ctl = QHBoxLayout(bar)
        ctl.setContentsMargins(4, 2, 4, 2)
        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.btn_play.clicked.connect(self.player.toggle_pause)
        ctl.addWidget(self.btn_play)
        self.pos_slider = QSlider(Qt.Horizontal); self.pos_slider.setRange(0, 1000)
        self.pos_slider.sliderReleased.connect(self._seek)
        ctl.addWidget(self.pos_slider, 1)
        self.time_lbl = QLabel("00:00 / 00:00"); self.time_lbl.setObjectName("Meta")
        ctl.addWidget(self.time_lbl)
        vlbl = QLabel("🔊"); ctl.addWidget(vlbl)
        self.vol = QSlider(Qt.Horizontal); self.vol.setRange(0, 150); self.vol.setFixedWidth(110)
        self.vol.setValue(self.settings.get("volume", 100))
        self.vol.valueChanged.connect(self._set_volume)
        ctl.addWidget(self.vol)
        self.btn_fs = QPushButton("⛶")
        self.btn_fs.clicked.connect(self._toggle_fullscreen)
        ctl.addWidget(self.btn_fs)
        return bar

    # ---- mode / categories --------------------------------------------
    def _set_mode(self, mode):
        self.mode = mode
        self.viewing_series = None
        for b, m in ((self.btn_live, "live"), (self.btn_vod, "vod"), (self.btn_series, "series")):
            b.setChecked(m == mode)
        grid = mode in ("vod", "series")
        self.content_list.setViewMode(QListWidget.IconMode if grid else QListWidget.ListMode)
        self.content_list.setIconSize(POSTER if grid else QSize(0, 0))
        self.content_list.setGridSize(QSize(POSTER.width() + 24, POSTER.height() + 52) if grid else QSize())
        self.content_list.setWordWrap(grid)
        self.content_list.setMovement(QListWidget.Static)
        self.btn_dl_info.setEnabled(mode in ("vod", "series"))
        self.cat_list.clear(); self.content_list.clear()
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

    def _on_category(self, item, _prev=None):
        if not item:
            return
        self.category_id = item.data(ROLE)
        self.viewing_series = None
        self.content_list.clear()
        self.content_header.setText("Loading…")
        cid = self.category_id
        fn = {"live": lambda: self.client.live_streams(cid),
              "vod": lambda: self.client.vod_streams(cid),
              "series": lambda: self.client.series(cid)}[self.mode]
        self._run(fn, self._populate_content)

    def _populate_content(self, items):
        self.content_list.clear()
        if isinstance(items, Exception) or not items:
            self.content_header.setText("Empty"); return
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
            self._play(self.client.live_url(d.get("stream_id")), d.get("name"))
        elif self.mode == "vod":
            ext = d.get("container_extension") or "mp4"
            self._play(self.client.movie_url(d.get("stream_id"), ext), d.get("name"))
        elif self.mode == "series":
            if d == "__back__":
                self._on_category(self.cat_list.currentItem())
            elif self.viewing_series is None:
                self._open_series(d)
            else:
                ext = d.get("container_extension") or "mp4"
                self._play(self.client.series_url(d.get("id"), ext), d.get("title"))

    def _on_back(self):
        # Series episodes -> back to the series list; otherwise stop & reset.
        if self.mode == "series" and self.viewing_series is not None:
            self.viewing_series = None
            self._on_category(self.cat_list.currentItem())
            return
        self.player.stop()
        self.setWindowTitle(self._base_title)
        self.info_title.setText("Select something to watch")
        self.info_meta.setText(""); self.info_plot.setText("")
        self.info_poster.clear()

    def _open_series(self, series):
        self.viewing_series = series
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
    def _play(self, url, title=None):
        if title:
            self._base_title = f"QPlayer — {title}"
            self.setWindowTitle(self._base_title)
        self._duration = 0
        self.pos_slider.setValue(0)
        self.player.play(url)

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
        self.dl_bar.setVisible(True)
        self.dl_bar.setFormat(f"{name} — %p%")
        self.downloads.start(url, name or "download", ext, subdir)

    def _on_dl_progress(self, name, done, total):
        if total:
            self.dl_bar.setMaximum(total); self.dl_bar.setValue(done)
        else:
            self.dl_bar.setMaximum(0)

    def _on_dl_done(self, name, path):
        self.dl_bar.setVisible(False)
        QMessageBox.information(self, "Download complete", f"{name}\n→ {path}")

    def _on_dl_failed(self, name, err):
        self.dl_bar.setVisible(False)
        if err != "cancelled":
            QMessageBox.warning(self, "Download failed", f"{name}\n{err}")

    # ---- player wiring -------------------------------------------------
    def _on_position(self, pos):
        if self._duration > 0 and not self.pos_slider.isSliderDown():
            self.pos_slider.setValue(int(pos / self._duration * 1000))
        self.time_lbl.setText(f"{self._fmt(pos)} / {self._fmt(self._duration)}")

    def _on_duration(self, dur):
        self._duration = dur or 0

    def _on_pause_changed(self, paused):
        icon = QStyle.SP_MediaPlay if paused else QStyle.SP_MediaPause
        self.btn_play.setIcon(self.style().standardIcon(icon))

    def _on_player_info(self, info):
        # show decoder + resolution in the title so HW decode is verifiable
        self.setWindowTitle(f"{self._base_title}   [{info}]")

    def _seek(self):
        if self._duration > 0:
            self.player.seek(self.pos_slider.value() / 1000 * self._duration)

    def _set_volume(self, v):
        self.player.set_volume(v)
        self.settings["volume"] = v
        config.save_settings(self.settings)

    # ---- fullscreen ----------------------------------------------------
    def _toggle_fullscreen(self):
        self._exit_fullscreen() if self._fs else self._enter_fullscreen()

    def _enter_fullscreen(self):
        self._fs = True
        self.left.hide(); self.center.hide(); self.info_card.hide()
        self.controls_bar.hide()
        self.centralWidget().layout().setContentsMargins(0, 0, 0, 0)
        self.splitter.setHandleWidth(0)
        self.right.setHandleWidth(0)
        self.showFullScreen()

    def _exit_fullscreen(self):
        if not self._fs:
            return
        self._fs = False
        self.left.show(); self.center.show(); self.info_card.show()
        self.controls_bar.show()
        self.centralWidget().layout().setContentsMargins(8, 8, 8, 8)
        self.splitter.setHandleWidth(5)
        self.right.setHandleWidth(5)
        self.showNormal()

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        if obj is self.player and ev.type() == QEvent.MouseButtonDblClick:
            self._toggle_fullscreen(); return True
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
        w.done.connect(lambda _=None, ww=w: self._workers.remove(ww) if ww in self._workers else None)
        self._workers.append(w)
        w.start()

    def closeEvent(self, ev):
        self.downloads.shutdown()   # join download threads (avoids QThread abort)
        for w in list(self._workers):
            w.wait(3000)
        self.player.shutdown()
        super().closeEvent(ev)
