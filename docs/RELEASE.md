# Release Process

This document describes the steps to cut an official release of QMediaCenter.

## Pre-release checklist

Run the full test suite and verify everything passes:

```bash
ruff check .
pytest tests/ -v
QT_QPA_PLATFORM=offscreen LC_NUMERIC=C python test_ui.py
python -m build
nix-build packaging/nix/default.nix
./result/bin/qmediacenter --version
flatpak-builder --force-clean /tmp/qmc-build \
  packaging/flatpak/io.github.ycderman.qmediacenter.yml
flatpak-builder --run /tmp/qmc-build \
  packaging/flatpak/io.github.ycderman.qmediacenter.yml qmediacenter --version
```

## 1. Update CHANGELOG

Move items from `[Unreleased]` to a new `[X.Y.Z] — YYYY-MM-DD` section.
Write entries in user-facing language, not sprint/task language.

## 2. Update AppStream releases

In `data/io.github.ycderman.qmediacenter.metainfo.xml`, add a `<release>` entry:

```xml
<release version="X.Y.Z" date="YYYY-MM-DD">
  <description>
    <p>Short summary of what changed.</p>
  </description>
</release>
```

Validate after editing:

```bash
LC_ALL=C LANG=C nix-shell -p appstream --run \
  "appstreamcli validate --no-net data/io.github.ycderman.qmediacenter.metainfo.xml"
```

## 3. Commit and tag

```bash
git add CHANGELOG.md data/io.github.ycderman.qmediacenter.metainfo.xml
git commit -m "release: X.Y.Z"
git tag -a "vX.Y.Z" -m "QMediaCenter X.Y.Z"
git push origin main --tags
```

## 4. GitHub Release

Push the tag; CI will build `.deb` and `.rpm` via PyInstaller + fpm.
Create a GitHub Release from the tag and attach the CI artifacts.

## 5. Update Nix derivation for release

In `packaging/nix/qmediacenter.nix`, replace the placeholder `src`:

```nix
src = fetchFromGitHub {
  owner  = "ycderman";
  repo   = "qmediacenter";
  rev    = "vX.Y.Z";
  sha256 = lib.fakeHash;  # build once, copy the correct hash from error output
};
```

Then build to get the real hash:

```bash
nix-build packaging/nix/qmediacenter.nix   # will fail with the real sha256
# Copy the sha256 from the error, update the file, build again
```

## 6. Update Flatpak manifest for release

In `packaging/flatpak/io.github.ycderman.qmediacenter.yml`, replace the
`type: dir` source with:

```yaml
    sources:
      - type: git
        url: https://github.com/ycderman/qmediacenter
        tag: vX.Y.Z
        commit: <output of git rev-parse HEAD>
```

Also bump `SETUPTOOLS_SCM_PRETEND_VERSION` to match the tag.

Test with flatpak-builder before publishing.

## 7. Flathub PR

Before re-opening the Flathub PR:
- Switch source to `type: git` with the release tag and commit hash
- Fill in the Flathub submission checklist
- Record a short screen capture (IPTV channel loading, local library browse)
- Note AI policy: all bundled code must be reviewed; generated code is acceptable
  if reviewed and understood

## 8. AUR PKGBUILD (Sprint 4)

Update `packaging/arch/PKGBUILD`:
```
pkgver=X.Y.Z
source=("$pkgname-$pkgver.tar.gz::https://github.com/ycderman/qmediacenter/archive/vX.Y.Z.tar.gz")
sha256sums=('...')
```

Run `makepkg -si` in a clean Arch environment, then push to AUR:
```bash
ssh aur@aur.archlinux.org qmediacenter.git
```

## 9. Nixpkgs PR (Sprint 4)

After adding `ycderman` to `nixpkgs/maintainers/maintainer-list.nix`:
- Submit `pkgs/applications/video/qmediacenter/default.nix`
- Point to the sdist on PyPI or tarball on GitHub releases
- Run `nix-build -A python3Packages.qmediacenter` against nixpkgs checkout

## Version numbering

QMediaCenter uses [Semantic Versioning](https://semver.org/):

- `0.x.y` — pre-stable; packaging and API may change
- `1.0.0` — first stable release (Flathub accepted + Nixpkgs merged)
- Patch releases (`x.y.Z`) for bug fixes
- Minor releases (`x.Y.0`) for new features
- `setuptools-scm` derives the version from git tags automatically
