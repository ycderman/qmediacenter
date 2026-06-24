# QMediaCenter — Professionalization Roadmap

> Generated: 2026-06-24 | Updated: 2026-06-25 | Status: Sprint 4 complete

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
| Flatpak/Flathub | ✅ Flathub manifest ready (`type: git`) | Push tag → fill commit hash → PR checklist + demo video |
| Nixpkgs | ✅ `buildPythonApplication` derivation + release-example.nix | Push tag → run nix-prefetch-url → open nixpkgs PR |
| openSUSE OBS | ✅ RPM spec ready | Push tag → test on Fedora/OBS → submit |
| Fedora COPR/official | ✅ RPM spec ready | Same as OBS |
| Debian mentors | Not started | Needs `debian/` directory + ITP (Sprint 5) |
| AUR | ✅ PKGBUILD ready | Push tag → fill sha256sum → push to AUR |
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
- [x] pyproject.toml + source install (`pip install -e .`, `pip install dist/*.whl`)
- [x] ThemeManager + Breeze Dark theme
- [x] tests/ directory (pytest, 61 tests)
- [x] `data/` and `themes/` as Python packages — importlib.resources
- [x] `--version` / `--help` CLI without Qt/display
- [x] Wheel contents verified: themes, icon, metainfo all present
- [x] CI wheel-build + clean-venv install smoke test

### 0.7.0 — Packaging & Distribution (Sprint 4 — complete)
- [x] `pyproject.toml` complete
- [x] `pip install .` / `pipx install .` works
- [x] Split tests into `tests/`
- [x] `pytest` + CI job (63 passed, 2 skipped)
- [x] `packaging/nix/qmediacenter.nix` — `buildPythonApplication` derivation, builds + smoke-tested
- [x] `packaging/nix/release-example.nix` — release pin template for Nixpkgs PR
- [x] `packaging/flatpak/io.github.ycderman.qmediacenter.yml` — local dev manifest (type: dir)
- [x] `packaging/flatpak/io.github.ycderman.qmediacenter.flathub.yml` — Flathub manifest (type: git, v0.7.0)
- [x] `packaging/rpm/qmediacenter.spec` — real pyproject-based RPM spec (Fedora/openSUSE)
- [x] `packaging/arch/PKGBUILD` + `packaging/arch/README.md` — AUR package
- [x] `docs/NIXPKGS.md` + `docs/FLATPAK.md` updated
- [x] `CONTRIBUTING.md` complete
- [x] AppStream `releases` updated (0.5.0 through 0.7.0, validates cleanly)
- [x] CHANGELOG [0.7.0] as proper release notes
- [x] `docs/RELEASE.md` full release process documented
- [ ] v0.7.0 git tag + GitHub Release (tag pending push, manual)
- [ ] Nixpkgs PR — pin real sha256, open PR against nixpkgs/master (manual, after tag)
- [ ] Flathub PR — type: git, commit hash, checklist + demo video (manual, after tag)
- [ ] AUR sha256sum update + push to aur.archlinux.org (manual, after tag)
- [ ] Debian `debian/` structure (Sprint 5)

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
- ✅ `packaging/flatpak/io.github.ycderman.qmediacenter.flathub.yml` — `type: git`, v0.7.0
- Remaining: push v0.7.0 tag → fill `commit:` hash → reopen PR with checklist + demo video

### Nixpkgs
- ✅ `packaging/nix/qmediacenter.nix` — working `buildPythonApplication` derivation
- ✅ `packaging/nix/release-example.nix` — release pin template
- Remaining: push v0.7.0 tag → `nix-prefetch-url` to get real hash → open nixpkgs PR

### openSUSE OBS / Fedora
- ✅ `packaging/rpm/qmediacenter.spec` — real pyproject-based RPM spec
- Remaining: push tag → test on Fedora container or COPR → submit

### Debian mentors
- `debian/` directory with all required files (Sprint 5)
- Network-free build (no pip during `dh_auto_build`)
- All deps must exist as Debian packages (python-mpv status in Debian is unclear)

### AUR
- ✅ `packaging/arch/PKGBUILD` ready
- Remaining: push tag → replace `sha256sums=('SKIP')` → push to AUR

---

---

## Sprint Summary

### Sprint 1 — Completed 2026-06-24
- `pyproject.toml` + `ThemeManager` + `themes/` package
- `CHANGELOG.md`, `MANIFEST.in`, `tests/` directory (47 tests)
- CI: pytest job, spec path fix, bundle needs pytest

### Sprint 2 — Completed 2026-06-24
- `data/` as Python package → `importlib.resources` for icon + metainfo
- `qmediacenter/` package with `__version__`
- `--version` / `--help` CLI (no display needed)
- `project.scripts` deduplication (single entry point)
- `tests/test_resources.py` (15 new tests; 61 total)
- CI `wheel-build` job: build → verify wheel contents → clean venv install → smoke
- Wheel verified: all resources present, install+run confirmed

### Sprint 3 — Completed 2026-06-24
Nix + Flatpak packaging infrastructure.

1. ✅ `packaging/nix/qmediacenter.nix` — `buildPythonApplication` derivation
   - `wrapQtAppsHook` for Qt plugin path; `LD_LIBRARY_PATH` for libmpv
   - `dontCheckRuntimeDeps` (PyPA normalisation mismatch for `mpv` binding)
   - `packaging/nix/default.nix` — source filter removes `dist/` artifacts
   - Builds and smoke-tested: `--version`, `--help`, desktop/icon/metainfo installed
2. ✅ `packaging/flatpak/io.github.ycderman.qmediacenter.yml`
   - Uses `io.qt.PySide.BaseApp//6.8` + `org.kde.Platform//6.8`
   - Builds mpv from source (libass → libplacebo → mpv chain)
   - pip installs qmediacenter via pyproject.toml (importlib.resources works)
   - `type: dir` for local dev; `type: git` for Flathub
   - Builds and smoke-tested via `flatpak-builder --run`
3. ✅ `docs/NIXPKGS.md`, `docs/FLATPAK.md`, packaging READMEs
4. ✅ README updated with Nix + Flatpak install sections

### Sprint 3.5 — Completed 2026-06-25
Release readiness and quality pass.

1. ✅ AppStream `releases` updated: 0.5.0 through 0.7.0 all documented
2. ✅ AppStream description updated (removed "development packaging" phrasing)
3. ✅ AppStream validates cleanly: `appstreamcli validate --no-net`
4. ✅ CHANGELOG [0.7.0] written as proper release notes (user-facing language)
5. ✅ Nix derivation quality pass: mpv/python-mpv separation documented,
   `maintainers` expression correct, comments explain non-obvious choices
6. ✅ Flatpak manifest: `--filesystem=home` not used; minimal permissions documented
7. ✅ `docs/RELEASE.md` created — full release process from tag to AUR/Nixpkgs/Flathub
8. ✅ `CONTRIBUTING.md` created — dev setup, test commands, security rules
9. ✅ README NixOS section corrected (removed `nix-build package.nix` / `qplayer`)
10. ✅ ROADMAP Sprint 4/5/6 milestones defined

### Sprint 4 — Completed 2026-06-25
RPM spec, AUR PKGBUILD, Flathub manifest, and release prep.

1. ✅ `packaging/rpm/qmediacenter.spec` — real pyproject-based RPM spec (Fedora/openSUSE)
   - `%pyproject_wheel` / `%pyproject_install` macros
   - `SETUPTOOLS_SCM_PRETEND_VERSION` for tarball builds (no .git)
   - `%check` validates desktop file, AppStream, headless `--version` smoke
   - openSUSE package name notes in comments
2. ✅ `packaging/arch/PKGBUILD` — AUR package for v0.7.0
   - `python -m build --wheel --no-isolation` + `python -m installer`
   - `sha256sums=('SKIP')` placeholder — replace before AUR push
3. ✅ `packaging/arch/README.md` — AUR submission workflow
4. ✅ `packaging/nix/release-example.nix` — release pin template with `lib.fakeHash`
5. ✅ `packaging/flatpak/io.github.ycderman.qmediacenter.flathub.yml` — Flathub `type: git` manifest
   - SETUPTOOLS_SCM_PRETEND_VERSION=0.7.0
   - Same module chain as dev manifest; commit placeholder to replace after tagging
6. ✅ `docs/FLATPAK.md` — local vs Flathub manifest distinction, release workflow
7. ✅ `docs/NIXPKGS.md` — nix-prefetch-url command for hash pinning
8. ✅ Distro repo table updated

**Post-sprint manual steps (require live v0.7.0 tag on GitHub):**
- `git tag -a v0.7.0 -m "QMediaCenter 0.7.0" && git push origin v0.7.0`
- Update `sha256sums` in PKGBUILD; update `commit:` in flathub manifest
- Open Nixpkgs PR, open Flathub PR, push to AUR

### Sprint 5 — Proposed
Debian packaging.

1. `packaging/debian/` — `control`, `rules`, `copyright`, `changelog`, `watch`
2. All runtime deps must exist as Debian packages (check `python-mpv` status)
3. ITP filed on Debian BTS
4. pbuilder/sbuild clean network-free build test

### Sprint 6 — Proposed
Architecture and UI improvements.

1. Split `MainWindow` (1 600+ lines) into page controllers
2. `sources/` module with shared `Source` interface
3. DB migration system
4. `SecretStore` abstraction (KWallet / GNOME Keyring)
5. Fullscreen overlay with auto-hide controls
6. 80%+ test coverage

*This document is updated at the end of each sprint.*
