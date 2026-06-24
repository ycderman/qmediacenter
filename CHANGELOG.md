# Changelog

All notable changes to QMediaCenter are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [0.7.0] — 2026-06-25

### Added
- Nix development packaging (`packaging/nix/`) — `buildPythonApplication` derivation;
  installs `.desktop`, metainfo, and icon; Wayland plugin path wired via `wrapQtAppsHook`
- Flatpak development manifest (`packaging/flatpak/`) — builds via pip install so
  `importlib.resources` and `dist-info` entry points work correctly inside the sandbox;
  uses `io.qt.PySide.BaseApp//6.8` + `org.kde.Platform//6.8`
- Installable Python package (`pyproject.toml`) — `pip install .`, `pip install -e .`,
  `pipx install`, and wheel install all work
- Breeze Dark theme alongside Breeze Light; theme switcher in Sources → Appearance
- `tests/` directory with pytest suite (63 tests covering library DB, M3U parser,
  themes, packaging metadata, and resource access)
- `--version` and `--help` CLI flags that work without a display server
- CI: pytest job, wheel build + smoke test job, `qmediacenter --version` verified in CI

### Fixed
- Icon loaded from package bytes (`QPixmap.loadFromData`) instead of a context-manager
  temp file — eliminates a race condition when resources are inside a zip importer
- Theme QSS files and app icon now accessible via `importlib.resources` after wheel
  install (no longer path-relative only)

### Changed
- AppStream `releases` updated to cover 0.5.0 through 0.7.0
- PyInstaller spec moved to `packaging/pyinstaller/`

---

## [0.6.7] — 2026-06-24

### Fixed
- Video output blank (no picture) inside Flatpak: `fbo-format=rgba8` avoids GL `INVALID_ENUM`
  on texture creation with Mesa

## [0.6.6] — 2026-06-24

### Fixed
- Revert ES2 render context — `es2=True` in `MpvOpenGLInitParams` broke the player widget

## [0.6.5] — 2026-06-24

### Fixed
- Removed `profile=fast` from mpv init — it zeroed `analyzeduration`, preventing codec
  parameter detection on many HLS streams

## [0.6.4] — 2026-06-24

### Added
- mpv warn-level logging to stderr for diagnostics

## [0.6.3] — 2026-06-23

### Changed
- Live stream buffer reduced from 200 MiB to 4 MiB (`demuxer-max-bytes`) — faster channel start
- `cache-pause=False` set globally; per-play live/VOD buffer sizes

## [0.6.2] — 2026-06-23

### Fixed
- M3U client not applied before `_set_mode()` — channels didn't appear after adding M3U source

## [0.6.1] — 2026-06-23

### Added
- Debug logging in `M3uClient` for fetching and load count

## [0.6.0] — 2026-06-23

### Added
- M3U playlist support (`iptv/m3u.py`, `M3uClient`) alongside Xtream IPTV
- M3U tab in Sources dialog (URL and file picker)
- M3U profile persistence (`iptv/config.py`)
- IPTV profile combo in main nav (switches between Xtream and M3U sources)
- VOD/Series buttons hidden for M3U profiles (live-only)

### Changed
- App starts without login dialog — IPTV configured via Sources menu only

### Fixed
- Removed `ytdl` mpv option (removed in mpv 0.39)
- Removed `osc` mpv option (removed in mpv 0.39)

## [0.5.4] — 2026-06-22

### Added
- AppStream `metainfo.xml`, `desktop` file in Flatpak manifest
- CI: `.deb` and `.rpm` build/smoke test jobs

## [0.5.2] — 2026-06-21

### Added
- Disk-cached IPTV stream list (2 h TTL via `meta_cache`)
- Background auto-refresh after categories load
- Scroll pagination for Recently Added (250/page, up to 1 000)

## [0.5.0] — 2026-06-20

### Added
- Flatpak manifest (`packaging/io.github.ycderman.qmediacenter.yaml`)
- KDE Plasma integration: MPRIS2, ScreenSaver inhibit
- Home screen rows: Continue Watching, Favourites, Recently Added, Movies by source
- Source badges on home screen items
- Alphabetical sorting for movies and series

[Unreleased]: https://github.com/ycderman/qmediacenter/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/ycderman/qmediacenter/compare/v0.6.7...v0.7.0
[0.6.7]: https://github.com/ycderman/qmediacenter/compare/v0.6.6...v0.6.7
[0.6.6]: https://github.com/ycderman/qmediacenter/compare/v0.6.5...v0.6.6
[0.6.5]: https://github.com/ycderman/qmediacenter/compare/v0.6.4...v0.6.5
[0.6.4]: https://github.com/ycderman/qmediacenter/compare/v0.6.3...v0.6.4
[0.6.3]: https://github.com/ycderman/qmediacenter/compare/v0.6.2...v0.6.3
[0.6.2]: https://github.com/ycderman/qmediacenter/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/ycderman/qmediacenter/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/ycderman/qmediacenter/compare/v0.5.4...v0.6.0
[0.5.4]: https://github.com/ycderman/qmediacenter/compare/v0.5.2...v0.5.4
[0.5.2]: https://github.com/ycderman/qmediacenter/compare/v0.5.0...v0.5.2
[0.5.0]: https://github.com/ycderman/qmediacenter/releases/tag/v0.5.0
