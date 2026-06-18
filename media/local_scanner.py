"""Scan local and network (NFS/SMB-mounted) folders into the library.

Walks the configured paths, classifies files as video / music / photo, parses
a clean title + year (and season/episode for TV) from the filename, then
upserts each item into the library DB. Movies and episodes are enriched with
posters/overview/IMDb rating via the metadata provider when keys are set.

No heavy dependency (guessit etc.): a compact regex parser handles the common
scene/release naming. Designed to run inside a worker thread; emits progress
through an optional callback ``progress(done, total, title)``.
"""
import os
import re

VIDEO_EXT = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm", ".ts", ".m2ts", ".mpg", ".mpeg", ".wmv", ".flv"}
MUSIC_EXT = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".wma"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".heic"}

# SxxEyy / 1x02 episode markers
_EP_RE = re.compile(r"[._\s-]+[sS](\d{1,2})[eE](\d{1,2})", re.I)
_EP_RE2 = re.compile(r"[._\s-]+(\d{1,2})x(\d{2})", re.I)
_YEAR_RE = re.compile(r"(?:^|[.\s(_\-])((?:19|20)\d{2})(?=[.\s)_\-]|$)")
# junk tokens to strip from a title once year/quality starts
# word-boundaried so tokens like "tr"/"eng" can't match inside real words
# (e.g. the "tr" in "Matrix"). Everything from the first junk token is dropped.
_JUNK_RE = re.compile(
    r"\b(1080p|720p|2160p|480p|4k|bluray|brrip|bdrip|webrip|web-?dl|hdtv|"
    r"x264|x265|h264|h265|hevc|aac|ac3|dts|dd5|10bit|remux|hdr|imax|extended|"
    r"unrated|proper|repack|multi|dual|turkish|tr|eng|dubbed)\b.*", re.I)


def _clean_title(raw):
    name = re.sub(r"[._]+", " ", raw).strip()
    name = _JUNK_RE.sub("", name).strip(" -[](){}")
    return re.sub(r"\s{2,}", " ", name).strip()


def parse_filename(filename):
    """Return a dict describing the media item parsed from a filename stem."""
    stem = os.path.splitext(filename)[0]

    m = _EP_RE.search(stem) or _EP_RE2.search(stem)
    if m:
        show = _clean_title(stem[:m.start()])
        ym = _YEAR_RE.search(show)
        year = int(ym.group(1)) if ym else None
        if ym:
            show = _clean_title(show[:ym.start()]) or show
        return {"kind": "episode", "title": show,
                "season": int(m.group(1)), "episode": int(m.group(2)), "year": year}

    ym = _YEAR_RE.search(stem)
    year = int(ym.group(1)) if ym else None
    title = _clean_title(stem[:ym.start()] if ym else stem)
    return {"kind": "movie", "title": title or _clean_title(stem), "year": year}


def _kind_for(ext):
    if ext in VIDEO_EXT:
        return "video"
    if ext in MUSIC_EXT:
        return "music"
    if ext in IMAGE_EXT:
        return "photo"
    return None


def iter_media_files(paths):
    """Yield (abspath, ext_kind) for every media file under the given paths."""
    for base in paths:
        if not base or not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                kind = _kind_for(ext)
                if kind:
                    yield os.path.join(root, fn), kind


class LibraryScanner:
    def __init__(self, db, metadata=None):
        self._db = db
        self._meta = metadata

    def scan(self, paths, progress=None, should_stop=None):
        """Scan paths into the DB. Returns (added, total). Re-runnable; existing
        rows are updated, vanished files pruned."""
        files = list(iter_media_files(paths))
        total = len(files)
        seen = set()
        for i, (path, ext_kind) in enumerate(files):
            if should_stop and should_stop():
                break
            seen.add(path)
            item = self._build_item(path, ext_kind)
            self._db.upsert_media(item)
            if progress:
                progress(i + 1, total, item.get("title", ""))
        self._db.delete_missing("local", seen)
        return len(seen), total

    def _build_item(self, path, ext_kind):
        fn = os.path.basename(path)
        item = {
            "item_key": f"local:{path}",
            "source": "local",
            "path": path,
            "extra": {},
        }
        if ext_kind == "video":
            parsed = parse_filename(fn)
            item["kind"] = parsed["kind"]
            item["title"] = parsed["title"]
            item["year"] = parsed.get("year")
            if parsed["kind"] == "episode":
                item["extra"] = {"season": parsed.get("season"),
                                 "episode": parsed.get("episode")}
            self._enrich(item, parsed)
        elif ext_kind == "music":
            item["kind"] = "music"
            item["title"] = os.path.splitext(fn)[0]
            item["extra"] = {"album": os.path.basename(os.path.dirname(path))}
        else:  # photo
            item["kind"] = "photo"
            item["title"] = os.path.splitext(fn)[0]
            item["poster"] = path  # the image itself is its thumbnail
        return item

    def _enrich(self, item, parsed):
        if not (self._meta and self._meta.enabled):
            return
        kind = "movie" if parsed["kind"] == "movie" else "tv"
        meta = self._meta.lookup(parsed["title"], parsed.get("year"), kind)
        if not meta:
            return
        item["poster"] = meta.get("poster", "")
        item["backdrop"] = meta.get("backdrop", "")
        item["overview"] = meta.get("overview", "")
        item["rating"] = meta.get("rating")
        item["genres"] = meta.get("genres", [])
        item["extra"].update({"tmdb_id": meta.get("tmdb_id"),
                              "imdb_id": meta.get("imdb_id")})
