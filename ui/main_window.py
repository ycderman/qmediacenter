"""Main window: Live TV / Movies / Series browser with embedded mpv player."""
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLineEdit, QLabel, QSlider, QSplitter, QStyle, QFileDialog,
    QMessageBox, QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject

from iptv import config
from iptv.mpv_widget import MpvWidget
from iptv.downloader import DownloadManager

ROLE = Qt.UserRole


class Worker(QThread):
    """Run a callable off the GUI thread and deliver its result."""
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
        self.mode = "live"
        self.category_id = None
        self.viewing_series = None     # series dict while showing episodes
        self._workers = []
        self.downloads = DownloadManager(
            self.settings.get("download_dir", os.path.expanduser("~/Downloads")), self)
        self.downloads.progress.connect(self._on_dl_progress)
        self.downloads.finished_ok.connect(self._on_dl_done)
        self.downloads.failed.connect(self._on_dl_failed)

        self.setWindowTitle(f"QtIPTV — {profile['name']}")
        self.resize(1280, 760)
        self._build_ui()
        self._set_mode("live")

    # ---- UI ------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        outer.addWidget(splitter)

        # --- left: nav + categories ---
        left = QWidget()
        lv = QVBoxLayout(left)
        nav = QHBoxLayout()
        self.btn_live = QPushButton("Live TV")
        self.btn_vod = QPushButton("Movies")
        self.btn_series = QPushButton("Series")
        for b, m in ((self.btn_live, "live"), (self.btn_vod, "vod"), (self.btn_series, "series")):
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, mm=m: self._set_mode(mm))
            nav.addWidget(b)
        lv.addLayout(nav)
        lv.addWidget(QLabel("Categories"))
        self.cat_search = QLineEdit(); self.cat_search.setPlaceholderText("Filter categories…")
        self.cat_search.textChanged.connect(self._filter_categories)
        lv.addWidget(self.cat_search)
        self.cat_list = QListWidget()
        self.cat_list.currentItemChanged.connect(self._on_category)
        lv.addWidget(self.cat_list)
        splitter.addWidget(left)

        # --- middle: content ---
        mid = QWidget()
        mv = QVBoxLayout(mid)
        self.content_header = QLabel("Content")
        mv.addWidget(self.content_header)
        self.content_search = QLineEdit(); self.content_search.setPlaceholderText("Search…")
        self.content_search.textChanged.connect(self._filter_content)
        mv.addWidget(self.content_search)
        self.content_list = QListWidget()
        self.content_list.itemActivated.connect(self._on_content_activated)
        mv.addWidget(self.content_list)
        row = QHBoxLayout()
        self.play_sel = QPushButton("Play")
        self.play_sel.clicked.connect(lambda: self._on_content_activated(self.content_list.currentItem()))
        self.dl_sel = QPushButton("Download")
        self.dl_sel.clicked.connect(self._download_selected)
        row.addWidget(self.play_sel); row.addWidget(self.dl_sel)
        mv.addLayout(row)
        splitter.addWidget(mid)

        # --- right: player ---
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.player = MpvWidget()
        self.player.position_changed.connect(self._on_position)
        self.player.duration_changed.connect(self._on_duration)
        self.player.pause_changed.connect(self._on_pause_changed)
        rv.addWidget(self.player, 1)

        ctl = QHBoxLayout()
        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.btn_play.clicked.connect(self.player.toggle_pause)
        ctl.addWidget(self.btn_play)
        self.pos_slider = QSlider(Qt.Horizontal)
        self.pos_slider.setRange(0, 1000)
        self.pos_slider.sliderReleased.connect(self._seek)
        ctl.addWidget(self.pos_slider, 1)
        self.time_lbl = QLabel("00:00 / 00:00")
        ctl.addWidget(self.time_lbl)
        ctl.addWidget(QLabel("Vol"))
        self.vol = QSlider(Qt.Horizontal); self.vol.setRange(0, 150)
        self.vol.setFixedWidth(110)
        self.vol.setValue(self.settings.get("volume", 100))
        self.vol.valueChanged.connect(self._set_volume)
        ctl.addWidget(self.vol)
        self.btn_fs = QPushButton("⛶")
        self.btn_fs.clicked.connect(self._toggle_fullscreen)
        ctl.addWidget(self.btn_fs)
        rv.addLayout(ctl)

        self.dl_bar = QProgressBar(); self.dl_bar.setVisible(False)
        rv.addWidget(self.dl_bar)
        splitter.addWidget(right)

        splitter.setSizes([260, 360, 660])
        self._duration = 0
        self.player.set_volume(self.vol.value())
        self.player.installEventFilter(self)

    # ---- mode / categories --------------------------------------------
    def _set_mode(self, mode):
        self.mode = mode
        self.viewing_series = None
        for b, m in ((self.btn_live, "live"), (self.btn_vod, "vod"), (self.btn_series, "series")):
            b.setChecked(m == mode)
        self.dl_sel.setEnabled(mode in ("vod", "series"))
        self.cat_list.clear()
        self.content_list.clear()
        self.content_header.setText("Loading categories…")
        fetch = {"live": self.client.live_categories,
                 "vod": self.client.vod_categories,
                 "series": self.client.series_categories}[mode]
        self._run(fetch, self._populate_categories)

    def _populate_categories(self, cats):
        self.cat_list.clear()
        if isinstance(cats, Exception) or not cats:
            self.content_header.setText("No categories")
            return
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
        if self.mode == "live":
            self._run(lambda: self.client.live_streams(cid), self._populate_content)
        elif self.mode == "vod":
            self._run(lambda: self.client.vod_streams(cid), self._populate_content)
        else:
            self._run(lambda: self.client.series(cid), self._populate_content)

    def _populate_content(self, items):
        self.content_list.clear()
        if isinstance(items, Exception) or not items:
            self.content_header.setText("Empty")
            return
        self.content_header.setText(f"{len(items)} items")
        for d in items:
            name = d.get("name") or d.get("title") or "?"
            it = QListWidgetItem(name)
            it.setData(ROLE, d)
            self.content_list.addItem(it)

    # ---- activation (play / open series) ------------------------------
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
            if self.viewing_series is None:
                self._open_series(d)
            else:
                self._play_episode(d)

    def _open_series(self, series):
        self.viewing_series = series
        self.content_header.setText("Loading episodes…")
        self.content_list.clear()
        sid = series.get("series_id")
        self._run(lambda: self.client.series_info(sid), self._populate_episodes)

    def _populate_episodes(self, info):
        self.content_list.clear()
        back = QListWidgetItem("⬅ Back to series")
        back.setData(ROLE, "__back__")
        self.content_list.addItem(back)
        if isinstance(info, Exception) or not info:
            self.content_header.setText("No episode info")
            return
        episodes = info.get("episodes") or {}
        count = 0
        for season in sorted(episodes.keys(), key=lambda s: int(s) if str(s).isdigit() else 0):
            for ep in episodes[season]:
                title = ep.get("title") or f"S{season}E{ep.get('episode_num')}"
                it = QListWidgetItem(f"S{season:>2} · {title}")
                it.setData(ROLE, ep)
                self.content_list.addItem(it)
                count += 1
        self.content_header.setText(f"{self.viewing_series.get('name','Series')} — {count} episodes")

    def _play_episode(self, ep):
        if ep == "__back__":
            self._on_category(self.cat_list.currentItem())
            return
        ext = ep.get("container_extension") or "mp4"
        self._play(self.client.series_url(ep.get("id"), ext), ep.get("title"))

    # handle the back item which lands in _on_content_activated for series
    def _maybe_back(self, d):
        if d == "__back__":
            self._on_category(self.cat_list.currentItem())
            return True
        return False

    # ---- playback ------------------------------------------------------
    def _play(self, url, title=None):
        if title:
            self.setWindowTitle(f"QtIPTV — {title}")
        self.pos_slider.setRange(0, 1000)
        self.player.play(url)

    # ---- download ------------------------------------------------------
    def _download_selected(self):
        item = self.content_list.currentItem()
        if not item:
            return
        d = item.data(ROLE)
        if self.mode == "vod":
            ext = d.get("container_extension") or "mp4"
            url = self.client.movie_url(d.get("stream_id"), ext)
            self._start_download(url, d.get("name"), ext)
        elif self.mode == "series" and self.viewing_series is not None and isinstance(d, dict):
            ext = d.get("container_extension") or "mp4"
            url = self.client.series_url(d.get("id"), ext)
            sub = self.viewing_series.get("name", "")
            self._start_download(url, d.get("title"), ext, sub)

    def _start_download(self, url, name, ext, subdir=""):
        from iptv.downloader import _safe_name  # noqa
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

    # ---- player control wiring ----------------------------------------
    def _on_position(self, pos):
        if self._duration > 0 and not self.pos_slider.isSliderDown():
            self.pos_slider.setValue(int(pos / self._duration * 1000))
        self.time_lbl.setText(f"{self._fmt(pos)} / {self._fmt(self._duration)}")

    def _on_duration(self, dur):
        self._duration = dur or 0

    def _on_pause_changed(self, paused):
        icon = QStyle.SP_MediaPlay if paused else QStyle.SP_MediaPause
        self.btn_play.setIcon(self.style().standardIcon(icon))

    def _seek(self):
        if self._duration > 0:
            self.player.seek(self.pos_slider.value() / 1000 * self._duration)

    def _set_volume(self, v):
        self.player.set_volume(v)
        self.settings["volume"] = v
        config.save_settings(self.settings)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        if obj is self.player and ev.type() == QEvent.MouseButtonDblClick:
            self._toggle_fullscreen()
            return True
        return super().eventFilter(obj, ev)

    @staticmethod
    def _fmt(s):
        s = int(s or 0)
        return f"{s // 3600:02d}:{(s % 3600)//60:02d}:{s % 60:02d}" if s >= 3600 \
            else f"{s // 60:02d}:{s % 60:02d}"

    # ---- filters / helpers --------------------------------------------
    def _filter_categories(self, text):
        self._filter(self.cat_list, text)

    def _filter_content(self, text):
        self._filter(self.content_list, text)

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
        self.player.shutdown()
        super().closeEvent(ev)
