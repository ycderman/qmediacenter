# AUR packaging

## Build locally (requires Arch Linux or an Arch container)

```bash
cd packaging/arch

# Generate .SRCINFO (needed for AUR submission)
makepkg --printsrcinfo > .SRCINFO

# Build and install (downloads source, installs deps, builds wheel)
makepkg --cleanbuild --syncdeps --noconfirm
sudo pacman -U qmediacenter-0.7.0-1-x86_64.pkg.tar.zst
```

## After tagging v0.7.0

1. Get the real sha256sum of the source tarball:
   ```bash
   curl -L https://github.com/ycderman/qmediacenter/archive/refs/tags/v0.7.0.tar.gz | sha256sum
   ```
2. Replace `sha256sums=('SKIP')` in `PKGBUILD` with the real hash.
3. Re-run `makepkg --printsrcinfo > .SRCINFO`.
4. Push to AUR:
   ```bash
   git clone ssh://aur@aur.archlinux.org/qmediacenter.git aur-qmediacenter
   cp PKGBUILD .SRCINFO aur-qmediacenter/
   cd aur-qmediacenter && git add -A && git commit -m "Initial release 0.7.0"
   git push
   ```

## Notes

- `sha256sums=('SKIP')` is a placeholder until the release tag exists.
  **Never submit to AUR with SKIP** — replace with the real hash first.
- `python-mpv` is available in the AUR as `python-mpv`; confirm it is
  present or the build will fail with a missing dependency.
- `makepkg` is not available on NixOS — test in an Arch container:
  ```bash
  docker run --rm -it archlinux:latest bash
  pacman -Sy --noconfirm base-devel git && cd /tmp
  # copy PKGBUILD in, then run makepkg
  ```
