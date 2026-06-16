"""Profile persistence (JSON in ~/.config/qtiptv)."""
import json
import os

CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "qtiptv"
)
PROFILES_FILE = os.path.join(CONFIG_DIR, "profiles.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")


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
        return {"download_dir": os.path.expanduser("~/Downloads"), "volume": 100}


def save_settings(settings):
    _ensure_dir()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
