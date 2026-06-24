# Contributing to QMediaCenter

## Development setup

```bash
git clone https://github.com/ycderman/qmediacenter
cd qmediacenter

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Or with pipx for isolation
pipx install -e ".[dev]" --include-deps
```

System packages required (Debian/Ubuntu):
```bash
sudo apt install libmpv-dev libgl1 libgles2
```

NixOS:
```bash
nix-shell -p python3 python3Packages.pyside6 python3Packages.mpv \
  python3Packages.pyopengl python3Packages.requests python3Packages.yt-dlp \
  mpv libGL
```

## Running tests

```bash
# Unit + integration tests
pytest tests/ -v

# Headless UI tests
QT_QPA_PLATFORM=offscreen LC_NUMERIC=C python test_ui.py

# Lint
ruff check .
```

All three must pass before opening a PR.

## Packaging tests

```bash
# Wheel build and install smoke test
python -m build
python -m venv /tmp/qmc-test
/tmp/qmc-test/bin/pip install dist/*.whl pyside6 mpv pyopengl requests yt-dlp
/tmp/qmc-test/bin/qmediacenter --version
/tmp/qmc-test/bin/qmediacenter --help

# Nix derivation (NixOS/nix only)
nix-build packaging/nix/default.nix
./result/bin/qmediacenter --version

# Flatpak (requires flatpak-builder + org.kde.Platform//6.8 + io.qt.PySide.BaseApp//6.8)
flatpak-builder --force-clean /tmp/qmc-build \
  packaging/flatpak/io.github.ycderman.qmediacenter.yml
flatpak-builder --run /tmp/qmc-build \
  packaging/flatpak/io.github.ycderman.qmediacenter.yml qmediacenter --version
```

## Commit style

- One logical change per commit
- Present tense imperative: `fix mpv buffer overflow` not `fixed` or `fixes`
- Reference issue if applicable: `fix channel list blank (#42)`
- No co-author tags, attribution lines, or AI-generated commit credits

## Code style

- Ruff enforced: `ruff check .` must pass
- No multi-paragraph docstrings — one short line max, only when the WHY is non-obvious
- No comments explaining WHAT the code does — name things well instead
- No feature flags, no backwards-compat shims, no error handling for impossible scenarios

## Security / privacy rules

- **Never log credentials** — Xtream passwords, Plex tokens, Emby API keys, TMDb/OMDb keys
  must never appear in log output even at DEBUG level
- Xtream URLs may include `user:password` in the path — strip before logging
- Download paths must be sanitized against path traversal
- New network requests must have explicit timeouts

## Pull requests

- Open a draft PR early if you want feedback on direction
- The PR description should explain WHY, not just WHAT
- One PR per logical change; don't bundle unrelated fixes
- CI must be green before requesting review

## Release process

See [docs/RELEASE.md](docs/RELEASE.md) for the full release checklist.
