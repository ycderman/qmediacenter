# Changelog

All notable changes to QMediaCenter are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- `pyproject.toml` — standard Python packaging, `pip install .` support
- `ThemeManager` with Breeze Light and Breeze Dark themes
- `themes/breeze-light.qss` and `themes/breeze-dark.qss` with `@ACCENT@` placeholder
- `tests/` directory with pytest-based test suite (library_db, m3u, themes, packaging metadata)
- `docs/ROADMAP_PROFESSIONALIZATION.md` — architecture analysis and distro packaging roadmap
- PyInstaller spec moved to `packaging/pyinstaller/qmediacenter.spec`

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

[Unreleased]: https://github.com/ycderman/qmediacenter/compare/v0.6.7...HEAD
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
