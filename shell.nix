# Dev shell for QtIPTV
# Usage:  nix-shell  then  python main.py
{ pkgs ? import <nixpkgs> { } }:
let
  py = pkgs.python3.withPackages (ps: with ps; [
    pyside6
    mpv          # python-mpv (import mpv)
    pyopengl
    requests
    yt-dlp
  ]);
in
pkgs.mkShell {
  packages = [ py pkgs.mpv pkgs.mpv-unwrapped pkgs.libGL ];

  shellHook = ''
    # libmpv for python-mpv (ctypes), and GL for the render widget
    export LD_LIBRARY_PATH=${pkgs.mpv-unwrapped}/lib:${pkgs.libGL}/lib:$LD_LIBRARY_PATH
    # Intel iHD VAAPI hardware decode (UHD 620)
    export LIBVA_DRIVER_NAME=iHD
    # Qt on Wayland; falls back to xcb automatically if needed
    export QT_QPA_PLATFORM="wayland;xcb"
    echo "QtIPTV dev shell — run: python main.py"
  '';
}
