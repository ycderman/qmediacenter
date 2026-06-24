# QMediaCenter — Flatpak Packaging

## Manifest files

| File | Purpose |
|------|---------|
| `packaging/flatpak/io.github.ycderman.qmediacenter.yml` | Local dev (`type: dir`) — use for testing |
| `packaging/flatpak/io.github.ycderman.qmediacenter.flathub.yml` | Flathub release (`type: git`, tag pinned) |

## Local development build

```bash
flatpak-builder --force-clean /tmp/qmc-build \
  packaging/flatpak/io.github.ycderman.qmediacenter.yml

# Smoke tests
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

## Flathub / release build

`packaging/flatpak/io.github.ycderman.qmediacenter.flathub.yml` is pinned to
**v0.7.0** with commit `9193a174a8d0b312648949086ca4bec90a91245a`.
No placeholder remains — the manifest is ready for Flathub PR submission.

For future releases, update `tag:` and `commit:` in the manifest:

```bash
# Get commit hash (use rev-list, not rev-parse, for annotated tags):
git rev-list -n 1 vX.Y.Z
```

### Flathub PR checklist (v0.7.0)

See `docs/FLATHUB_SUBMISSION.md` for the full checklist.

Quick status:
1. ✅ `type: git` with pinned tag + commit
2. ✅ `SETUPTOOLS_SCM_PRETEND_VERSION=0.7.0`
3. ✅ AppStream metainfo validates cleanly
4. ✅ Desktop file validates cleanly
5. ✅ `--filesystem=home` not used
6. ✅ `--socket=session-bus` removed (named bus access sufficient for MPRIS2)
7. ✅ All bundled sources pinned with sha256 — no floating branches
8. ✅ OARS content rating present in metainfo
9. [ ] Screenshots added to AppStream metainfo
10. [ ] Fork flathub/flathub and open PR

### Testing the Flathub manifest

Before submitting, build from the release manifest (requires internet for git fetch):

1. ~~Tag the release and push it~~ — done (v0.7.0)

2. Get the exact commit hash that the tag points to:
   ```bash
   # For annotated tags, rev-parse on the ref returns the tag object hash,
   # not the commit hash. Dereference with ^{} or use rev-list:
   git rev-list -n 1 v0.7.0
   # Equivalent: git rev-parse v0.7.0^{}
   ```

3. Update `.flathub.yml`:
   - Replace `PLACEHOLDER_REPLACE_WITH_REAL_COMMIT_AFTER_TAGGING` with the hash
   - Confirm `SETUPTOOLS_SCM_PRETEND_VERSION=0.7.0` matches the tag

4. Test the release manifest:
   ```bash
   flatpak-builder --force-clean /tmp/qmc-flathub-build \
     packaging/flatpak/io.github.ycderman.qmediacenter.flathub.yml
   flatpak-builder --run /tmp/qmc-flathub-build \
     packaging/flatpak/io.github.ycderman.qmediacenter.flathub.yml qmediacenter --version
   ```

5. Fill in the Flathub PR checklist:
   - Testing: built locally, `--version` and `--help` verified
   - No non-free bundled code (libass, libplacebo, mpv all LGPL/GPL; Python deps are MIT/Apache)
   - AppStream metainfo complete and validates cleanly
   - Screenshots in metainfo match actual release UI
   - OARS content rating set (currently empty `<content_rating type="oars-1.1"/>`)
   - Record a short screen capture: IPTV channel switching + local library browse

6. AI policy note: review all source references in the manifest for compliance with
   Flathub's policy on AI-generated code before submitting.

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

The older `packaging/io.github.ycderman.qmediacenter.yaml` manifest used
manual file copies. The new manifests in `packaging/flatpak/` use pip install
for correct entry-point and resource access.
