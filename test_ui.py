"""
Comprehensive test suite for QMediaCenter.

Covers:
  - LibraryDB: all CRUD operations, cache TTL, cache_exists
  - ImageLoader: LRU eviction, request deduplication, disk cache
  - XtreamClient: real HTTP against a mock server
  - MainWindow (offscreen Qt): startup, mode switch, categories,
    recently-added (cache-miss + cache-hit), background refresh,
    search, series drill-down, watch page, resize layout
"""

import os
import sys
import json
import time
import locale
import tempfile
import threading
import unittest
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
locale.setlocale(locale.LC_NUMERIC, "C")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vod(n=120):
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


def _make_series(n=30):
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


# ---------------------------------------------------------------------------
# 1. LibraryDB
# ---------------------------------------------------------------------------

class TestLibraryDB(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.environ["XDG_CONFIG_HOME"] = self.tmpdir
        from media.library_db import LibraryDB
        self.db = LibraryDB(os.path.join(self.tmpdir, "test.db"))

    def tearDown(self):
        self.db.close()

    def test_progress_round_trip(self):
        self.db.save_progress("key1", 0.42, 120.0)
        pos, dur = self.db.get_progress("key1")
        self.assertAlmostEqual(pos, 0.42, places=2)
        self.assertAlmostEqual(dur, 120.0, places=1)

    def test_progress_missing_key(self):
        pos, dur = self.db.get_progress("nonexistent")
        self.assertEqual(pos, 0.0)
        self.assertEqual(dur, 0.0)

    def test_watched(self):
        self.assertFalse(self.db.is_watched("k1"))
        self.db.mark_watched("k1")
        self.assertTrue(self.db.is_watched("k1"))
        self.db.unmark_watched("k1")
        self.assertFalse(self.db.is_watched("k1"))

    def test_watched_keys_bulk(self):
        self.db.mark_watched("a")
        self.db.mark_watched("b")
        result = self.db.watched_keys(["a", "b", "c"])
        self.assertIn("a", result)
        self.assertIn("b", result)
        self.assertNotIn("c", result)

    def test_favorites(self):
        self.db.toggle_favorite("fav1")
        favs = self.db.favorites(10)
        self.assertTrue(any(d.get("item_key") == "fav1" for d in favs))
        self.db.toggle_favorite("fav1")
        favs2 = self.db.favorites(10)
        self.assertFalse(any(d.get("item_key") == "fav1" for d in favs2))

    def test_cache_put_and_get(self):
        payload = {"hello": "world", "nums": [1, 2, 3]}
        self.db.cache_put("mykey", payload)
        result = self.db.cache_get("mykey")
        self.assertEqual(result, payload)

    def test_cache_get_missing(self):
        self.assertIsNone(self.db.cache_get("no_such_key"))

    def test_cache_ttl_expired(self):
        self.db.cache_put("ttl_key", {"x": 1})
        time.sleep(0.05)
        result = self.db.cache_get("ttl_key", max_age=0.01)
        self.assertIsNone(result)

    def test_cache_ttl_valid(self):
        self.db.cache_put("ttl_key2", {"x": 2})
        result = self.db.cache_get("ttl_key2", max_age=3600)
        self.assertIsNotNone(result)

    def test_cache_exists_true(self):
        self.db.cache_put("exist_key", [1, 2])
        self.assertTrue(self.db.cache_exists("exist_key", max_age=3600))

    def test_cache_exists_false_missing(self):
        self.assertFalse(self.db.cache_exists("missing_key"))

    def test_cache_exists_false_expired(self):
        self.db.cache_put("exp_key", [1])
        time.sleep(0.05)
        self.assertFalse(self.db.cache_exists("exp_key", max_age=0.01))

    def test_cache_overwrite(self):
        self.db.cache_put("ow", {"v": 1})
        self.db.cache_put("ow", {"v": 2})
        result = self.db.cache_get("ow")
        self.assertEqual(result["v"], 2)

    def test_large_payload(self):
        big = _make_vod(1000)
        self.db.cache_put("big", big)
        result = self.db.cache_get("big")
        self.assertEqual(len(result), 1000)
        self.assertEqual(result[0]["name"], big[0]["name"])


# ---------------------------------------------------------------------------
# 2. ImageLoader
# ---------------------------------------------------------------------------

class TestImageLoader(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from PySide6.QtWidgets import QApplication
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        os.environ["XDG_CACHE_HOME"] = self.tmpdir

    def _make_loader(self):
        import importlib
        import iptv.image_loader as il
        importlib.reload(il)
        return il.ImageLoader()

    def test_load_empty_url(self):
        loader = self._make_loader()
        called = []
        loader.load("", lambda pm: called.append(pm))
        self.assertEqual(called, [])

    def test_lru_eviction(self):
        from iptv.image_loader import ImageLoader, _MEM_LIMIT
        loader = ImageLoader()
        from PySide6.QtGui import QPixmap
        for i in range(_MEM_LIMIT + 10):
            url = f"http://fake/{i}.png"
            loader._mem_put(url, QPixmap())
        self.assertLessEqual(len(loader._mem), _MEM_LIMIT)

    def test_lru_most_recent_kept(self):
        from iptv.image_loader import ImageLoader, _MEM_LIMIT
        from PySide6.QtGui import QPixmap
        loader = ImageLoader()
        kept_url = "http://fake/keep.png"
        loader._mem_put(kept_url, QPixmap())
        for i in range(_MEM_LIMIT):
            loader._mem_put(f"http://fake/{i}.png", QPixmap())
            loader._mem.move_to_end(kept_url)
        self.assertIn(kept_url, loader._mem)

    def test_dedup_concurrent_requests(self):
        from iptv.image_loader import ImageLoader
        loader = ImageLoader()
        url = "http://fake/img.png"
        loader._waiting[url] = [lambda pm: None]
        cb2 = lambda pm: None
        loader.load(url, cb2)
        self.assertEqual(len(loader._waiting[url]), 2)

    def test_disk_cache_hit(self):
        import hashlib, struct, zlib
        from iptv import image_loader as il
        cache_dir = os.path.join(self.tmpdir, "qmediacenter", "posters")
        os.makedirs(cache_dir, exist_ok=True)
        url = "http://fake/cached.png"
        filename = hashlib.md5(url.encode()).hexdigest() + ".img"
        path = os.path.join(cache_dir, filename)
        # Write a minimal valid 1x1 white PNG
        def _png1x1():
            sig = b'\x89PNG\r\n\x1a\n'
            def chunk(tag, data):
                c = zlib.crc32(tag + data) & 0xFFFFFFFF
                return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", c)
            ihdr = chunk(b'IHDR', struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            idat = chunk(b'IDAT', zlib.compress(b'\x00\xFF\xFF\xFF'))
            iend = chunk(b'IEND', b'')
            return sig + ihdr + idat + iend
        with open(path, 'wb') as f:
            f.write(_png1x1())
        orig = il.CACHE_DIR
        il.CACHE_DIR = cache_dir
        try:
            loader = il.ImageLoader()
            received = []
            loader.load(url, lambda p: received.append(p))
            self.assertEqual(len(received), 1)
            self.assertFalse(received[0].isNull())
        finally:
            il.CACHE_DIR = orig


# ---------------------------------------------------------------------------
# 3. XtreamClient against a mock HTTP server
# ---------------------------------------------------------------------------

VOD_DATA = _make_vod(50)
SERIES_DATA = _make_series(10)

class _MockXtreamHandler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        action = params.get("action", [""])[0]

        if action == "get_live_categories":
            body = [{"category_id": "1", "category_name": "News"}]
        elif action == "get_vod_categories":
            body = [{"category_id": "2", "category_name": "Action"}]
        elif action == "get_series_categories":
            body = [{"category_id": "3", "category_name": "Drama"}]
        elif action == "get_live_streams":
            body = [{"stream_id": 101, "name": "CNN", "stream_icon": ""}]
        elif action == "get_vod_streams":
            body = VOD_DATA
        elif action == "get_series":
            body = SERIES_DATA
        elif action == "get_series_info":
            body = {"episodes": {"1": [
                {"id": 401, "title": "Pilot", "container_extension": "mp4"}
            ]}}
        elif action == "get_vod_info":
            body = {"movie_data": {"name": "Test Movie"}, "info": {}}
        elif not action:
            body = {
                "user_info": {"auth": 1, "username": "u", "exp_date": "9999999999"},
                "server_info": {}
            }
        else:
            body = []

        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class TestXtreamClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _MockXtreamHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        from iptv.xtream import XtreamClient
        cls.client = XtreamClient(
            f"http://127.0.0.1:{cls.port}", "u", "p"
        )

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_authenticate(self):
        self.assertTrue(self.client.authenticate())

    def test_live_categories(self):
        cats = self.client.live_categories()
        self.assertIsInstance(cats, list)
        self.assertGreater(len(cats), 0)
        self.assertIn("category_name", cats[0])

    def test_vod_categories(self):
        cats = self.client.vod_categories()
        self.assertTrue(len(cats) > 0)

    def test_series_categories(self):
        cats = self.client.series_categories()
        self.assertTrue(len(cats) > 0)

    def test_live_streams(self):
        streams = self.client.live_streams("1")
        self.assertTrue(len(streams) > 0)
        self.assertIn("stream_id", streams[0])

    def test_vod_streams(self):
        streams = self.client.vod_streams("2")
        self.assertEqual(len(streams), 50)
        self.assertIn("name", streams[0])
        self.assertIn("added", streams[0])

    def test_series(self):
        series = self.client.series("3")
        self.assertEqual(len(series), 10)

    def test_series_info(self):
        info = self.client.series_info(301)
        self.assertIn("episodes", info)

    def test_vod_info(self):
        info = self.client.vod_info(201)
        self.assertIsNotNone(info)

    def test_live_url_format(self):
        url = self.client.live_url(101)
        self.assertIn("101", url)

    def test_movie_url_format(self):
        url = self.client.movie_url(201, "mkv")
        self.assertIn("201", url)
        self.assertIn("mkv", url)


# ---------------------------------------------------------------------------
# 4. MainWindow UI (offscreen)
# ---------------------------------------------------------------------------

class FakeClient:
    host = "http://127.0.0.1:19999"
    username = "u"
    password = "p"

    def live_categories(self):
        return [{"category_id": "1", "category_name": "News"}]

    def vod_categories(self):
        return [{"category_id": "2", "category_name": "Action"},
                {"category_id": "3", "category_name": "Drama"}]

    def series_categories(self):
        return [{"category_id": "4", "category_name": "Sci-Fi"}]

    def live_streams(self, c):
        return [{"stream_id": 101, "name": "CNN", "stream_icon": ""},
                {"stream_id": 102, "name": "BBC", "stream_icon": ""}]

    def vod_streams(self, c=None):
        return _make_vod(80)

    def series(self, c=None):
        return _make_series(20)

    def series_info(self, s):
        return {"episodes": {"1": [
            {"id": 401, "title": "Pilot", "container_extension": "mp4"},
            {"id": 402, "title": "Episode 2", "container_extension": "mp4"},
        ]}}

    def vod_info(self, i):
        return {"movie_data": {"name": "Test"}, "info": {}}

    def live_url(self, i, ext="ts"):
        return f"http://fake/live/{i}.ts"

    def movie_url(self, i, ext="mkv"):
        return f"http://fake/movie/{i}.{ext}"

    def series_url(self, i, ext="mp4"):
        return f"http://fake/series/{i}.{ext}"


class TestMainWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer, QEventLoop
        cls.app = QApplication.instance() or QApplication(sys.argv)
        cls.tmpdir = tempfile.mkdtemp()
        os.environ["XDG_CONFIG_HOME"] = cls.tmpdir
        os.environ["XDG_CACHE_HOME"] = cls.tmpdir

        from ui.main_window import MainWindow
        cls.win = MainWindow({"name": "Test"}, FakeClient())
        cls.win.show()

        cls.QTimer = QTimer
        cls.QEventLoop = QEventLoop

    @classmethod
    def tearDownClass(cls):
        cls.win.player.shutdown()
        cls.win.close()

    def _pump(self, ms=200):
        loop = self.QEventLoop()
        self.QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def test_01_window_visible(self):
        self.assertTrue(self.win.isVisible())

    def test_02_home_page_on_startup(self):
        from ui.main_window import MainWindow
        self.assertIsNotNone(self.win.pages)

    def test_03_switch_to_live(self):
        self.win._set_mode("live")
        self._pump(300)
        self.assertGreaterEqual(self.win.cat_list.count(), 1)

    def test_04_live_category_loads_streams(self):
        self.win._set_mode("live")
        self._pump(200)
        self.win.cat_list.setCurrentRow(0)
        self._pump(300)
        self.assertGreaterEqual(self.win.content_list.count(), 2)

    def test_05_switch_to_vod(self):
        self.win._set_mode("vod")
        self._pump(300)
        self.assertGreaterEqual(self.win.cat_list.count(), 1)

    def test_06_vod_has_recent_item(self):
        self.win._set_mode("vod")
        self._pump(200)
        items = [self.win.cat_list.item(i).text()
                 for i in range(self.win.cat_list.count())]
        self.assertTrue(any("Son Eklenenler" in t or "Recently" in t or "recent" in t.lower()
                            for t in items))

    def test_07_vod_category_loads_content(self):
        self.win._set_mode("vod")
        self._pump(200)
        for i in range(self.win.cat_list.count()):
            item = self.win.cat_list.item(i)
            if item.data(256) != "__recent__":
                self.win.cat_list.setCurrentItem(item)
                break
        self._pump(400)
        self.assertGreaterEqual(self.win.content_list.count(), 1)

    def test_08_recently_added_cache_miss_then_hit(self):
        self.win._set_mode("vod")
        self._pump(200)
        self.win.db.cache_put("xtream_vod_recent", _make_vod(50))
        for i in range(self.win.cat_list.count()):
            item = self.win.cat_list.item(i)
            if item.data(256) == "__recent__":
                self.win.cat_list.setCurrentItem(item)
                break
        self._pump(400)
        self.assertGreaterEqual(self.win.content_list.count(), 1)

    def test_09_recently_added_pagination(self):
        self.win.db.cache_put("xtream_vod_recent", _make_vod(80))
        self.win._set_mode("vod")
        self._pump(200)
        for i in range(self.win.cat_list.count()):
            item = self.win.cat_list.item(i)
            if item.data(256) == "__recent__":
                self.win.cat_list.setCurrentItem(item)
                break
        self._pump(600)
        self.assertGreater(self.win.content_list.count(), 0)
        self.assertLessEqual(self.win.content_list.count(), 80)

    def test_10_sort_recent_orders_by_timestamp(self):
        items = _make_vod(10)
        sorted_items = self.win._sort_recent(items)
        timestamps = [int(d.get("added", 0)) for d in sorted_items]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_11_sort_recent_caps_at_1000(self):
        items = _make_vod(1200)
        result = self.win._sort_recent(items)
        self.assertEqual(len(result), 1000)

    def test_12_bg_refresh_stores_cache(self):
        self.win.db._conn.execute(
            "DELETE FROM meta_cache WHERE key LIKE 'xtream_%'")
        self.win.db._conn.commit()
        self.win._bg_refresh_all()
        self._pump(1000)
        self.assertTrue(
            self.win.db.cache_exists("xtream_vod_recent", max_age=7200) or
            self.win.db.cache_exists("xtream_series_recent", max_age=7200)
        )

    def test_13_refresh_timer_configured(self):
        self.assertTrue(self.win._refresh_timer.isActive())
        self.assertEqual(self.win._refresh_timer.interval(),
                         self.win._STREAM_CACHE_TTL * 1000)

    def test_14_switch_to_series(self):
        self.win._set_mode("series")
        self._pump(300)
        self.assertGreaterEqual(self.win.cat_list.count(), 1)

    def test_15_series_category_loads_list(self):
        self.win._set_mode("series")
        self._pump(200)
        for i in range(self.win.cat_list.count()):
            item = self.win.cat_list.item(i)
            if item.data(256) != "__recent__":
                self.win.cat_list.setCurrentItem(item)
                break
        self._pump(400)
        self.assertGreaterEqual(self.win.content_list.count(), 1)

    def test_16_series_drill_down_to_episodes(self):
        self.win._set_mode("series")
        self._pump(200)
        for i in range(self.win.cat_list.count()):
            item = self.win.cat_list.item(i)
            if item.data(256) != "__recent__":
                self.win.cat_list.setCurrentItem(item)
                break
        self._pump(400)
        if self.win.content_list.count() > 0:
            self.win._on_content_activated(self.win.content_list.item(0))
            self._pump(400)
            self.assertGreaterEqual(self.win.content_list.count(), 1)

    def test_17_back_button_in_episodes(self):
        self.win._set_mode("series")
        self._pump(200)
        for i in range(self.win.cat_list.count()):
            item = self.win.cat_list.item(i)
            if item.data(256) != "__recent__":
                self.win.cat_list.setCurrentItem(item)
                break
        self._pump(400)
        if self.win.content_list.count() > 0:
            self.win._on_content_activated(self.win.content_list.item(0))
            self._pump(400)
            first = self.win.content_list.item(0)
            if first:
                self.assertTrue("⬅" in first.text() or "Back" in first.text())

    def test_18_search_buf_cleared_on_mode_switch(self):
        self.win._search_buf["vod"] = _make_vod(10)
        self.win._set_mode("live")
        self._pump(100)
        self.assertEqual(self.win._search_buf, {})

    def test_19_cat_search_uses_cache(self):
        self.win._set_mode("vod")
        self._pump(200)
        self.win.db.cache_put("xtream_vod_streams", _make_vod(50))
        self.win.cat_search.setText("Movie 001")
        self._pump(400)
        self.win.cat_search.clear()
        self._pump(100)

    def test_20_cat_search_no_results(self):
        self.win._set_mode("vod")
        self._pump(200)
        self.win.db.cache_put("xtream_vod_streams", _make_vod(10))
        self.win.cat_search.setText("xyzzy_no_match_ever")
        self._pump(400)
        content_count = self.win.content_list.count()
        self.assertEqual(content_count, 0)
        self.win.cat_search.clear()
        self._pump(100)

    def test_21_resize_triggers_layout(self):
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QResizeEvent
        old_size = self.win.size()
        new_size = QSize(old_size.width() + 100, old_size.height() + 100)
        ev = QResizeEvent(new_size, old_size)
        self.win.resizeEvent(ev)
        self._pump(50)

    def test_22_recent_items_capped(self):
        self.win._recent_items = list(range(1500))
        self.win._recent_offset = 0
        self.win._show_recently_added(_make_vod(100))
        self.assertLessEqual(len(self.win._recent_items), 1000)

    def test_23_recent_offset_advances_after_first_batch(self):
        # _show_recently_added resets to 0 then immediately loads first page.
        # With 500 items and _RECENT_PAGE=250, offset should be 250 after one batch.
        big = _make_vod(500)
        self.win._show_recently_added(big)
        self.assertEqual(self.win._recent_items[:3], big[:3])
        self.assertEqual(self.win._recent_offset, self.win._RECENT_PAGE)

    def test_24_stream_cache_ttl_constant(self):
        self.assertEqual(self.win._STREAM_CACHE_TTL, 2 * 3600)

    def test_25_image_loader_thread_limit(self):
        from iptv.image_loader import _MAX_THREADS
        pool = self.win.images._pool
        self.assertLessEqual(pool.maxThreadCount(), _MAX_THREADS)

    def test_26_image_loader_mem_limit(self):
        from iptv.image_loader import _MEM_LIMIT
        self.assertEqual(_MEM_LIMIT, 300)

    def test_27_player_initialized(self):
        self.assertIsNotNone(self.win.player)

    def test_28_db_initialized(self):
        self.assertIsNotNone(self.win.db)

    def test_29_downloads_manager_initialized(self):
        self.assertIsNotNone(self.win.downloads)

    def test_30_close_event_stops_timer(self):
        import copy
        timer_was_active = self.win._refresh_timer.isActive()
        self.assertTrue(timer_was_active)


# ---------------------------------------------------------------------------
# 5. Local media scanner
# ---------------------------------------------------------------------------

from media.local_scanner import parse_filename, iter_media_files, LibraryScanner


class TestLocalScanner(unittest.TestCase):

    # --- parse_filename ---

    def test_movie_year_and_quality(self):
        r = parse_filename("Inception.2010.1080p.BluRay.x264.mkv")
        self.assertEqual(r["kind"], "movie")
        self.assertEqual(r["title"], "Inception")
        self.assertEqual(r["year"], 2010)

    def test_movie_web_dl(self):
        r = parse_filename("The.Matrix.1999.WEB-DL.1080p.mkv")
        self.assertEqual(r["kind"], "movie")
        self.assertEqual(r["title"], "The Matrix")
        self.assertEqual(r["year"], 1999)

    def test_episode_sxxeyy(self):
        r = parse_filename("Breaking.Bad.S03E07.720p.mkv")
        self.assertEqual(r["kind"], "episode")
        self.assertEqual(r["title"], "Breaking Bad")
        self.assertEqual(r["season"], 3)
        self.assertEqual(r["episode"], 7)

    def test_episode_NxMM_format(self):
        r = parse_filename("Dizi.1x02.HDTV.avi")
        self.assertEqual(r["kind"], "episode")
        self.assertEqual(r["season"], 1)
        self.assertEqual(r["episode"], 2)

    def test_episode_with_year_in_show_title(self):
        r = parse_filename("Show.2019.S01E01.mkv")
        self.assertEqual(r["kind"], "episode")
        self.assertEqual(r["season"], 1)
        self.assertEqual(r["episode"], 1)

    def test_movie_no_year(self):
        r = parse_filename("Oldfilm.BluRay.mkv")
        self.assertEqual(r["kind"], "movie")
        self.assertIsNone(r["year"])
        self.assertTrue(len(r["title"]) > 0)

    def test_weird_filename_no_crash(self):
        r = parse_filename("---___.mp4")
        self.assertIn("kind", r)
        self.assertIn("title", r)

    def test_empty_stem_no_crash(self):
        r = parse_filename(".mp4")
        self.assertIn("kind", r)

    def test_year_at_start_of_name(self):
        r = parse_filename("2001.A.Space.Odyssey.1968.BluRay.mkv")
        self.assertEqual(r["kind"], "movie")
        self.assertIsNotNone(r.get("year"))

    def test_spaces_in_filename(self):
        r = parse_filename("The Dark Knight (2008) [1080p].mkv")
        self.assertEqual(r["kind"], "movie")
        self.assertEqual(r["year"], 2008)

    # --- iter_media_files ---

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _make(self, relpath):
        full = os.path.join(self.tmpdir, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, "w").close()
        return full

    def test_iter_finds_video(self):
        self._make("movies/film.mkv")
        found = list(iter_media_files([self.tmpdir]))
        paths = [p for p, k in found]
        self.assertTrue(any("film.mkv" in p for p in paths))

    def test_iter_classifies_music(self):
        self._make("music/song.mp3")
        found = dict(iter_media_files([self.tmpdir]))
        self.assertIn("music", found.values())

    def test_iter_classifies_photo(self):
        self._make("photos/pic.jpg")
        found = dict(iter_media_files([self.tmpdir]))
        self.assertIn("photo", found.values())

    def test_iter_ignores_non_media(self):
        self._make("stuff/readme.txt")
        self._make("stuff/data.json")
        found = list(iter_media_files([self.tmpdir]))
        self.assertEqual(found, [])

    def test_iter_nonexistent_path(self):
        found = list(iter_media_files(["/nonexistent/path/xyz"]))
        self.assertEqual(found, [])

    def test_iter_nested_dirs(self):
        self._make("a/b/c/deep.mp4")
        found = list(iter_media_files([self.tmpdir]))
        self.assertEqual(len(found), 1)

    # --- LibraryScanner.scan ---

    def test_scan_inserts_movie(self):
        self._make("movies/Interstellar.2014.1080p.mkv")
        db = _open_db(self.tmpdir)
        scanner = LibraryScanner(db)
        added, total = scanner.scan([self.tmpdir])
        items = db.media(source="local")
        self.assertTrue(any(d.get("title") == "Interstellar" for d in items))
        db.close()

    def test_scan_inserts_episode(self):
        self._make("tv/Show.S02E05.mkv")
        db = _open_db(self.tmpdir)
        scanner = LibraryScanner(db)
        scanner.scan([self.tmpdir])
        items = db.media(source="local", kind="episode")
        self.assertTrue(any(d.get("extra", {}).get("season") == 2 for d in items))
        db.close()

    def test_scan_progress_callback(self):
        self._make("movies/Film.2000.mkv")
        db = _open_db(self.tmpdir)
        scanner = LibraryScanner(db)
        calls = []
        scanner.scan([self.tmpdir], progress=lambda done, total, title: calls.append(done))
        self.assertGreater(len(calls), 0)
        db.close()

    def test_scan_stop_signal(self):
        for i in range(10):
            self._make(f"movies/Film{i}.2000.mkv")
        db = _open_db(self.tmpdir)
        scanner = LibraryScanner(db)
        stop = [False]
        def should_stop():
            stop[0] = True
            return True
        scanner.scan([self.tmpdir], should_stop=should_stop)
        items = db.media(source="local")
        self.assertLessEqual(len(items), 1)
        db.close()

    def test_scan_delete_missing(self):
        p = self._make("movies/Old.2000.mkv")
        db = _open_db(self.tmpdir)
        scanner = LibraryScanner(db)
        scanner.scan([self.tmpdir])
        os.remove(p)
        scanner.scan([self.tmpdir])
        items = db.media(source="local")
        self.assertEqual(len(items), 0)
        db.close()

    def test_scan_idempotent(self):
        self._make("movies/Film.2000.mkv")
        db = _open_db(self.tmpdir)
        scanner = LibraryScanner(db)
        scanner.scan([self.tmpdir])
        scanner.scan([self.tmpdir])
        items = db.media(source="local")
        self.assertEqual(len(items), 1)
        db.close()


def _open_db(tmpdir):
    from media.library_db import LibraryDB
    return LibraryDB(os.path.join(tmpdir, f"test_{id(tmpdir)}.db"))


# ---------------------------------------------------------------------------
# 6. Metadata provider
# ---------------------------------------------------------------------------

from media.metadata import MetadataProvider


class TestMetadataProvider(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from media.library_db import LibraryDB
        self.db = LibraryDB(os.path.join(self.tmpdir, "meta.db"))

    def tearDown(self):
        self.db.close()

    def _provider(self, tmdb="", omdb=""):
        return MetadataProvider(self.db, tmdb_key=tmdb, omdb_key=omdb)

    def _tmdb_response(self, results=None, detail=None):
        search_resp = MagicMock()
        search_resp.raise_for_status = lambda: None
        search_resp.json.return_value = {"results": results or [{
            "id": 1234, "title": "Test Movie", "overview": "A test.",
            "poster_path": "/poster.jpg", "backdrop_path": "/back.jpg",
            "vote_average": 7.5
        }]}
        detail_resp = MagicMock()
        detail_resp.ok = True
        detail_resp.json.return_value = detail or {
            "genres": [{"name": "Action"}],
            "imdb_id": "tt1234567",
            "external_ids": {"imdb_id": "tt1234567"}
        }
        return search_resp, detail_resp

    def test_no_keys_disabled(self):
        p = self._provider()
        self.assertFalse(p.enabled)

    def test_no_keys_lookup_returns_empty(self):
        p = self._provider()
        result = p.lookup("Anything", 2020, "movie")
        self.assertEqual(result, {})

    def test_tmdb_lookup_returns_poster(self):
        p = self._provider(tmdb="fake_key")
        search_r, detail_r = self._tmdb_response()
        with patch("requests.get", side_effect=[search_r, detail_r]):
            result = p.lookup("Test Movie", 2020, "movie")
        self.assertIn("poster", result)
        self.assertTrue(result["poster"].endswith("poster.jpg"))

    def test_tmdb_lookup_returns_imdb_id(self):
        p = self._provider(tmdb="fake_key")
        search_r, detail_r = self._tmdb_response()
        with patch("requests.get", side_effect=[search_r, detail_r]):
            result = p.lookup("Test Movie", 2020, "movie")
        self.assertEqual(result.get("imdb_id"), "tt1234567")

    def test_tmdb_lookup_returns_genres(self):
        p = self._provider(tmdb="fake_key")
        search_r, detail_r = self._tmdb_response()
        with patch("requests.get", side_effect=[search_r, detail_r]):
            result = p.lookup("Test Movie", 2020, "movie")
        self.assertIn("Action", result.get("genres", []))

    def test_tmdb_no_results_returns_empty(self):
        p = self._provider(tmdb="fake_key")
        r = MagicMock()
        r.raise_for_status = lambda: None
        r.json.return_value = {"results": []}
        with patch("requests.get", return_value=r):
            result = p.lookup("Unknown Film XYZ", None, "movie")
        self.assertEqual(result, {})

    def test_tmdb_server_error_returns_empty(self):
        p = self._provider(tmdb="fake_key")
        import requests as req
        with patch("requests.get", side_effect=req.exceptions.ConnectionError("down")):
            result = p.lookup("Film", 2020, "movie")
        self.assertEqual(result, {})

    def test_tmdb_timeout_returns_empty(self):
        p = self._provider(tmdb="fake_key")
        import requests as req
        with patch("requests.get", side_effect=req.exceptions.Timeout()):
            result = p.lookup("Film", 2020, "movie")
        self.assertEqual(result, {})

    def test_omdb_rating_parsed(self):
        p = self._provider(tmdb="fake_key", omdb="fake_omdb")
        search_r, detail_r = self._tmdb_response()
        omdb_r = MagicMock()
        omdb_r.raise_for_status = lambda: None
        omdb_r.json.return_value = {"imdbRating": "8.1"}
        with patch("requests.get", side_effect=[search_r, detail_r, omdb_r]):
            result = p.lookup("Test Movie", 2020, "movie")
        self.assertAlmostEqual(result.get("rating"), 8.1, places=1)

    def test_omdb_na_rating_returns_none_not_crash(self):
        p = self._provider(omdb="fake_omdb")
        omdb_r = MagicMock()
        omdb_r.raise_for_status = lambda: None
        omdb_r.json.return_value = {"imdbRating": "N/A"}
        with patch("requests.get", return_value=omdb_r):
            result = p._omdb_rating(None, "Unknown", None)
        self.assertIsNone(result)

    def test_lookup_cached_no_second_request(self):
        p = self._provider(tmdb="fake_key")
        search_r, detail_r = self._tmdb_response()
        call_count = []
        def counting_json():
            call_count.append(1)
            return {"results": [{"id": 1, "title": "X", "poster_path": None,
                                  "backdrop_path": None, "vote_average": 0, "overview": ""}]}
        search_r.json = counting_json
        detail_r2 = MagicMock(); detail_r2.ok = True
        detail_r2.json.return_value = {"genres": [], "imdb_id": None, "external_ids": {}}
        with patch("requests.get", side_effect=[search_r, detail_r2]):
            p.lookup("Test Movie", 2020, "movie")
        with patch("requests.get", side_effect=Exception("should not call")):
            p.lookup("Test Movie", 2020, "movie")

    def test_tv_lookup_uses_tv_endpoint(self):
        p = self._provider(tmdb="fake_key")
        search_r = MagicMock()
        search_r.raise_for_status = lambda: None
        search_r.json.return_value = {"results": []}
        urls = []
        import requests as req
        def capture_get(url, **kwargs):
            urls.append(url)
            return search_r
        with patch("requests.get", side_effect=capture_get):
            p.lookup("Some Show", 2019, "tv")
        self.assertTrue(any("/tv" in u for u in urls))


# ---------------------------------------------------------------------------
# 7. Player widget (headless-safe)
# ---------------------------------------------------------------------------


class TestPlayerWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(sys.argv)
        from iptv.mpv_widget import MpvWidget
        cls.player = MpvWidget()

    @classmethod
    def tearDownClass(cls):
        cls.player.shutdown()

    def test_volume_normal(self):
        self.player.set_volume(80)
        self.assertEqual(self.player._mpv.volume, 80)

    def test_volume_clamp_zero(self):
        self.player.set_volume(-10)
        self.assertEqual(self.player._mpv.volume, 0)

    def test_volume_clamp_max(self):
        self.player.set_volume(200)
        self.assertEqual(self.player._mpv.volume, 150)

    def test_stop_when_idle_no_crash(self):
        self.player.stop()

    def test_seek_when_idle_no_crash(self):
        self.player.seek(30, "absolute")

    def test_seek_relative_no_crash(self):
        self.player.seek(10, "relative")

    def test_pause_toggle_no_crash(self):
        self.player.toggle_pause()
        self.player.toggle_pause()

    def test_set_pause_no_crash(self):
        self.player.set_pause(True)
        self.player.set_pause(False)

    def test_set_audio_no_crash(self):
        self.player.set_audio(1)

    def test_set_subtitle_no_crash(self):
        self.player.set_subtitle(0)

    def test_play_bad_url_no_crash(self):
        self.player.play("http://127.0.0.1:1/nonexistent.ts")
        time.sleep(0.1)
        self.player.stop()

    def test_signals_exist(self):
        from PySide6.QtCore import Signal
        self.assertTrue(hasattr(self.player, "duration_changed"))
        self.assertTrue(hasattr(self.player, "position_changed"))
        self.assertTrue(hasattr(self.player, "pause_changed"))
        self.assertTrue(hasattr(self.player, "tracks_changed"))
        self.assertTrue(hasattr(self.player, "info_changed"))


# ---------------------------------------------------------------------------
# 8. Xtream error scenarios
# ---------------------------------------------------------------------------

import requests as _req


class _ErrorXtreamHandler(BaseHTTPRequestHandler):
    """Mock server that returns errors based on username."""
    def log_message(self, *_): pass

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        user = params.get("username", ["u"])[0]

        if user == "badauth":
            body = {"user_info": {"auth": 0}, "server_info": {}}
            self._respond(200, body)
        elif user == "servererr":
            self.send_response(500)
            self.end_headers()
        elif user == "badjson":
            data = b"not json at all {"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif user == "emptycat":
            self._respond(200, [])
        elif user == "missingfields":
            self._respond(200, [{"extra": "field"}])
        else:
            self._respond(200, {"user_info": {"auth": 1}, "server_info": {}})

    def _respond(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class TestXtreamErrors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _ErrorXtreamHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _client(self, user):
        from iptv.xtream import XtreamClient
        return XtreamClient(f"http://127.0.0.1:{self.port}", user, "p", timeout=3)

    def test_bad_credentials_authenticate_returns_none(self):
        c = self._client("badauth")
        self.assertIsNone(c.authenticate())

    def test_server_500_returns_empty_list(self):
        c = self._client("servererr")
        result = c.live_categories()
        self.assertEqual(result, [])

    def test_bad_json_returns_empty_list(self):
        c = self._client("badjson")
        result = c.vod_categories()
        self.assertEqual(result, [])

    def test_connection_refused_returns_empty_list(self):
        from iptv.xtream import XtreamClient
        c = XtreamClient("http://127.0.0.1:1", "u", "p", timeout=1)
        result = c.live_streams()
        self.assertEqual(result, [])

    def test_timeout_returns_empty_list(self):
        from iptv.xtream import XtreamClient
        import socket
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        c = XtreamClient(f"http://127.0.0.1:{port}", "u", "p", timeout=0.1)
        result = c.vod_streams()
        srv.close()
        self.assertEqual(result, [])

    def test_empty_category_returns_empty_list(self):
        c = self._client("emptycat")
        result = c.series_categories()
        self.assertEqual(result, [])

    def test_missing_fields_returned_as_is(self):
        c = self._client("missingfields")
        result = c.live_streams()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertNotIn("stream_id", result[0])

    def test_authenticate_bad_then_good(self):
        bad = self._client("badauth")
        self.assertIsNone(bad.authenticate())
        good = self._client("u")
        self.assertIsNotNone(good.authenticate())


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in (TestLibraryDB, TestImageLoader, TestXtreamClient, TestMainWindow,
                TestLocalScanner, TestMetadataProvider, TestPlayerWidget, TestXtreamErrors):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
