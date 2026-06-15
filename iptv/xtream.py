"""Minimal Xtream Codes API client."""
import requests
import logging

log = logging.getLogger(__name__)


class XtreamClient:
    def __init__(self, host, username, password, timeout=15):
        # host may be "http://server:port" or "server:port"
        host = host.strip().rstrip("/")
        if not host.startswith(("http://", "https://")):
            host = "http://" + host
        self.host = host
        self.username = username
        self.password = password
        self.timeout = timeout
        self._session = requests.Session()

    # ---- low level ----------------------------------------------------
    def _api(self, action, **params):
        url = f"{self.host}/player_api.php"
        q = {"username": self.username, "password": self.password}
        if action:
            q["action"] = action
        q.update(params)
        try:
            r = self._session.get(url, params=q, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning("Xtream API '%s' failed: %s", action, e)
            return None

    # ---- auth ---------------------------------------------------------
    def authenticate(self):
        data = self._api(None)
        if isinstance(data, dict) and data.get("user_info", {}).get("auth") == 1:
            return data
        return None

    # ---- categories ---------------------------------------------------
    def live_categories(self):
        return self._api("get_live_categories") or []

    def vod_categories(self):
        return self._api("get_vod_categories") or []

    def series_categories(self):
        return self._api("get_series_categories") or []

    # ---- streams ------------------------------------------------------
    def live_streams(self, category_id=None):
        p = {"category_id": category_id} if category_id else {}
        return self._api("get_live_streams", **p) or []

    def vod_streams(self, category_id=None):
        p = {"category_id": category_id} if category_id else {}
        return self._api("get_vod_streams", **p) or []

    def series(self, category_id=None):
        p = {"category_id": category_id} if category_id else {}
        return self._api("get_series", **p) or []

    def series_info(self, series_id):
        return self._api("get_series_info", series_id=series_id) or {}

    def vod_info(self, vod_id):
        return self._api("get_vod_info", vod_id=vod_id) or {}

    # ---- stream URLs --------------------------------------------------
    def live_url(self, stream_id, ext="ts"):
        return f"{self.host}/live/{self.username}/{self.password}/{stream_id}.{ext}"

    def movie_url(self, stream_id, ext="mp4"):
        return f"{self.host}/movie/{self.username}/{self.password}/{stream_id}.{ext}"

    def series_url(self, episode_id, ext="mp4"):
        return f"{self.host}/series/{self.username}/{self.password}/{episode_id}.{ext}"
