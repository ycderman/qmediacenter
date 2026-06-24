{ lib
, python3
, fetchFromGitHub
, qt6
, libGL
# pkgs.mpv — provides libmpv.so; distinct from python3Packages.mpv below.
, mpv
# Override src/version when calling from default.nix or a flake.
# When src is null the derivation falls back to fetchFromGitHub with a
# placeholder sha256 — replace rev/sha256 before using for a real release.
, src ? null
, version ? "git"
}:

python3.pkgs.buildPythonApplication {
  pname = "qmediacenter";
  inherit version;

  src = if src != null then src else fetchFromGitHub {
    owner  = "ycderman";
    repo   = "qmediacenter";
    # Pin to a release tag before submitting to nixpkgs:
    rev    = "HEAD";
    sha256 = lib.fakeSha256;
  };

  format = "pyproject";

  nativeBuildInputs = with python3.pkgs; [
    setuptools
    setuptools-scm
    # wrapQtAppsHook sets QT_PLUGIN_PATH / QT_QPA_PLATFORM_PLUGIN_PATH so
    # PySide6's bundled platform plugins (wayland, xcb) are found at runtime.
  ] ++ [ qt6.wrapQtAppsHook ];

  # python3Packages.mpv is the pure-Python ctypes binding (python-mpv on PyPI).
  # It is distinct from the pkgs.mpv argument above which provides libmpv.so.
  propagatedBuildInputs = with python3.pkgs; [
    pyside6
    mpv
    pyopengl
    requests
    yt-dlp
  ];

  # libGL: OpenGL for the mpv OpenGL render API.
  # pkgs.mpv: libmpv.so loaded at runtime by the python-mpv ctypes binding.
  # qt6.qtwayland: Wayland platform plugin for Qt.
  buildInputs = [
    libGL
    mpv
    qt6.qtwayland
  ];

  # setuptools-scm cannot determine the version from a Nix store path (no .git).
  SETUPTOOLS_SCM_PRETEND_VERSION = version;

  # pythonRuntimeDepsCheckHook verifies Requires-Dist entries against installed
  # dist-info names.  python3Packages.mpv (pname = "mpv") is not resolved
  # against "Requires-Dist: mpv>=1.0" due to a PyPA normalisation edge case.
  # Disabling is safe: the Nix closure already enforces all runtime deps.
  dontCheckRuntimeDeps = true;

  postInstall = ''
    install -Dm644 packaging/qmediacenter.desktop \
      $out/share/applications/io.github.ycderman.qmediacenter.desktop
    install -Dm644 data/io.github.ycderman.qmediacenter.metainfo.xml \
      $out/share/metainfo/io.github.ycderman.qmediacenter.metainfo.xml
    install -Dm644 data/qmediacenter.png \
      $out/share/icons/hicolor/256x256/apps/io.github.ycderman.qmediacenter.png

    # Add libmpv to LD_LIBRARY_PATH so the python-mpv ctypes binding resolves
    # libmpv.so.  wrapQtAppsHook applies this during the fixup phase.
    qtWrapperArgs+=(--prefix LD_LIBRARY_PATH : "${mpv}/lib")
  '';

  # Tests require a connected display (or QT_QPA_PLATFORM=offscreen + libmpv).
  doCheck = false;

  meta = with lib; {
    description = "Qt6/libmpv media center — IPTV, Emby, Plex and local media";
    homepage    = "https://github.com/ycderman/qmediacenter";
    license     = licenses.mit;
    platforms   = platforms.linux;
    mainProgram = "qmediacenter";
    # maintainers field is intentionally omitted in this development derivation.
    # When submitting to nixpkgs, add yourself to maintainers/maintainer-list.nix
    # and add: maintainers = with maintainers; [ ycderman ];
  };
}
