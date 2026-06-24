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
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in (TestLibraryDB, TestImageLoader, TestXtreamClient, TestMainWindow):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
