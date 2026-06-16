"""Threaded download manager for VOD / episodes (resumable HTTP)."""
import os
import http.client
import requests
from PySide6.QtCore import QObject, QThread, Signal

UA = "QtIPTV/0.1"
_RESUMABLE = (requests.exceptions.ChunkedEncodingError,
              requests.exceptions.ConnectionError,
              http.client.IncompleteRead)


def _safe_name(name):
    keep = " .-_()[]'"
    return "".join(c for c in name if c.isalnum() or c in keep).strip() or "download"


class DownloadWorker(QThread):
    # qlonglong: byte counts exceed 32-bit int for multi-GB files
    progress = Signal('qlonglong', 'qlonglong')   # bytes_done, total (0 if unknown)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, url, dest_path, parent=None):
        super().__init__(parent)
        self.url = url
        self.dest_path = dest_path
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        tmp = self.dest_path + ".part"
        try:
            os.makedirs(os.path.dirname(self.dest_path), exist_ok=True)
            done = os.path.getsize(tmp) if os.path.exists(tmp) else 0
            stall = 0          # consecutive failures with no new bytes
            last_done = -1
            while True:
                headers = {"User-Agent": UA}
                if done:
                    headers["Range"] = f"bytes={done}-"
                try:
                    with requests.get(self.url, stream=True, timeout=30, headers=headers) as r:
                        r.raise_for_status()
                        # If we asked to resume (Range) but the server ignored it
                        # (200 instead of 206), it's resending the whole file —
                        # restart from scratch, otherwise we'd append duplicates.
                        if done and r.status_code != 206:
                            done = 0
                        mode = "ab" if done else "wb"
                        total = done + int(r.headers.get("content-length", 0))
                        with open(tmp, mode) as f:
                            for chunk in r.iter_content(chunk_size=1 << 20):
                                if self._cancel:
                                    self.failed.emit("cancelled")
                                    return
                                if chunk:
                                    f.write(chunk)
                                    done += len(chunk)
                                    self.progress.emit(done, total)
                    break  # completed without error
                except _RESUMABLE:
                    if self._cancel:
                        raise
                    # IPTV servers often drop the connection mid-file; keep
                    # resuming via Range as long as we're still making progress.
                    if done > last_done:
                        last_done = done
                        stall = 0
                    else:
                        stall += 1
                        if stall > 8:
                            raise
                    # loop again with a Range request resuming from `done`
            os.replace(tmp, self.dest_path)
            self.finished_ok.emit(self.dest_path)
        except Exception as e:
            self.failed.emit(str(e))


class DownloadManager(QObject):
    progress = Signal(str, 'qlonglong', 'qlonglong')   # name, done, total
    finished_ok = Signal(str, str)
    failed = Signal(str, str)

    def __init__(self, download_dir, parent=None):
        super().__init__(parent)
        self.download_dir = download_dir
        self._workers = []

    def start(self, url, name, ext="mp4", subdir=""):
        filename = _safe_name(name) + "." + (ext or "mp4")
        dest = os.path.join(self.download_dir, _safe_name(subdir), filename) if subdir \
            else os.path.join(self.download_dir, filename)
        worker = DownloadWorker(url, dest)
        worker.progress.connect(lambda d, t, n=name: self.progress.emit(n, d, t))
        worker.finished_ok.connect(lambda p, n=name: self._done(worker, n, p))
        worker.failed.connect(lambda e, n=name: self._fail(worker, n, e))
        self._workers.append(worker)
        worker.start()
        return worker

    def _done(self, worker, name, path):
        self.finished_ok.emit(name, path)
        if worker in self._workers:
            self._workers.remove(worker)

    def _fail(self, worker, name, err):
        self.failed.emit(name, err)
        if worker in self._workers:
            self._workers.remove(worker)

    def cancel_all(self):
        """Stop active downloads (async); the .part is kept for later resume."""
        for w in list(self._workers):
            w.cancel()

    def shutdown(self):
        """Cancel and join all downloads — avoids 'QThread destroyed while
        running' aborts when the window closes mid-download."""
        for w in list(self._workers):
            w.cancel()
        for w in list(self._workers):
            w.wait(3000)
        self._workers.clear()
