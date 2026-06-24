# QMediaCenter — Flatpak Packaging

## Local development build

```bash
flatpak-builder --force-clean /tmp/qmc-build \
  packaging/flatpak/io.github.ycderman.qmediacenter.yml

# Smoke tests (headless)
flatpak-builder --run /tmp/qmc-build \
  packaging/flatpak/io.github.ycderman.qmediacenter.yml qmediacenter --version
flatpak-builder --run /tmp/qmc-build \
  packaging/flatpak/io.github.ycderman.qmediacenter.yml qmediacenter --help
```

## Install locally for testing

```bash
flatpak-builder --force-clean --install --user /tmp/qmc-build \
  packaging/flatpak/io.github.ycderman.qmediacenter.yml
flatpak run io.github.ycderman.qmediacenter
```

## Runtime / SDK

| Item | Value |
|------|-------|
| Runtime | `org.kde.Platform//6.8` |
| SDK | `org.kde.Sdk//6.8` |
| Base | `io.qt.PySide.BaseApp//6.8` |

`io.qt.PySide.BaseApp` provides Python 3 + PySide6 built against Qt 6.8.
This avoids bundling ~500 MB of Qt/PySide6 in the application bundle.

## Filesystem permissions

| Permission | Reason |
|-----------|---------|
| `xdg-videos:ro` | Local video library scanning |
| `xdg-music:ro` | Local music library scanning |
| `xdg-pictures:ro` | Poster/backdrop cache |
| `--filesystem=home` | **NOT granted** — use portals for file picker |

Users who want to open media files from arbitrary paths should use the system
file manager or drag-and-drop (portal-based). Granting `home:ro` or `home`
would expose the entire home directory, which violates Flathub policy without
a documented reason.

## How pip install works in Flatpak

The `qmediacenter` module uses `pip3 install --no-build-isolation .` with
`SETUPTOOLS_SCM_PRETEND_VERSION` set (no `.git` in the Flatpak sandbox).
This installs via `pyproject.toml` / `setuptools.build_meta`, so:

- Entry point `qmediacenter` is registered in `dist-info/entry_points.txt`
- `importlib.resources` finds theme QSS files and the app icon from the
  wheel's `themes/` and `data/` packages
- `importlib.metadata.version("qmediacenter")` returns the correct version

The older `packaging/io.github.ycderman.qmediacenter.yaml` manifest copied
Python files manually. The new manifest in `packaging/flatpak/` uses pip
install for correct entry-point and resource access.

## Source switching (local ↔ release)

The manifest contains a `type: dir` source for local development.
To build a tagged release, replace it with:

```yaml
    sources:
      - type: git
        url: https://github.com/ycderman/qmediacenter
        tag: v0.7.0
        commit: <commit-hash>
```

Run `git rev-parse HEAD` after tagging to get the commit hash.

## Flathub submission (Sprint 4)

Before re-opening the Flathub PR:
- Switch source to `type: git` with the release tag
- Bump `SETUPTOOLS_SCM_PRETEND_VERSION` to match the tag
- Record a short screen capture showing IPTV channel loading and local library
- Fill in the Flathub PR checklist (testing, no non-free code, metainfo complete)
- Note: AI-generated code policy — review all bundled sources for compliance
