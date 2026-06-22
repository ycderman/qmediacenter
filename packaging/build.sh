#!/usr/bin/env bash
# Gereksinimler: pyinstaller, fpm (gem install fpm)
# NixOS: nix-shell -p ruby.gems.fpm python3Packages.pyinstaller
set -euo pipefail

VERSION="${1:-0.2.0}"
ARCH="x86_64"
DIST="dist/qmediacenter"

cd "$(dirname "$0")/.."

echo "==> PyInstaller build (v$VERSION)"
pyinstaller qmediacenter.spec --clean --noconfirm

echo "==> DEB paketi"
fpm -s dir -t deb \
  -n qmediacenter \
  -v "$VERSION" \
  -a "$ARCH" \
  --description "Qt6/mpv media center — IPTV, Emby, Plex + local/network library" \
  --url "https://github.com/ycderman/qmediacenter" \
  --license MIT \
  --depends "libmpv1 | libmpv2" \
  --category "video" \
  --deb-no-default-config-files \
  --after-install packaging/postinst \
  --after-remove packaging/postrm \
  --package dist/ \
  "$DIST/=/opt/qmediacenter/" \
  "packaging/qmediacenter.desktop=/usr/share/applications/io.github.ycderman.qmediacenter.desktop" \
  "data/qmediacenter.png=/usr/share/pixmaps/qmediacenter.png"

echo "==> RPM paketi"
fpm -s dir -t rpm \
  -n qmediacenter \
  -v "$VERSION" \
  -a "$ARCH" \
  --description "Qt6/mpv media center — IPTV, Emby, Plex + local/network library" \
  --url "https://github.com/ycderman/qmediacenter" \
  --license MIT \
  --depends "mpv-libs" \
  --category "Applications/Multimedia" \
  --after-install packaging/postinst \
  --after-remove packaging/postrm \
  --package dist/ \
  "$DIST/=/opt/qmediacenter/" \
  "packaging/qmediacenter.desktop=/usr/share/applications/io.github.ycderman.qmediacenter.desktop" \
  "data/qmediacenter.png=/usr/share/pixmaps/qmediacenter.png"

echo ""
echo "==> Hazır:"
ls dist/*.deb dist/*.rpm
