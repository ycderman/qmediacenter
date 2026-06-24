# AUR packaging

## Status: v0.7.0 ready

`PKGBUILD` contains the real sha256sum for v0.7.0. The next step is to
generate `.SRCINFO` on an Arch system and push to AUR.

## Generate .SRCINFO and push to AUR (requires Arch Linux or Arch container)

```bash
cd packaging/arch

# Generate .SRCINFO (needed for AUR submission)
makepkg --printsrcinfo > .SRCINFO

# Optional: test local build (downloads source, builds wheel, installs)
makepkg --cleanbuild --syncdeps --noconfirm
sudo pacman -U qmediacenter-0.7.0-1-x86_64.pkg.tar.zst

# Push to AUR
git clone ssh://aur@aur.archlinux.org/qmediacenter.git aur-qmediacenter
cp PKGBUILD .SRCINFO aur-qmediacenter/
cd aur-qmediacenter && git add -A && git commit -m "Initial release 0.7.0"
git push
```

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
5. Commit and push to AUR.

## Notes

- `makepkg` is not available on NixOS — use an Arch container:
  ```bash
  docker run --rm -it archlinux:latest bash
  pacman -Sy --noconfirm base-devel git && cd /tmp
  # copy PKGBUILD in, then run makepkg
  ```
- `python-mpv` must be present in AUR before this package can be installed.
