# Flathub Submission Checklist — QMediaCenter v0.7.0

## App identity

| Field | Value |
|-------|-------|
| App ID | `io.github.ycderman.qmediacenter` |
| Name | QMediaCenter |
| Version | 0.7.0 |
| License | MIT |
| Homepage | https://github.com/ycderman/qmediacenter |

## Manifest

| Field | Value |
|-------|-------|
| Manifest path | `packaging/flatpak/flathub/io.github.ycderman.qmediacenter.yml` |
| Runtime | `org.kde.Platform//6.8` |
| SDK | `org.kde.Sdk//6.8` |
| Base | `io.qt.PySide.BaseApp//6.8` |
| Source type | `git` |
| Tag | `v0.7.0` |
| Commit | `9193a174a8d0b312648949086ca4bec90a91245a` |

## Build test results

| Test | Result |
|------|--------|
| `flatpak-builder --force-clean` | ✅ Build successful |
| `qmediacenter --version` in sandbox | ✅ `qmediacenter 0.7.0` |
| `qmediacenter --help` in sandbox | ✅ |
| `appstreamcli validate --no-net` | ✅ Validation successful |
| `desktop-file-validate` | ✅ |

## Sandbox permissions

| Permission | Reason | Required? |
|-----------|---------|-----------|
| `--share=network` | IPTV streams (M3U/Xtream), Emby/Plex API, metadata fetching | Yes |
| `--share=ipc` | X11 shared-memory (needed for XWayland) | Yes |
| `--socket=wayland` | Primary display protocol | Yes |
| `--socket=fallback-x11` | X11 support for non-Wayland compositors | Yes |
| `--socket=pulseaudio` | Audio output (PipeWire PulseAudio socket) | Yes |
| `--device=dri` | GPU access for VAAPI hardware decode, OpenGL | Yes |
| `--filesystem=xdg-videos:ro` | Local video library scanning | Yes |
| `--filesystem=xdg-music:ro` | Local music library scanning | Yes |
| `--filesystem=xdg-pictures:ro` | Poster/backdrop cache write access | Yes |
| `--talk-name=org.freedesktop.ScreenSaver` | Inhibit screen saver during playback | Yes |
| `--own-name=org.mpris.MediaPlayer2.qmediacenter` | MPRIS2 media player registration | Yes |
| `--talk-name=org.mpris.MediaPlayer2.*` | MPRIS2 controller communication | Yes |
| `--env=LC_NUMERIC=C` | libmpv requires C locale for float parsing | Yes |
| `--filesystem=home` | **NOT granted** | N/A |
| `--socket=session-bus` | **NOT granted** (removed; named bus access sufficient) | N/A |

## AppStream metainfo

- File: `data/io.github.ycderman.qmediacenter.metainfo.xml`
- App ID matches manifest: ✅ `io.github.ycderman.qmediacenter`
- `<releases>` populated: ✅ (0.5.0 through 0.7.0)
- `<content_rating type="oars-1.1"/>`: ✅ present
- Screenshots: see below
- Validates with `appstreamcli validate --no-net`: ✅

## Bundled third-party sources

All sources in the manifest are pinned with exact version tags and sha256 hashes.
No `branch:`, `HEAD`, or floating version references.

| Module | Version | License | Source |
|--------|---------|---------|--------|
| libass | 0.17.3 | ISC/LGPL-2.1 | GitHub release tarball |
| MarkupSafe | 2.1.5 | BSD-3-Clause | PyPI wheel |
| jinja2 | 3.1.6 | BSD-3-Clause | PyPI wheel |
| libplacebo | 6.338.2 | LGPL-2.1 | GitHub tag tarball |
| mpv (libmpv) | 0.39.0 | LGPL-2.1 | GitHub tag tarball |
| python-mpv | 1.0.8 | MIT | PyPI wheel |
| PyOpenGL | 3.1.10 | BSD-3-Clause | PyPI wheel |
| requests | 2.34.2 | Apache-2.0 | PyPI wheel |
| certifi | 2026.6.17 | MPL-2.0 | PyPI wheel |
| charset-normalizer | 3.4.7 | MIT | PyPI wheel |
| idna | 3.18 | BSD-3-Clause | PyPI wheel |
| urllib3 | 2.7.0 | MIT | PyPI wheel |
| yt-dlp | 2026.6.9 | Unlicense | PyPI wheel |
| setuptools-scm | 9.2.2 | MIT | PyPI wheel |
| qmediacenter | 0.7.0 | MIT | GitHub tag (git) |

All licenses are compatible with Flathub distribution requirements.

## AI policy compliance

This project was developed with assistance from Claude (Anthropic).
Per Flathub's AI policy, all generated or AI-assisted code has been:
- Reviewed by the maintainer before inclusion
- Understood in full — no black-box code included
- Tested end-to-end (build, smoke, CI)

The author (ycderman) is the sole maintainer and takes responsibility for all code.

## Screenshots checklist

AppStream metainfo currently has no `<screenshots>` element.
Before submitting to Flathub, add at least one screenshot.

- [ ] Main home screen (Continue Watching / Recently Added)
- [ ] IPTV channel list
- [ ] Local library view
- [ ] Playback with media controls visible

Screenshot format: PNG, 16:9, 1280×720 or larger.
Store in `data/screenshots/` and reference in metainfo.

## Demo video checklist

Flathub does not require a video, but it helps reviewers.
If recording:

- [ ] App launches cleanly from desktop
- [ ] Navigate to local media or IPTV source
- [ ] Start playback (show video + audio working)
- [ ] Show MPRIS controls responding (taskbar or media keys)
- [ ] Close cleanly

## Missing before PR can be opened

- [ ] At least one screenshot in AppStream metainfo
- [ ] Screenshots stored in `data/screenshots/` and committed
- [ ] Fork https://github.com/flathub/flathub on GitHub
- [ ] Create branch `new-app/io.github.ycderman.qmediacenter`
- [ ] Copy `packaging/flatpak/flathub/io.github.ycderman.qmediacenter.yml` to repo root
- [ ] Open PR — title: `Add io.github.ycderman.qmediacenter`

## PR template text (draft)

```
## App name
QMediaCenter

## App description
QMediaCenter is a lightweight open-source media center built with Qt6 (PySide6)
and libmpv. It unifies IPTV (Xtream Codes, M3U), Emby, Plex, and local media
in one interface with hardware-accelerated video decoding.

## Testing
Built locally with flatpak-builder; `qmediacenter --version` returns 0.7.0.
AppStream and desktop file validate cleanly.

## Checklist
- [x] App ID: io.github.ycderman.qmediacenter
- [x] Manifest uses type:git with pinned tag and commit
- [x] No --filesystem=home
- [x] No --socket=session-bus
- [x] All bundled sources pinned with sha256
- [x] OARS content rating present
- [x] AppStream releases populated (0.5.0 – 0.7.0)
- [x] License: MIT
- [ ] Screenshots added to metainfo
```
