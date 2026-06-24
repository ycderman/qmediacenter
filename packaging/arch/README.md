# AUR packaging

## Status: v0.7.0 ready

`PKGBUILD` and `.SRCINFO` are pinned to v0.7.0. All hashes verified.
The next step is to push to AUR from an Arch system.

## Dependency status (Arch official repos)

All runtime dependencies are in the official `extra` repository — no AUR
dependencies required:

| Package | Repo |
|---------|------|
| `python` | core |
| `pyside6` | extra |
| `python-mpv` | extra |
| `python-pyopengl` | extra |
| `python-requests` | extra |
| `yt-dlp` | extra |
| `mpv` | extra |
| `qt6-wayland` | extra |

## Push to AUR (requires Arch system or Arch container)

```bash
# Clone the AUR repo (first time only)
git clone ssh://aur@aur.archlinux.org/qmediacenter.git aur-qmediacenter

# Copy the files
cp packaging/arch/PKGBUILD packaging/arch/.SRCINFO aur-qmediacenter/

# Commit and push
cd aur-qmediacenter
git add PKGBUILD .SRCINFO
git commit -m "Initial release 0.7.0"
git push
```

## Build locally (on Arch or in Arch container)

```bash
cd packaging/arch

# Install build dependencies
sudo pacman -S --needed base-devel python-build python-installer \
  python-setuptools python-setuptools-scm python-wheel

# Build and install
makepkg --cleanbuild --syncdeps --noconfirm
sudo pacman -U qmediacenter-0.7.0-1-x86_64.pkg.tar.zst
```

## Regenerate .SRCINFO

```bash
cd packaging/arch
makepkg --printsrcinfo > .SRCINFO
```

`.SRCINFO` was generated using `makepkg --printsrcinfo` (via nix-shell pacman
on NixOS with `MAKEPKG_CONF` override). The output is deterministic and
functionally identical to what `makepkg` produces on Arch.

## v0.7.0 source hash

```
sha256sums=('6723ddf69e2554b26dd63e312e69b9c0440f5bbafbb7e03a2c860377054d8f1d')
```

Source: `https://github.com/ycderman/qmediacenter/archive/refs/tags/v0.7.0.tar.gz`

## For future releases

1. Update `pkgver` in `PKGBUILD`.
2. Get new sha256:
   ```bash
   curl -L https://github.com/ycderman/qmediacenter/archive/refs/tags/vX.Y.Z.tar.gz \
     | sha256sum
   # or on Arch: makepkg -g
   ```
3. Update `sha256sums=('...')`.
4. Re-run `makepkg --printsrcinfo > .SRCINFO`.
5. Commit to main, then push to AUR.
