# QMediaCenter — Professionalization Roadmap

> Generated: 2026-06-24 | Status: Sprint 1 in progress

---

## 1. Current Architecture

```
main.py                 Entry point: QApplication + auto-login + MainWindow
iptv/
  xtream.py             Xtream Codes API (auth, live, VOD, series)
  m3u.py                M3U/M3U8 parser and drop-in client
  config.py             JSON profiles, settings, media config, M3U profiles
  mpv_widget.py         QOpenGLWidget wrapping libmpv render API
  downloader.py         Resumable threaded HTTP downloader
  image_loader.py       Async poster loader with disk LRU cache
media/
  library_db.py         SQLite: positions, favourites, scanned items, meta cache
  metadata.py           TMDb + OMDb (posters, overviews, IMDb ratings)
  local_scanner.py      Filesystem scanner + filename parser
  emby.py               Emby/Jellyfin browse + play
  plex.py               Plex browse + play
  mpris.py              MPRIS2 + ScreenSaver inhibit (dbus optional)
ui/
  login_dialog.py       Xtream profile entry (now unused at startup)
  sources_dialog.py     Sources & settings dialog
  main_window.py        1 649-line monolith: nav, all pages, player, home screen
  style.py              KDE Breeze Light QSS + desktop accent helper
data/
  qmediacenter.png      App icon (256×256)
  io.github.ycderman.qmediacenter.metainfo.xml  AppStream
packaging/
  qmediacenter.desktop  XDG desktop entry
  build.sh              PyInstaller + fpm build helper
  qmediacenter.sh       Flatpak launcher wrapper
  io.github.ycderman.qmediacenter.yaml  Flatpak manifest
  postinst / postrm     Deb/rpm hooks
qmediacenter.spec       PyInstaller spec (naming clash with RPM spec)
package.nix             Nix derivation (named "qplayer", v0.1.0, outdated)
test_ui.py              1 154-line monolithic unittest file
.github/workflows/ci.yml  CI: syntax, lint, tests, PyInstaller, deb/rpm
```

**Source count:** ~5 500 lines Python across 14 modules.

**Runtime deps:** PySide6, python-mpv, PyOpenGL, requests, yt-dlp, dbus-python (optional), PyGObject (optional).

---

## 2. Code Quality Problems

| # | Problem | Severity |
|---|---------|----------|
| 1 | `MainWindow` (1 649 lines) handles navigation, source logic, library, player, home screen | Critical |
| 2 | `package.nix` references `qplayer` v0.1.0 — completely outdated | High |
| 3 | `qmediacenter.spec` name collides with RPM spec convention | High |
| 4 | No `pyproject.toml` — not installable as standard Python package | High |
| 5 | `QtIPTV/0.1` user-agent in `mpv_widget.py` | Medium |
| 6 | Magic strings scattered (buffer sizes, TTLs, cache limits) | Medium |
| 7 | No DB migration system — schema changes are destructive | High |
| 8 | `test_ui.py` is a 1 154-line monolith | Medium |
| 9 | No entry point — must run as `python main.py` | High |
| 10 | `profile["name"]` KeyError risk (should be `.get()`) | Medium |
| 11 | Credentials logged in some error paths | High |
| 12 | Config files have no permission hardening (0600) | Medium |
| 13 | No central error handling for network calls | Medium |
| 14 | Worker threads have no guaranteed cleanup path | Medium |

---

## 3. UI/UX Problems

- Single theme (Breeze Light) — no dark mode, no user choice
- No empty-state screens (no IPTV source, no local folder, no search results)
- No loading skeleton/placeholder on poster grid
- No error state component
- Player controls bar adequate but lacks fullscreen auto-hide
- No keyboard shortcut reference in UI
- Poster grid items have no "watched" badge or "source" badge at item level
- Window title does not update to playing item name

---

## 4. Theme/Skin System Gaps

- One hardcoded QSS string in `ui/style.py`
- No `ThemeManager` class
- No theme persistence
- No dark theme
- No user-facing theme selector
- Accent colour detection works but fallback is always Breeze Blue

---

## 5. Test Gaps

- All tests in one file (`test_ui.py`) — no `tests/` directory
- No `pytest` setup — uses plain `unittest`
- No `pytest-qt` integration
- No coverage reporting
- No M3U tests
- No theme tests
- No DB migration tests
- No secret masking tests
- Player tests marked "requires libmpv" but not skipped gracefully in all envs
- XDG isolation is done but only in some test classes

---

## 6. Packaging Gaps

- No `pyproject.toml` → can't `pip install .` or `python -m build`
- PyInstaller spec at root creates filename collision with RPM spec
- `build.sh` references `qmediacenter.spec` at root — must be updated after move
- Nix derivation (`package.nix`) is outdated (v0.1.0, wrong name `qplayer`)
- README says `pkgs/qmediacenter.nix` but file is at root as `package.nix`
- No RPM `.spec` file for distro packaging (fpm-based rpm ≠ real spec)
- No Debian `debian/` directory
- No AUR `PKGBUILD`
- No COPR / OBS configuration
- `MANIFEST.in` absent — sdist would miss data/themes

---

## 7. Security/Privacy Gaps

- Xtream username/password stored in plain JSON (no SecretService)
- Plex token, Emby API key, TMDb/OMDb keys stored in plain JSON
- Config file created without explicit 0600 permissions
- Some error paths may log credentials (URL includes user:pass for some Xtream hosts)
- No input sanitization on M3U channel names before display
- Download path not sanitized against path traversal
- No `SecretStore` abstraction for future KWallet/GNOME Keyring support
- Network requests have per-call timeouts but no global enforcer

---

## 8. Distro Repo Readiness (Current State)

| Distro | Status | Blocker |
|--------|--------|---------|
| Flatpak/Flathub | Local build works | PR needs checklist + video; manifest to maintain |
| Nixpkgs | `package.nix` exists but outdated | Needs rewrite as buildPythonApplication |
| openSUSE OBS | Not started | Needs real RPM spec |
| Fedora COPR/official | Not started | Needs real RPM spec + review |
| Debian mentors | Not started | Needs `debian/` directory + ITP |
| AUR | Not started | Needs PKGBUILD |
| Arch official | Not started | AUR first |

---

## 9. Flathub Readiness

- Manifest exists and builds locally (`v0.6.7`)
- mpv built from source (libass → libplacebo → mpv chain)
- PySide6 from BaseApp
- `finish-args` reasonably minimal but `--socket=session-bus` is broad
- AppStream validates cleanly
- Desktop file validates cleanly
- Missing: Flathub PR checklist, demo video, author declaration
- Missing: proper `releases` entries (only `0.5.2` listed, project is at `0.6.7`)

---

## 10. Version Milestones

### 0.6.x — Stabilization (current)
- [x] M3U playlist support
- [x] Startup without login dialog
- [x] Flatpak local build
- [x] fbo-format fix (GL INVALID_ENUM)
- [ ] pyproject.toml + source install
- [ ] ThemeManager + dark theme
- [ ] tests/ directory

### 0.7.0 — Packaging & Distribution
- [ ] `pyproject.toml` complete
- [ ] `pip install .` / `pipx install .` works
- [ ] RPM spec for OBS/Fedora
- [ ] Debian `debian/` structure
- [ ] AUR `PKGBUILD`
- [ ] Nixpkgs derivation updated
- [ ] Flathub PR reopened with checklist
- [ ] `CHANGELOG.md` and SemVer discipline
- [ ] `CONTRIBUTING.md`
- [ ] Split tests into `tests/`
- [ ] `pytest` + coverage CI job

### 0.8.0 — Architecture
- [ ] `MainWindow` split into page controllers
- [ ] `sources/` module with shared `Source` interface
- [ ] DB migration system
- [ ] `SecretStore` abstraction
- [ ] ThemeManager with hot-swap
- [ ] Empty-state and loading-state components
- [ ] Fullscreen overlay with auto-hide controls
- [ ] Keyboard shortcuts documented in UI

### 1.0.0 — Stable Release
- [ ] Flathub accepted
- [ ] openSUSE OBS home project live
- [ ] Fedora COPR live
- [ ] Debian mentors ITP filed
- [ ] AUR package published
- [ ] Nixpkgs PR merged
- [ ] 80%+ test coverage
- [ ] Zero `ruff` warnings with extended ruleset
- [ ] No credentials in logs
- [ ] AppStream screenshots reflect actual release UI
- [ ] OARS content rating verified

---

## Blocking Issues per Target

### Flatpak/Flathub
- Reopen PR with proper checklist and demo video (manual — Flathub AI policy)
- Update `releases` in metainfo to include 0.6.x tags

### Nixpkgs
- `package.nix` must become `buildPythonApplication` targeting a released sdist or GitHub tag
- `pyproject.toml` is a prerequisite

### openSUSE OBS / Fedora
- Real RPM `.spec` file needed (not PyInstaller + fpm)
- `pyproject.toml` prerequisite

### Debian mentors
- `debian/` directory with all required files
- Network-free build (no pip during `%build`)
- All deps must exist as Debian packages (python-mpv status in Debian is unclear)

### AUR
- Simplest target: `PKGBUILD` pointing at GitHub release tag
- `pyproject.toml` makes this clean

---

*This document is updated at the end of each sprint.*
