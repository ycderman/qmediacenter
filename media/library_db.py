"""SQLite-backed library and state store, shared across every source.

Holds three concerns:
  * progress   — resume positions ("Continue Watching"), keyed by a stable
                 cross-source item key ("xtream:1234", "local:/path", ...).
  * favorites  — user-pinned items with a JSON metadata blob.
  * media      — items discovered by the local/network scanner.
  * meta_cache — cached TMDb/OMDb lookups so we don't re-hit the network.

A single connection is used from the GUI thread plus worker threads, so it is
opened with check_same_thread=False and guarded by a lock. Writes are small.
"""
import json
import os
import sqlite3
import threading
import time

from iptv import config

DB_PATH = os.path.join(config.CONFIG_DIR, "library.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS progress (
    item_key   TEXT PRIMARY KEY,
    source     TEXT,
    title      TEXT,
    kind       TEXT,
    position   REAL NOT NULL,
    duration   REAL NOT NULL,
    poster     TEXT,
    extra      TEXT,            -- JSON: url, ids, season/episode, ...
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS favorites (
    item_key   TEXT PRIMARY KEY,
    source     TEXT,
    title      TEXT,
    kind       TEXT,
    poster     TEXT,
    extra      TEXT,            -- JSON payload to re-open the item
    added_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS media (
    item_key   TEXT PRIMARY KEY,
    source     TEXT,            -- "local" | "emby" | "plex" | ...
    kind       TEXT,            -- "movie" | "episode" | "music" | "photo"
    title      TEXT,
    year       INTEGER,
    path       TEXT,            -- filesystem path or stream URL
    poster     TEXT,
    backdrop   TEXT,
    overview   TEXT,
    rating     REAL,            -- IMDb rating when known
    genres     TEXT,
    extra      TEXT,            -- JSON: tmdb_id, imdb_id, show/season/episode...
    added_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS meta_cache (
    key        TEXT PRIMARY KEY,   -- e.g. "tmdb:movie:Inception:2010"
    payload    TEXT NOT NULL,      -- JSON
    fetched_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_media_kind ON media(kind);
CREATE INDEX IF NOT EXISTS idx_progress_updated ON progress(updated_at);
"""


class LibraryDB:
    def __init__(self, path=DB_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ---- progress / continue watching --------------------------------
    def save_progress(self, item_key, position, duration, *, source="",
                      title="", kind="", poster="", extra=None):
        # Drop near-finished items from the resume row so they don't linger.
        if duration and position / duration > 0.95:
            self.clear_progress(item_key)
            return
        with self._lock:
            self._conn.execute(
                """INSERT INTO progress
                   (item_key, source, title, kind, position, duration, poster, extra, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(item_key) DO UPDATE SET
                     position=excluded.position, duration=excluded.duration,
                     poster=excluded.poster, extra=excluded.extra,
                     updated_at=excluded.updated_at""",
                (item_key, source, title, kind, float(position), float(duration or 0),
                 poster, json.dumps(extra or {}), time.time()),
            )
            self._conn.commit()

    def get_progress(self, item_key):
        with self._lock:
            row = self._conn.execute(
                "SELECT position, duration FROM progress WHERE item_key=?",
                (item_key,)).fetchone()
        return (row["position"], row["duration"]) if row else (0.0, 0.0)

    def clear_progress(self, item_key):
        with self._lock:
            self._conn.execute("DELETE FROM progress WHERE item_key=?", (item_key,))
            self._conn.commit()

    def continue_watching(self, limit=20):
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM progress ORDER BY updated_at DESC LIMIT ?",
                (limit,)).fetchall()
        return [self._row(r) for r in rows]

    # ---- favorites ----------------------------------------------------
    def is_favorite(self, item_key):
        with self._lock:
            return self._conn.execute(
                "SELECT 1 FROM favorites WHERE item_key=?", (item_key,)).fetchone() is not None

    def toggle_favorite(self, item_key, *, source="", title="", kind="",
                        poster="", extra=None):
        if self.is_favorite(item_key):
            with self._lock:
                self._conn.execute("DELETE FROM favorites WHERE item_key=?", (item_key,))
                self._conn.commit()
            return False
        with self._lock:
            self._conn.execute(
                """INSERT INTO favorites
                   (item_key, source, title, kind, poster, extra, added_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (item_key, source, title, kind, poster, json.dumps(extra or {}), time.time()))
            self._conn.commit()
        return True

    def favorites(self, limit=200):
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM favorites ORDER BY added_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._row(r) for r in rows]

    # ---- scanned media ------------------------------------------------
    def upsert_media(self, item):
        with self._lock:
            self._conn.execute(
                """INSERT INTO media
                   (item_key, source, kind, title, year, path, poster, backdrop,
                    overview, rating, genres, extra, added_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(item_key) DO UPDATE SET
                     title=excluded.title, year=excluded.year, poster=excluded.poster,
                     backdrop=excluded.backdrop, overview=excluded.overview,
                     rating=excluded.rating, genres=excluded.genres, extra=excluded.extra""",
                (item["item_key"], item.get("source", "local"), item.get("kind", "movie"),
                 item.get("title", ""), item.get("year"), item.get("path", ""),
                 item.get("poster", ""), item.get("backdrop", ""), item.get("overview", ""),
                 item.get("rating"), json.dumps(item.get("genres", [])),
                 json.dumps(item.get("extra", {})), time.time()))
            self._conn.commit()

    def media(self, kind=None, source=None, limit=2000, order="title"):
        q = "SELECT * FROM media"
        clauses, args = [], []
        if kind:
            clauses.append("kind=?"); args.append(kind)
        if source:
            clauses.append("source=?"); args.append(source)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        order_sql = "added_at DESC" if order == "recent" else "title COLLATE NOCASE"
        q += f" ORDER BY {order_sql} LIMIT ?"; args.append(limit)
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
        return [self._row(r) for r in rows]

    def media_paths(self, source="local"):
        with self._lock:
            rows = self._conn.execute(
                "SELECT path FROM media WHERE source=?", (source,)).fetchall()
        return {r["path"] for r in rows}

    def delete_missing(self, source, keep_paths):
        """Drop scanned rows whose files no longer exist on disk."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT item_key, path FROM media WHERE source=?", (source,)).fetchall()
            gone = [r["item_key"] for r in rows if r["path"] not in keep_paths]
            self._conn.executemany("DELETE FROM media WHERE item_key=?",
                                   [(k,) for k in gone])
            self._conn.commit()
        return len(gone)

    # ---- metadata cache ----------------------------------------------
    def cache_get(self, key, max_age=None):
        with self._lock:
            row = self._conn.execute(
                "SELECT payload, fetched_at FROM meta_cache WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        if max_age and time.time() - row["fetched_at"] > max_age:
            return None
        try:
            return json.loads(row["payload"])
        except json.JSONDecodeError:
            return None

    def cache_put(self, key, payload):
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO meta_cache (key, payload, fetched_at) VALUES (?,?,?)",
                (key, json.dumps(payload), time.time()))
            self._conn.commit()

    # ---- helpers ------------------------------------------------------
    @staticmethod
    def _row(r):
        d = dict(r)
        for k in ("extra", "genres"):
            if k in d and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except json.JSONDecodeError:
                    d[k] = {} if k == "extra" else []
        return d

    def close(self):
        with self._lock:
            self._conn.close()
