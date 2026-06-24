# QMediaCenter — Nix Packaging

## Development build (from repo)

```bash
nix-build packaging/nix/default.nix
./result/bin/qmediacenter --version
./result/bin/qmediacenter --help
QT_QPA_PLATFORM=offscreen ./result/bin/qmediacenter
```

`packaging/nix/default.nix` filters build artifacts (`dist/`, `build/`, `*.egg-info`) from the source tree before passing it to the derivation, so local `dist/*.whl` files don't interfere.

## Files

| File | Purpose |
|------|---------|
| `packaging/nix/qmediacenter.nix` | Main derivation (`buildPythonApplication`) |
| `packaging/nix/default.nix` | Dev wrapper — points `src` at repo root with artifact filter |

## Using from a NixOS flake

```nix
# flake.nix
{
  inputs.qmediacenter.url = "github:ycderman/qmediacenter";
  outputs = { self, nixpkgs, qmediacenter }: {
    nixosConfigurations.myhost = nixpkgs.lib.nixosSystem {
      modules = [
        ({ pkgs, ... }: {
          environment.systemPackages = [
            (pkgs.callPackage (qmediacenter + "/packaging/nix/qmediacenter.nix") {
              src = qmediacenter;
              version = qmediacenter.rev or "git";
            })
          ];
        })
      ];
    };
  };
}
```

## Runtime dependencies

| Dep | Nixpkgs attribute | Notes |
|-----|-------------------|-------|
| Python 3.11+ | `python3` | via `buildPythonApplication` |
| PySide6 | `python3Packages.pyside6` | Qt6 bindings |
| python-mpv | `python3Packages.mpv` | ctypes binding for libmpv |
| PyOpenGL | `python3Packages.pyopengl` | OpenGL context |
| requests | `python3Packages.requests` | HTTP client |
| yt-dlp | `python3Packages.yt-dlp` | stream URL extraction |
| libmpv | `mpv` | shared library for python-mpv |
| Mesa/libGL | `libGL` | OpenGL + VAAPI |
| qtwayland | `qt6.qtwayland` | Wayland platform plugin |

## `dontCheckRuntimeDeps`

Set to `true` because `pythonRuntimeDepsCheckHook` compares `Requires-Dist: mpv>=1.0`
from the wheel against installed Nix dist-info names. The Nix package `python3Packages.mpv`
ships with pname `"mpv"` but the PyPA normalisation of the wheel metadata doesn't match,
producing a false "not installed" error. The Nix closure already guarantees the dep is
present, so skipping this check is safe.

## Nixpkgs submission (Sprint 4)

Before submitting to nixpkgs:
- Pin `src` to a tagged release with a real `sha256` (replace `lib.fakeSha256`)
- Set `version` to the release tag (e.g. `"0.7.0"`)
- Add yourself to `maintainers/maintainer-list.nix` in the nixpkgs repo, then
  add to the derivation: `maintainers = with maintainers; [ ycderman ];`
- Run `nix-build` and confirm the `result/` symlink works end-to-end
- Open a PR against `nixpkgs/master` in the `pkgs/applications/video/` tree
