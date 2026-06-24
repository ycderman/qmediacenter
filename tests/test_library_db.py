"""Tests for media.library_db."""
import time

import pytest

from tests.conftest import make_vod


class TestLibraryDB:
    def test_progress_round_trip(self, tmp_db):
        tmp_db.save_progress("key1", 0.42, 120.0)
        pos, dur = tmp_db.get_progress("key1")
        assert abs(pos - 0.42) < 0.01
        assert abs(dur - 120.0) < 0.1

    def test_progress_missing_key(self, tmp_db):
        pos, dur = tmp_db.get_progress("nonexistent")
        assert pos == 0.0
        assert dur == 0.0

    def test_watched(self, tmp_db):
        assert not tmp_db.is_watched("k1")
        tmp_db.mark_watched("k1")
        assert tmp_db.is_watched("k1")
        tmp_db.unmark_watched("k1")
        assert not tmp_db.is_watched("k1")

    def test_watched_keys_bulk(self, tmp_db):
        tmp_db.mark_watched("a")
        tmp_db.mark_watched("b")
        result = tmp_db.watched_keys(["a", "b", "c"])
        assert "a" in result
        assert "b" in result
        assert "c" not in result

    def test_favorites(self, tmp_db):
        tmp_db.toggle_favorite("fav1")
        favs = tmp_db.favorites(10)
        assert any(d.get("item_key") == "fav1" for d in favs)
        tmp_db.toggle_favorite("fav1")
        favs2 = tmp_db.favorites(10)
        assert not any(d.get("item_key") == "fav1" for d in favs2)

    def test_cache_put_and_get(self, tmp_db):
        payload = {"hello": "world", "nums": [1, 2, 3]}
        tmp_db.cache_put("mykey", payload)
        result = tmp_db.cache_get("mykey")
        assert result == payload

    def test_cache_get_missing(self, tmp_db):
        assert tmp_db.cache_get("no_such_key") is None

    def test_cache_ttl_expired(self, tmp_db):
        tmp_db.cache_put("ttl_key", {"x": 1})
        time.sleep(0.05)
        result = tmp_db.cache_get("ttl_key", max_age=0.01)
        assert result is None

    def test_cache_ttl_valid(self, tmp_db):
        tmp_db.cache_put("ttl_key2", {"x": 2})
        result = tmp_db.cache_get("ttl_key2", max_age=3600)
        assert result is not None

    def test_cache_exists_true(self, tmp_db):
        tmp_db.cache_put("exist_key", [1, 2])
        assert tmp_db.cache_exists("exist_key", max_age=3600)

    def test_cache_exists_false_missing(self, tmp_db):
        assert not tmp_db.cache_exists("missing_key")

    def test_cache_exists_false_expired(self, tmp_db):
        tmp_db.cache_put("exp_key", [1])
        time.sleep(0.05)
        assert not tmp_db.cache_exists("exp_key", max_age=0.01)

    def test_cache_overwrite(self, tmp_db):
        tmp_db.cache_put("ow", {"v": 1})
        tmp_db.cache_put("ow", {"v": 2})
        result = tmp_db.cache_get("ow")
        assert result["v"] == 2

    def test_large_payload(self, tmp_db):
        big = make_vod(1000)
        tmp_db.cache_put("big", big)
        result = tmp_db.cache_get("big")
        assert len(result) == 1000
        assert result[0]["name"] == big[0]["name"]
