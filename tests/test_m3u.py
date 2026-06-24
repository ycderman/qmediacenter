"""Tests for iptv.m3u — M3U parser and M3uClient."""
import os
import tempfile

import pytest

from iptv.m3u import parse, M3uClient

SAMPLE_M3U = """\
#EXTM3U
#EXTINF:-1 tvg-id="bbc1" tvg-logo="https://example.com/bbc.png" group-title="News",BBC One
https://stream.example.com/bbc1
#EXTINF:-1 group-title="News",CNN International
https://stream.example.com/cnn
#EXTINF:-1 group-title="Sport",ESPN
https://stream.example.com/espn
#EXTINF:-1,No Group Channel
https://stream.example.com/nogroup
"""


@pytest.fixture
def m3u_file(tmp_path):
    p = tmp_path / "test.m3u"
    p.write_text(SAMPLE_M3U, encoding="utf-8")
    return str(p)


class TestM3uParser:
    def test_channel_count(self, m3u_file):
        channels = parse(m3u_file)
        assert len(channels) == 4

    def test_name_parsing(self, m3u_file):
        channels = parse(m3u_file)
        names = [c["name"] for c in channels]
        assert "BBC One" in names
        assert "CNN International" in names

    def test_group_parsing(self, m3u_file):
        channels = parse(m3u_file)
        groups = {c["group"] for c in channels}
        assert "News" in groups
        assert "Sport" in groups

    def test_logo_parsing(self, m3u_file):
        channels = parse(m3u_file)
        bbc = next(c for c in channels if c["name"] == "BBC One")
        assert bbc["logo"] == "https://example.com/bbc.png"

    def test_url_as_stream_id(self, m3u_file):
        channels = parse(m3u_file)
        for ch in channels:
            assert ch["stream_id"] == ch["url"]

    def test_no_group_fallback(self, m3u_file):
        channels = parse(m3u_file)
        no_group = next(c for c in channels if c["name"] == "No Group Channel")
        assert no_group["group"] == ""


class TestM3uClient:
    def test_live_categories(self, m3u_file):
        client = M3uClient("test", m3u_file)
        cats = client.live_categories()
        ids = [c["category_id"] for c in cats]
        assert "News" in ids
        assert "Sport" in ids

    def test_live_streams_all(self, m3u_file):
        client = M3uClient("test", m3u_file)
        streams = client.live_streams()
        assert len(streams) == 4

    def test_live_streams_filtered(self, m3u_file):
        client = M3uClient("test", m3u_file)
        news = client.live_streams(category_id="News")
        assert len(news) == 2
        names = [s["name"] for s in news]
        assert "BBC One" in names
        assert "CNN International" in names

    def test_live_url_passthrough(self, m3u_file):
        client = M3uClient("test", m3u_file)
        url = "https://stream.example.com/test"
        assert client.live_url(url) == url

    def test_authenticate_ok(self, m3u_file):
        client = M3uClient("test", m3u_file)
        assert client.authenticate()

    def test_authenticate_bad_path(self):
        client = M3uClient("bad", "/nonexistent/path.m3u")
        assert not client.authenticate()

    def test_stubs_return_empty(self, m3u_file):
        client = M3uClient("test", m3u_file)
        assert client.vod_categories() == []
        assert client.vod_streams() == []
        assert client.vod_info() == {}
        assert client.series_categories() == []
        assert client.movie_url() == ""
