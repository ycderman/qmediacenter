"""Emby / Jellyfin source — pull a server's movies and episodes into the library.

Both Emby and Jellyfin accept the API key as an ``api_key`` query parameter and
share the same item/image/stream endpoints used here, so one client covers both.
Items are upserted into the same ``media`` table the local scanner uses, with
``source="emby"`` and a stream URL as their ``path`` so playback just works.
"""
import logging

import requests

log = logging.getLogger(__name__)

UA = "QtIPTV/0.1"
# Fields we need to build a library row in one request.
_FIELDS = "Overview,Genres,ProductionYear,CommunityRating,SeriesName,ProviderIds"
_TYPES = "Movie,Episode"


class EmbyClient:
    def __init__(self, url, api_key, user_id="", timeout=20):
        self.url = (url or "").strip().rstrip("/")
        self.api_key = (api_key or "").strip()
        self.user_id = (user_id or "").strip()
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": UA})

    # ---- low level ----------------------------------------------------
    def _get(self, path, **params):
        params["api_key"] = self.api_key
        r = self._session.get(f"{self.url}{path}", params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _resolve_user(self):
        """Emby needs a user id to list items; fall back to the first account."""
        if self.user_id:
            return self.user_id
        users = self._get("/Users") or []
        if users:
            self.user_id = users[0].get("Id", "")
        return self.user_id

    # ---- public -------------------------------------------------------
    def items(self):
        """Yield library rows (dicts) for every movie and episode on the server."""
        uid = self._resolve_user()
        if not uid:
            raise RuntimeError("Emby: no user id and none could be resolved")
        data = self._get(
            f"/Users/{uid}/Items",
            Recursive="true", IncludeItemTypes=_TYPES, Fields=_FIELDS,
            ImageTypeLimit=1, EnableImageTypes="Primary",
        )
        for it in (data.get("Items") or []):
            row = self._to_row(it)
            if row:
                yield row

    def _image_url(self, item_id, tag):
        q = f"?api_key={self.api_key}&maxHeight=480"
        if tag:
            q += f"&tag={tag}"
        return f"{self.url}/Items/{item_id}/Images/Primary{q}"

    def stream_url(self, item_id):
        # Static=true asks the server to direct-play the original file.
        return (f"{self.url}/Videos/{item_id}/stream"
                f"?Static=true&api_key={self.api_key}")

    def _to_row(self, it):
        iid = it.get("Id")
        if not iid:
            return None
        is_episode = it.get("Type") == "Episode"
        tag = (it.get("ImageTags") or {}).get("Primary")
        rating = it.get("CommunityRating")
        row = {
            "item_key": f"emby:{iid}",
            "source": "emby",
            "kind": "episode" if is_episode else "movie",
            "title": it.get("Name") or "?",
            "year": it.get("ProductionYear"),
            "path": self.stream_url(iid),
            "poster": self._image_url(iid, tag) if tag else "",
            "overview": it.get("Overview") or "",
            "rating": float(rating) if rating is not None else None,
            "genres": it.get("Genres") or [],
            "extra": {"emby_id": iid},
        }
        if is_episode:
            row["extra"].update({
                "show": it.get("SeriesName") or "",
                "season": it.get("ParentIndexNumber"),
                "episode": it.get("IndexNumber"),
            })
            if it.get("SeriesName"):
                row["title"] = f"{it['SeriesName']} — {row['title']}"
        return row


def sync_emby(db, cfg):
    """Pull the configured Emby server into the library DB.

    Returns the number of items imported. Stale emby rows (deleted on the
    server) are pruned. Raises on connection/auth errors so the caller can
    surface them.
    """
    client = EmbyClient(cfg.get("url"), cfg.get("api_key"), cfg.get("user_id"))
    if not (client.url and client.api_key):
        return 0
    seen = set()
    count = 0
    for row in client.items():
        db.upsert_media(row)
        seen.add(row["path"])
        count += 1
    db.delete_missing("emby", seen)
    log.info("Emby sync: imported %d items", count)
    return count
