"""Shared pytest fixtures for QMediaCenter tests."""
import locale
import os
import tempfile
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
locale.setlocale(locale.LC_NUMERIC, "C")


@pytest.fixture
def xdg_tmp(tmp_path, monkeypatch):
    """Isolate XDG config/cache dirs to a temp directory."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return tmp_path


@pytest.fixture
def tmp_db(tmp_path):
    """Return a fresh LibraryDB instance backed by a temp file."""
    from media.library_db import LibraryDB
    db = LibraryDB(str(tmp_path / "test.db"))
    yield db
    db.close()


def make_vod(n=120):
    now = int(time.time())
    return [
        {
            "stream_id": 200 + i,
            "name": f"Movie {i:03d}",
            "container_extension": "mkv",
            "stream_icon": "",
            "added": str(now - i * 3600),
        }
        for i in range(n)
    ]


def make_series(n=30):
    now = int(time.time())
    return [
        {
            "series_id": 300 + i,
            "name": f"Series {i:03d}",
            "cover": "",
            "last_modified": str(now - i * 7200),
        }
        for i in range(n)
    ]
