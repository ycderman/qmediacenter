"""Official IMDb ratings via the public IMDb datasets.

IMDb publishes `title.ratings.tsv.gz` (every title's averageRating + numVotes,
keyed by the IMDb id / tconst) at https://datasets.imdbws.com/ — free for
personal, non-commercial use. We download it once into a local SQLite table and
look ratings up by IMDb id (which TMDb gives us), so ratings come straight from
IMDb with no API key and no per-title rate limit.

The dataset is a disposable cache (kept under ~/.cache), refreshed weekly.
"""
import logging
import os
import sqlite3
import threading
import time

import requests

log = logging.getLogger(__name__)

DATASET_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"
CACHE_DIR = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "qmediacenter")
DB_PATH = os.path.join(CACHE_DIR, "imdb_ratings.db")
_MAX_AGE = 60 * 60 * 24 * 7   # refresh weekly
_TIMEOUT = 60


class ImdbRatings:
    def __init__(self, path=DB_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS ratings "
            "(tconst TEXT PRIMARY KEY, rating REAL, votes INTEGER)")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
        self._conn.commit()

    # ---- state --------------------------------------------------------
    def count(self):
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM ratings").fetchone()[0]

    def is_ready(self):
        return self.count() > 0

    def updated_at(self):
        with self._lock:
            row = self._conn.execute(
                "SELECT v FROM meta WHERE k='updated_at'").fetchone()
        return float(row[0]) if row else 0.0

    def is_fresh(self):
        return self.is_ready() and (time.time() - self.updated_at() < _MAX_AGE)

    # ---- lookup -------------------------------------------------------
    def rating(self, imdb_id):
        if not imdb_id:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT rating FROM ratings WHERE tconst=?", (imdb_id,)).fetchone()
        return row[0] if row else None

    # ---- download / load ---------------------------------------------
    def ensure(self, force=False, progress=None):
        """Download + load the dataset if missing or stale. Returns row count.

        ``progress(loaded_rows)`` is called periodically while parsing. Network
        or parse errors are swallowed (caller keeps any existing data)."""
        if not force and self.is_fresh():
            return self.count()
        try:
            return self._download_and_load(progress)
        except Exception as e:
            log.warning("IMDb ratings update failed: %s", e)
            return self.count()

    def _download_and_load(self, progress):
        import gzip
        import tempfile

        # Stream the gzip to a temp file (≈25 MB), then parse it row by row.
        with requests.get(DATASET_URL, stream=True, timeout=_TIMEOUT) as r:
            r.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tsv.gz") as tmp:
                tmp_path = tmp.name
                for chunk in r.iter_content(chunk_size=1 << 16):
                    tmp.write(chunk)
        try:
            with self._lock:
                cur = self._conn.cursor()
                cur.execute("PRAGMA synchronous=OFF")
                cur.execute("PRAGMA journal_mode=MEMORY")
                cur.execute("DELETE FROM ratings")
                batch, total = [], 0
                with gzip.open(tmp_path, "rt", encoding="utf-8") as f:
                    next(f, None)  # skip header: tconst averageRating numVotes
                    for line in f:
                        parts = line.rstrip("\n").split("\t")
                        if len(parts) != 3:
                            continue
                        tconst, avg, votes = parts
                        try:
                            batch.append((tconst, float(avg), int(votes)))
                        except ValueError:
                            continue
                        if len(batch) >= 50000:
                            cur.executemany(
                                "INSERT OR REPLACE INTO ratings VALUES (?,?,?)", batch)
                            total += len(batch); batch = []
                            if progress:
                                progress(total)
                    if batch:
                        cur.executemany(
                            "INSERT OR REPLACE INTO ratings VALUES (?,?,?)", batch)
                        total += len(batch)
                self._conn.execute(
                    "INSERT OR REPLACE INTO meta VALUES ('updated_at', ?)",
                    (str(time.time()),))
                self._conn.commit()
            log.info("IMDb ratings loaded: %d titles", total)
            return total
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def close(self):
        with self._lock:
            self._conn.close()
