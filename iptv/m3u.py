"""M3U playlist parser and client.

Implements the same live-stream interface as XtreamClient so
main_window.py can treat M3U and Xtream profiles identically.
"""
import logging
import re
import urllib.request

log = logging.getLogger(__name__)


_EXTINF = re.compile(r'#EXTINF:[^,]*,?(.*)')
_ATTR   = re.compile(r'([\w-]+)="([^"]*)"')


def _fetch(url_or_path: str) -> str:
    if url_or_path.startswith(("http://", "https://")):
        req = urllib.request.Request(url_or_path,
                                     headers={"User-Agent": "QMediaCenter/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    with open(url_or_path, encoding="utf-8", errors="replace") as f:
        return f.read()


def parse(url_or_path: str) -> list[dict]:
    """Return list of channel dicts from a M3U playlist."""
    text = _fetch(url_or_path)
    channels = []
    pending: dict | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            attrs = dict(_ATTR.findall(line))
            m = _EXTINF.search(line)
            name = m.group(1).strip() if m else attrs.get("tvg-name", "")
            pending = {
                "name":      name or attrs.get("tvg-name", "Unknown"),
                "group":     attrs.get("group-title", ""),
                "logo":      attrs.get("tvg-logo", ""),
                "tvg_id":    attrs.get("tvg-id", ""),
            }
        elif line.startswith("#"):
            continue
        elif pending is not None:
            pending["url"] = line
            pending["stream_id"] = line  # stream_id == url for M3U
            channels.append(pending)
            pending = None
    return channels


class M3uClient:
    """Drop-in replacement for XtreamClient's live-stream methods."""

    def __init__(self, name: str, url_or_path: str):
        self.name = name
        self.url  = url_or_path
        self._channels: list[dict] | None = None

    def _ensure(self):
        if self._channels is None:
            log.info("M3U: fetching %s", self.url)
            self._channels = parse(self.url)
            log.info("M3U: loaded %d channels", len(self._channels))

    def authenticate(self) -> bool:
        try:
            self._ensure()
            return True
        except Exception as e:
            log.error("M3U: authenticate failed: %s", e)
            return False

    def live_categories(self) -> list[dict]:
        try:
            self._ensure()
        except Exception as e:
            log.error("M3U live_categories failed: %s", e)
            return []
        seen = {}
        for ch in self._channels:
            g = ch.get("group") or "Uncategorized"
            if g not in seen:
                seen[g] = {"category_id": g, "category_name": g}
        return list(seen.values())

    def live_streams(self, category_id=None) -> list[dict]:
        self._ensure()
        result = []
        for ch in self._channels:
            g = ch.get("group") or "Uncategorized"
            if category_id is None or g == category_id:
                result.append({
                    "name":         ch["name"],
                    "stream_id":    ch["stream_id"],
                    "stream_icon":  ch.get("logo", ""),
                    "group":        g,
                    "url":          ch["url"],
                })
        return result

    def live_url(self, stream_id) -> str:
        return stream_id

    # Stubs so the rest of main_window does not crash if accidentally called
    def vod_categories(self):    return []
    def vod_streams(self, *a):   return []
    def vod_info(self, *a):      return {}
    def series_categories(self): return []
    def series(self, *a):        return []
    def series_info(self, *a):   return {}
    def movie_url(self, *a):     return ""
    def series_url(self, *a):    return ""
