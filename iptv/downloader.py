"""Threaded download manager for VOD / episodes (direct HTTP streaming)."""
import os
import requests
from PySide6.QtCore import QObject, QThread, Signal


def _safe_name(name):
    keep = " .-_()[]'"
    return "".join(c for c in name if c.isalnum() or c in keep).strip() or "download"


class DownloadWorker(QThread):
    progress = Signal(int, int)        # bytes_done, total (total=0 if unknown)
    finished_ok = Signal(str)          # final path
    failed = Signal(str)               # error message

    def __init__(self, url, dest_path, parent=None):
        super().__init__(parent)
        self.url = url
        self.dest_path = dest_path
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            os.makedirs(os.path.dirname(self.dest_path), exist_ok=True)
            tmp = self.dest_path + ".part"
            headers = {"User-Agent": "QtIPTV/0.1"}
            with requests.get(self.url, stream=True, timeout=30, headers=headers) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                done = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if self._cancel:
                            f.close()
                            os.remove(tmp)
                            self.failed.emit("cancelled")
                            return
                        if chunk:
                            f.write(chunk)
                            done += len(chunk)
                            self.progress.emit(done, total)
            os.replace(tmp, self.dest_path)
            self.finished_ok.emit(self.dest_path)
        except Exception as e:
            self.failed.emit(str(e))


class DownloadManager(QObject):
    """Owns active download threads and re-emits their signals."""
    progress = Signal(str, int, int)   # name, done, total
    finished_ok = Signal(str, str)     # name, path
    failed = Signal(str, str)          # name, error

    def __init__(self, download_dir, parent=None):
        super().__init__(parent)
        self.download_dir = download_dir
        self._workers = []

    def start(self, url, name, ext="mp4", subdir=""):
        filename = _safe_name(name) + "." + (ext or "mp4")
        dest = os.path.join(self.download_dir, subdir, filename) if subdir \
            else os.path.join(self.download_dir, filename)
        worker = DownloadWorker(url, dest)
        worker.progress.connect(lambda d, t, n=name: self.progress.emit(n, d, t))
        worker.finished_ok.connect(lambda p, n=name: self._done(worker, n, p))
        worker.failed.connect(lambda e, n=name: self.failed.emit(n, e))
        self._workers.append(worker)
        worker.start()
        return worker

    def _done(self, worker, name, path):
        self.finished_ok.emit(name, path)
        if worker in self._workers:
            self._workers.remove(worker)
