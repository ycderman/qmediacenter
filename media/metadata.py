"""Metadata enrichment: posters, overviews and IMDb ratings.

IMDb has no public API, so we use two free services:
  * TMDb (themoviedb.org) — search by title/year, posters, backdrops,
    overview, genres and the linked IMDb id. Needs a free API key.
  * OMDb (omdbapi.com)    — returns the actual `imdbRating` string for an
    IMDb id. Needs a free API key.

Both are optional: without keys the library still works, just without art or
ratings. Results are cached in the library DB so a folder rescan is cheap.
"""
import logging

import requests

log = logging.getLogger(__name__)

TMDB_API = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p"
OMDB_API = "https://www.omdbapi.com/"
_TIMEOUT = 8
_CACHE_AGE = 60 * 60 * 24 * 30  # 30 days


class MetadataProvider:
    def __init__(self, db, tmdb_key="", omdb_key=""):
        self._db = db
        self._tmdb = (tmdb_key or "").strip()
        self._omdb = (omdb_key or "").strip()

    @property
    def enabled(self):
        return bool(self._tmdb or self._omdb)

    def poster_url(self, path, size="w342"):
        return f"{TMDB_IMG}/{size}{path}" if path else ""

    def lookup(self, title, year=None, kind="movie"):
        """Return an enrichment dict (poster/backdrop/overview/rating/ids) or {}.

        kind: "movie" or "tv". Cached by (kind,title,year).
        """
        key = f"meta:{kind}:{title.lower()}:{year or ''}"
        cached = self._db.cache_get(key, max_age=_CACHE_AGE)
        if cached is not None:
            return cached

        result = {}
        if self._tmdb:
            result = self._tmdb_lookup(title, year, kind)
        # Fill the real IMDb rating from OMDb when we have an imdb id or title.
        if self._omdb:
            rating = self._omdb_rating(result.get("imdb_id"), title, year)
            if rating is not None:
                result["rating"] = rating

        self._db.cache_put(key, result)
        return result

    # ---- TMDb ---------------------------------------------------------
    def _tmdb_lookup(self, title, year, kind):
        try:
            ep = "movie" if kind == "movie" else "tv"
            params = {"api_key": self._tmdb, "query": title, "include_adult": "false"}
            if year:
                params["year" if kind == "movie" else "first_air_date_year"] = year
            r = requests.get(f"{TMDB_API}/search/{ep}", params=params, timeout=_TIMEOUT)
            r.raise_for_status()
            hits = r.json().get("results") or []
            if not hits:
                return {}
            hit = hits[0]
            out = {
                "tmdb_id": hit.get("id"),
                "title": hit.get("title") or hit.get("name") or title,
                "overview": hit.get("overview", ""),
                "poster": self.poster_url(hit.get("poster_path"), "w342"),
                "backdrop": self.poster_url(hit.get("backdrop_path"), "w780"),
                "rating": hit.get("vote_average"),   # TMDb rating; OMDb overrides below
                "genres": [],
            }
            # one extra call to resolve the IMDb id + genres
            det = requests.get(
                f"{TMDB_API}/{ep}/{hit['id']}",
                params={"api_key": self._tmdb,
                        "append_to_response": "external_ids"}, timeout=_TIMEOUT)
            if det.ok:
                dj = det.json()
                out["genres"] = [g["name"] for g in dj.get("genres", [])]
                out["imdb_id"] = (dj.get("imdb_id")
                                  or dj.get("external_ids", {}).get("imdb_id"))
            return out
        except Exception as e:
            log.warning("TMDb lookup failed for %r: %s", title, e)
            return {}

    # ---- OMDb (IMDb rating) ------------------------------------------
    def _omdb_rating(self, imdb_id, title, year):
        try:
            params = {"apikey": self._omdb}
            if imdb_id:
                params["i"] = imdb_id
            else:
                params["t"] = title
                if year:
                    params["y"] = year
            r = requests.get(OMDB_API, params=params, timeout=_TIMEOUT)
            r.raise_for_status()
            val = r.json().get("imdbRating")
            return float(val) if val and val != "N/A" else None
        except Exception as e:
            log.debug("OMDb rating failed for %r: %s", title, e)
            return None
