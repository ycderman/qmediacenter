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
# Push main first so the tag points to a commit already on remote
git push origin main
git push origin vX.Y.Z
```

## 4. GitHub Release

Push the tag; CI will build `.deb` and `.rpm` via PyInstaller + fpm.
Create a GitHub Release from the tag and attach the CI artifacts.

## 5. Update Nix derivation for release

**Requires: tag already pushed to remote** (GitHub tarball must exist).

Use `packaging/nix/release-example.nix` as a template. The `lib.fakeHash`
placeholder triggers a build failure that prints the real hash:

```bash
# Build once with fakeHash — it will fail and print the correct hash
nix-build packaging/nix/release-example.nix
# Error output contains something like:
#   got:    sha256-AAAA...
# Paste that hash into release-example.nix, then:
nix-build packaging/nix/release-example.nix  # should succeed now
./result/bin/qmediacenter --version

# Alternative: prefetch directly (requires tag on remote)
nix-prefetch-url --unpack \
  https://github.com/ycderman/qmediacenter/archive/refs/tags/vX.Y.Z.tar.gz
```

## 6. Update Flatpak manifest for release

**Requires: tag already pushed to remote.**

`packaging/flatpak/io.github.ycderman.qmediacenter.flathub.yml` already uses
`type: git`. After pushing the tag, fill in the commit hash:

```bash
# For annotated tags: rev-parse on the ref returns the tag object, not the commit.
# Use rev-list or the ^{} dereference operator instead:
git rev-list -n 1 vX.Y.Z
# Equivalent: git rev-parse vX.Y.Z^{}
```

Update `commit:` in `.flathub.yml` with the output.
Also confirm `SETUPTOOLS_SCM_PRETEND_VERSION` matches the tag version.

Test the release manifest before submitting:

```bash
flatpak-builder --force-clean /tmp/qmc-flathub-build \
  packaging/flatpak/io.github.ycderman.qmediacenter.flathub.yml
flatpak-builder --run /tmp/qmc-flathub-build \
  packaging/flatpak/io.github.ycderman.qmediacenter.flathub.yml qmediacenter --version
```

## 7. Flathub PR

Before re-opening the Flathub PR:
- `commit:` field in `.flathub.yml` contains the real hash (not PLACEHOLDER)
- Fill in the Flathub submission checklist
- Record a short screen capture (IPTV channel loading, local library browse)
- Note AI policy: all bundled code must be reviewed; generated code is acceptable
  if reviewed and understood

## 8. AUR PKGBUILD

**Requires: tag already pushed to remote** (GitHub tarball must exist).

Get the sha256sum from the GitHub tarball:

```bash
curl -L https://github.com/ycderman/qmediacenter/archive/refs/tags/vX.Y.Z.tar.gz \
  | sha256sum
# or: makepkg -g (from inside packaging/arch/ on an Arch system)
```

Update `packaging/arch/PKGBUILD`:
- Replace `sha256sums=('SKIP')` with the real hash
- **Never push to AUR with SKIP**

Generate `.SRCINFO` and push:

```bash
cd packaging/arch
makepkg --printsrcinfo > .SRCINFO
git clone ssh://aur@aur.archlinux.org/qmediacenter.git aur-qmediacenter
cp PKGBUILD .SRCINFO aur-qmediacenter/
cd aur-qmediacenter && git add -A && git commit -m "Initial release X.Y.Z"
git push
```

## 9. Nixpkgs PR

**Requires: tag on remote and real hash in `release-example.nix`.**

After adding `ycderman` to `nixpkgs/maintainers/maintainer-list.nix`:
- Copy `packaging/nix/qmediacenter.nix` to `pkgs/applications/video/qmediacenter/default.nix`
- Update `fetchFromGitHub` with real rev + hash (from step 5)
- Run `nix-build -A python3Packages.qmediacenter` against nixpkgs checkout
- Open PR against `nixpkgs/master`

## Version numbering

QMediaCenter uses [Semantic Versioning](https://semver.org/):

- `0.x.y` — pre-stable; packaging and API may change
- `1.0.0` — first stable release (Flathub accepted + Nixpkgs merged)
- Patch releases (`x.y.Z`) for bug fixes
- Minor releases (`x.Y.0`) for new features
- `setuptools-scm` derives the version from git tags automatically
