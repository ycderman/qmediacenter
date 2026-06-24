%global pypi_name qmediacenter

Name:           qmediacenter
Version:        0.7.0
Release:        1%{?dist}
Summary:        Qt6/libmpv media center — IPTV, Emby, Plex and local media

License:        MIT
URL:            https://github.com/ycderman/qmediacenter
Source0:        https://github.com/ycderman/qmediacenter/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

# The application links against libmpv and requires Mesa at runtime.
# Marking as x86_64 because libmpv and Mesa are arch-specific.
# The Python source itself is noarch, but we can't guarantee cross-arch
# libmpv availability, so we leave this as the build arch.
#BuildArch:     noarch

BuildRequires:  python3-devel >= 3.11
BuildRequires:  python3-setuptools >= 68
BuildRequires:  python3-setuptools_scm
BuildRequires:  python3-pip
BuildRequires:  python3-wheel
BuildRequires:  desktop-file-utils
BuildRequires:  libappstream-glib
# pyproject-rpm-macros provides %%pyproject_* macros on Fedora 36+
BuildRequires:  pyproject-rpm-macros

# ── Runtime dependencies ────────────────────────────────────────────────────
# Package names are Fedora-centric; openSUSE equivalents in parentheses.
Requires:       python3 >= 3.11
# Fedora: python3-pyside6    openSUSE: python3-PySide6
Requires:       python3-pyside6
# Fedora: python3-mpv        openSUSE: python3-mpv  (may be unavailable; see note)
Requires:       python3-mpv
# Fedora: python3-pyopengl   openSUSE: python3-PyOpenGL
Requires:       python3-pyopengl
Requires:       python3-requests
# Fedora: yt-dlp             openSUSE: yt-dlp
Requires:       yt-dlp
# Fedora: mpv-libs           openSUSE: libmpv2
Requires:       mpv-libs
# Fedora: mesa-libGL         openSUSE: libGL1 / Mesa-libGL
Requires:       mesa-libGL
# Fedora: qt6-qtwayland      openSUSE: qt6-wayland
Requires:       qt6-qtwayland

# ── openSUSE note ───────────────────────────────────────────────────────────
# On openSUSE, substitute the following in BuildRequires/Requires:
#   python3-setuptools_scm  → python3-setuptools_scm (same)
#   python3-pyside6         → python3-PySide6
#   mpv-libs                → libmpv2
#   mesa-libGL              → libGL1 or Mesa-libGL
#   qt6-qtwayland           → qt6-wayland
#   libappstream-glib       → libappstream-glib or appstream-glib-devel
#   pyproject-rpm-macros    → python-rpm-macros (if available) or build manually
# python3-mpv availability on openSUSE: check OBS home:ycderman or bundling.

%description
QMediaCenter is a lightweight, open-source media center built with Qt6
(PySide6) and libmpv. It unifies IPTV (Xtream Codes, M3U), Emby, Plex,
and your local media library in one interface.

Features:
 * IPTV — Xtream Codes and M3U/M3U8 playlists; live, VOD and series
 * Emby and Plex — browse and stream server libraries
 * Local library — scan folders for video, music and photos
 * Hardware decoding via VAAPI (Intel, AMD); HEVC, AV1, H.264 and more
 * Continue Watching, Favourites, Recently Added home screen
 * MPRIS2 media player integration
 * Wayland and X11 support
 * Breeze Light and Breeze Dark themes

%prep
%autosetup -p1 -n %{name}-%{version}

%build
# SETUPTOOLS_SCM_PRETEND_VERSION is required because the source tarball
# extracted by rpmbuild has no .git directory.
SETUPTOOLS_SCM_PRETEND_VERSION=%{version} %pyproject_wheel

%install
SETUPTOOLS_SCM_PRETEND_VERSION=%{version} %pyproject_install
%pyproject_save_files %{pypi_name} qmediacenter themes data main

# Desktop integration
install -Dm644 packaging/qmediacenter.desktop \
  %{buildroot}%{_datadir}/applications/io.github.ycderman.qmediacenter.desktop
install -Dm644 data/io.github.ycderman.qmediacenter.metainfo.xml \
  %{buildroot}%{_datadir}/metainfo/io.github.ycderman.qmediacenter.metainfo.xml
install -Dm644 data/qmediacenter.png \
  %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/io.github.ycderman.qmediacenter.png
install -Dm644 LICENSE \
  %{buildroot}%{_datadir}/licenses/%{name}/LICENSE

%check
# Validate desktop file and AppStream metainfo
desktop-file-validate %{buildroot}%{_datadir}/applications/io.github.ycderman.qmediacenter.desktop
appstream-util validate-relax --nonet \
  %{buildroot}%{_datadir}/metainfo/io.github.ycderman.qmediacenter.metainfo.xml
# Headless smoke test — requires offscreen Qt platform
QT_QPA_PLATFORM=offscreen LC_NUMERIC=C \
  %{buildroot}%{_bindir}/qmediacenter --version

%files -f %{pyproject_files}
%license LICENSE
%{_bindir}/qmediacenter
%{_datadir}/applications/io.github.ycderman.qmediacenter.desktop
%{_datadir}/metainfo/io.github.ycderman.qmediacenter.metainfo.xml
%{_datadir}/icons/hicolor/256x256/apps/io.github.ycderman.qmediacenter.png
%{_datadir}/licenses/%{name}/LICENSE

%changelog
* Wed Jun 25 2026 ycderman <y.canderman@proton.me> - 0.7.0-1
- Initial RPM packaging
- Source-based build via pyproject.toml / setuptools-scm
- Nix and Flatpak development packaging added upstream
- Resources (themes, icon) accessible via importlib.resources after install
- CLI --version and --help work without a display server

* Tue Jun 24 2026 ycderman <y.canderman@proton.me> - 0.6.7-1
- Fix blank video in Flatpak: fbo-format=rgba8 (GL INVALID_ENUM with Mesa)

* Tue Jun 24 2026 ycderman <y.canderman@proton.me> - 0.6.5-1
- Fix codec detection on HLS: removed mpv fast profile (zeroed analyzeduration)

* Mon Jun 23 2026 ycderman <y.canderman@proton.me> - 0.6.3-1
- Faster channel switching: live buffer 200 MiB → 4 MiB

* Mon Jun 23 2026 ycderman <y.canderman@proton.me> - 0.6.0-1
- M3U/M3U8 playlist support alongside Xtream Codes
- App starts without login dialog
