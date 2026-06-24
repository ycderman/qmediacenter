{ lib
, python3
, fetchFromGitHub
, qt6
, libGL
, mpv
# Set src = ./. when using from the repo root; fetchFromGitHub for a pinned release.
, src ? null
, version ? "git"
}:

python3.pkgs.buildPythonApplication {
  pname = "qmediacenter";
  inherit version;

  src = if src != null then src else (fetchFromGitHub {
    owner = "ycderman";
    repo  = "qmediacenter";
    # Replace with current commit hash when pinning a release:
    rev    = "HEAD";
    sha256 = lib.fakeSha256;
  });

  format = "pyproject";

  nativeBuildInputs = with python3.pkgs; [
    setuptools
    setuptools-scm
  ] ++ [ qt6.wrapQtAppsHook ];

  propagatedBuildInputs = with python3.pkgs; [
    pyside6
    mpv
    pyopengl
    requests
    yt-dlp
  ];

  buildInputs = [
    libGL
    mpv          # libmpv.so at runtime for the ctypes binding
    qt6.qtwayland
  ];

  # setuptools-scm cannot detect the version from a Nix store path (no .git).
  SETUPTOOLS_SCM_PRETEND_VERSION = version;

  # pythonRuntimeDepsCheckHook compares Requires-Dist names from the wheel
  # against installed dist-info names.  python3Packages.mpv ships as pname
  # "mpv" but the hook can't resolve it against Requires-Dist: mpv>=1.0
  # (PyPA normalisation mismatch).  The Nix closure already enforces all
  # runtime deps are present, so skipping this check is safe.
  dontCheckRuntimeDeps = true;

  # Qt needs to find the platform plugin; wrap the binary so QT_PLUGIN_PATH
  # and QT_QPA_PLATFORM_PLUGIN_PATH include the PySide6 plugin tree.
  postInstall = ''
    # Desktop integration files
    install -Dm644 packaging/qmediacenter.desktop \
      $out/share/applications/io.github.ycderman.qmediacenter.desktop
    install -Dm644 data/io.github.ycderman.qmediacenter.metainfo.xml \
      $out/share/metainfo/io.github.ycderman.qmediacenter.metainfo.xml
    install -Dm644 data/qmediacenter.png \
      $out/share/icons/hicolor/256x256/apps/io.github.ycderman.qmediacenter.png

    # wrapQtAppsHook handles QT_PLUGIN_PATH / QT_QPA_PLATFORM_PLUGIN_PATH.
    # Add libmpv to LD_LIBRARY_PATH so the python-mpv ctypes binding finds it.
    qtWrapperArgs+=(--prefix LD_LIBRARY_PATH : "${mpv}/lib")
  '';

  # Tests require a live display or offscreen platform; skip during build.
  doCheck = false;

  meta = with lib; {
    description = "Qt6/libmpv media center — IPTV, Emby, Plex and local media";
    homepage    = "https://github.com/ycderman/qmediacenter";
    license     = licenses.mit;
    platforms   = platforms.linux;
    mainProgram = "qmediacenter";
    maintainers = [ maintainers.ycderman or {} ];
  };
}
