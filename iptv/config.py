"""Profile persistence (JSON in ~/.config/qtiptv)."""
import json
import os

_CONFIG_ROOT = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
CONFIG_DIR = os.path.join(_CONFIG_ROOT, "qmediacenter")
_LEGACY_DIR = os.path.join(_CONFIG_ROOT, "qtiptv")


def _migrate_legacy():
    """One-time rename of the old ~/.config/qtiptv data into the new dir."""
    if os.path.isdir(_LEGACY_DIR) and not os.path.exists(CONFIG_DIR):
        try:
            os.rename(_LEGACY_DIR, CONFIG_DIR)
        except OSError:
            pass


_migrate_legacy()
PROFILES_FILE     = os.path.join(CONFIG_DIR, "profiles.json")
M3U_PROFILES_FILE = os.path.join(CONFIG_DIR, "m3u_profiles.json")
SETTINGS_FILE     = os.path.join(CONFIG_DIR, "settings.json")


def _ensure_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_profiles():
    try:
        with open(PROFILES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_profiles(profiles):
    _ensure_dir()
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)


def load_m3u_profiles():
    try:
        with open(M3U_PROFILES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_m3u_profiles(profiles):
    _ensure_dir()
    with open(M3U_PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)


def download_dir():
    """Resolve the desktop's Downloads folder robustly across locales
    (e.g. ~/İndirilenler). QStandardPaths is unreliable in a minimal app
    environment, so read XDG settings directly."""
    env = os.environ.get("XDG_DOWNLOAD_DIR")
    if env:
        return os.path.expandvars(env)
    udd = os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
        "user-dirs.dirs")
    try:
        with open(udd, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("XDG_DOWNLOAD_DIR"):
                    val = line.split("=", 1)[1].strip().strip('"')
                    return os.path.expandvars(val)
    except OSError:
        pass
    fallback = os.path.expanduser("~/İndirilenler")
    return fallback if os.path.isdir(fallback) else os.path.expanduser("~/Downloads")


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # No download_dir here on purpose: an empty value makes the caller fall
        # back to download_dir() (locale-correct ~/İndirilenler).
        return {"volume": 100}


def save_settings(settings):
    _ensure_dir()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


# ---- media-center configuration ---------------------------------------
# Stored inside settings.json so existing persistence keeps working.
#   tmdb_key / omdb_key : metadata + IMDb rating API keys (optional)
#   library_paths       : list of local/NFS folders to scan
#   emby / plex         : {"url":..., "api_key"/"token":..., "user_id":...}

def media_config():
    s = load_settings()
    return {
        "tmdb_key": s.get("tmdb_key", ""),
        "omdb_key": s.get("omdb_key", ""),
        "library_paths": s.get("library_paths", []),
        "emby": s.get("emby", {}),
        "plex": s.get("plex", {}),
    }


def save_media_config(cfg):
    s = load_settings()
    for key in ("tmdb_key", "omdb_key", "library_paths", "emby", "plex"):
        if key in cfg:
            s[key] = cfg[key]
    save_settings(s)
