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

## Pinning to a release tag

**Requires: the release tag must be pushed to GitHub first** — `nix-prefetch-url`
and `fetchFromGitHub` fetch from the remote tarball, which only exists after push.

See `packaging/nix/release-example.nix` for a ready-to-use template.
Its `lib.fakeHash` placeholder must be replaced with the real hash before any
Nixpkgs PR submission.

The easiest workflow is to build once with `lib.fakeHash` and let Nix tell you
the correct hash:

```bash
nix-build packaging/nix/release-example.nix
# Build fails with: got: sha256-AAAA...
# Paste that value as hash = "sha256-AAAA..."; in release-example.nix, then rebuild.
```

Or prefetch directly (tag must be on remote):

```bash
nix-prefetch-url --unpack \
  https://github.com/ycderman/qmediacenter/archive/refs/tags/v0.7.0.tar.gz
```

Or with the newer `nix` CLI:

```bash
nix flake prefetch github:ycderman/qmediacenter/v0.7.0
# The hash appears as narHash in the output
```

After updating the hash, verify the pinned build works:

```bash
nix-build packaging/nix/release-example.nix
./result/bin/qmediacenter --version
```

## Nixpkgs submission

Before submitting to nixpkgs:
- Tag pushed to remote and `lib.fakeHash` replaced with the real hash
- Set `version` to the release tag (e.g. `"0.7.0"`)
- Add yourself to `maintainers/maintainer-list.nix` in the nixpkgs repo, then
  add to the derivation: `maintainers = with maintainers; [ ycderman ];`
- Run `nix-build` against the nixpkgs checkout and confirm end-to-end
- Open a PR against `nixpkgs/master` in the `pkgs/applications/video/` tree
