"""Plex source — pull movies and episodes into the library.

Uses the Plex HTTP API with X-Plex-Token auth (no separate user ID needed —
the token is already scoped to a user). Movies and episodes are fetched by
iterating library sections and upserted into the same ``media`` table the
local scanner and Emby client use.
"""
import logging

import requests

log = logging.getLogger(__name__)

UA = "QMediaCenter/0.1"
_TYPE_MOVIE = 1
_TYPE_EPISODE = 4


class PlexClient:
    def __init__(self, url, token, timeout=20):
        self.url = (url or "").strip().rstrip("/")
        self.token = (token or "").strip()
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": UA,
            "Accept": "application/json",
            "X-Plex-Token": self.token,
        })

    def _get(self, path, **params):
        r = self._session.get(f"{self.url}{path}", params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _sections(self):
        data = self._get("/library/sections")
        return (data.get("MediaContainer") or {}).get("Directory") or []

    def items(self):
        """Yield library rows for every movie and episode on the server."""
        for sec in self._sections():
            sec_type = sec.get("type")
            key = sec.get("key")
            if sec_type == "movie":
                yield from self._section_items(key, _TYPE_MOVIE, is_episode=False)
            elif sec_type == "show":
                yield from self._section_items(key, _TYPE_EPISODE, is_episode=True)

    def _section_items(self, key, plex_type, is_episode):
        data = self._get(f"/library/sections/{key}/all", type=plex_type)
        for it in (data.get("MediaContainer") or {}).get("Metadata") or []:
            row = self._to_row(it, is_episode)
            if row:
                yield row

    def _stream_url(self, it):
        try:
            part_key = it["Media"][0]["Part"][0]["key"]
            return f"{self.url}{part_key}?X-Plex-Token={self.token}"
        except (KeyError, IndexError, TypeError):
            return ""

    def _poster_url(self, thumb):
        return f"{self.url}{thumb}?X-Plex-Token={self.token}" if thumb else ""

    def _to_row(self, it, is_episode):
        iid = it.get("ratingKey")
        stream = self._stream_url(it)
        if not iid or not stream:
            return None
        genres = [g["tag"] for g in (it.get("Genre") or []) if g.get("tag")]
        rating = it.get("rating") or it.get("audienceRating")
        row = {
            "item_key": f"plex:{iid}",
            "source": "plex",
            "kind": "episode" if is_episode else "movie",
            "title": it.get("title") or "?",
            "year": it.get("year"),
            "path": stream,
            "poster": self._poster_url(it.get("thumb")),
            "overview": it.get("summary") or "",
            "rating": float(rating) if rating is not None else None,
            "genres": genres,
            "extra": {"plex_id": iid},
        }
        if is_episode:
            show = it.get("grandparentTitle") or ""
            row["extra"].update({
                "show": show,
                "season": it.get("parentIndex"),
                "episode": it.get("index"),
            })
            if show:
                row["title"] = f"{show} — {row['title']}"
        return row


def sync_plex(db, cfg):
    """Pull the configured Plex server into the library DB.

    Returns the number of items imported. Raises on connection/auth errors.
    """
    client = PlexClient(cfg.get("url"), cfg.get("token"))
    if not (client.url and client.token):
        return 0
    seen = set()
    count = 0
    for row in client.items():
        db.upsert_media(row)
        seen.add(row["path"])
        count += 1
    db.delete_missing("plex", seen)
    log.info("Plex sync: imported %d items", count)
    return count
