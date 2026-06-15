# QtIPTV

A minimal **Qt6 (PySide6) + libmpv** IPTV player with **Xtream Codes** support.

- Embedded mpv player (OpenGL render API → works on Wayland *and* X11) with
  full hardware decoding (VAAPI) and every codec mpv supports — HEVC, AC-3,
  E-AC3, DTS, … — so audio/video "just works" like EngPlayer.
- **Live TV**, **Movies (VOD)** and **Series** browsing by category.
- **Download** option for movies and episodes.
- Profile login with credentials saved in `~/.config/qtiptv/`.

## Architecture

```
main.py                entry point (QApplication + login + main window)
iptv/
  xtream.py            Xtream Codes API client
  config.py            profile / settings persistence (JSON)
  mpv_widget.py        QOpenGLWidget that renders libmpv (the hard part)
  downloader.py        threaded HTTP download manager
ui/
  login_dialog.py      Xtream profile entry / selection
  main_window.py       sidebar (Live/Movies/Series) + content list + player
package.nix            Nix derivation (wrapped runnable binary)
shell.nix              dev shell
```

## Run (NixOS)

```sh
nix-build package.nix
./result/bin/qtiptv
```

Or for development:

```sh
nix-build -o /tmp/pyenv -E 'with import <nixpkgs>{}; \
  python3.withPackages(ps: with ps;[pyside6 mpv pyopengl requests yt-dlp])'
LD_LIBRARY_PATH=$(nix eval --raw nixpkgs#mpv-unwrapped)/lib \
LC_NUMERIC=C QT_QPA_PLATFORM="wayland;xcb" \
  /tmp/pyenv/bin/python3 main.py
```

## Notes / next steps

This is a working **v0.1 foundation**, not feature-parity with EngPlayer yet.
Natural next additions: poster/thumbnail grid (async image loading), EPG for
Live TV, resume/watch-history, favourites, search across all content, and a
KDE-Breeze-aware Qt stylesheet.

## Tested

- `test_ui.py` — end-to-end UI flow against a fake Xtream client (categories,
  content, series → episodes, mode switching). All threading paths exercised.
