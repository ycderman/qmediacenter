"""Async poster/thumbnail loader with disk + memory cache."""
import os
import hashlib
import requests
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QPixmap

CACHE_DIR = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "qtiptv", "posters"
)


class _TaskSignals(QObject):
    done = Signal(str, str)   # url, local_path  ("" path on failure)


class _DownloadTask(QRunnable):
    def __init__(self, url, path):
        super().__init__()
        self.url = url
        self.path = path
        self.signals = _TaskSignals()

    def run(self):
        try:
            r = requests.get(self.url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) QtIPTV/0.1"})
            r.raise_for_status()
            tmp = self.path + ".part"
            with open(tmp, "wb") as f:
                f.write(r.content)
            os.replace(tmp, self.path)
            self.signals.done.emit(self.url, self.path)
        except Exception:
            self.signals.done.emit(self.url, "")


class ImageLoader(QObject):
    """Loads images off-thread; calls back with a QPixmap on the GUI thread."""

    def __init__(self, parent=None):
        super().__init__(parent)
        os.makedirs(CACHE_DIR, exist_ok=True)
        self._pool = QThreadPool.globalInstance()
        self._mem = {}                  # url -> QPixmap
        self._waiting = {}              # url -> [callbacks]
        self._tasks = set()             # keep QRunnables alive until they finish

    @staticmethod
    def _path(url):
        return os.path.join(CACHE_DIR, hashlib.md5(url.encode()).hexdigest() + ".img")

    def load(self, url, callback):
        """callback(QPixmap) — called immediately if cached, else when ready."""
        if not url:
            return
        pm = self._mem.get(url)
        if pm is not None:
            callback(pm)
            return
        path = self._path(url)
        if os.path.exists(path):
            pm = QPixmap(path)
            if not pm.isNull():
                self._mem[url] = pm
                callback(pm)
                return
        # queue download (dedupe concurrent requests for the same url)
        if url in self._waiting:
            self._waiting[url].append(callback)
            return
        self._waiting[url] = [callback]
        task = _DownloadTask(url, path)
        task.setAutoDelete(False)        # we manage its lifetime via _tasks
        task.signals.done.connect(self._on_done)
        self._tasks.add(task)
        self._pool.start(task)

    def _on_done(self, url, path):
        # drop the finished task reference
        for t in list(self._tasks):
            if t.url == url:
                self._tasks.discard(t)
        callbacks = self._waiting.pop(url, [])
        if not path:
            return
        pm = QPixmap(path)
        if pm.isNull():
            return
        self._mem[url] = pm
        for cb in callbacks:
            try:
                cb(pm)
            except RuntimeError:
                pass  # widget went away
