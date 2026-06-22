# Build:  nix-build package.nix      Run:  ./result/bin/qplayer
{ pkgs ? import <nixpkgs> { } }:
let
  py = pkgs.python3.withPackages (ps: with ps; [
    pyside6
    mpv          # python-mpv
    pyopengl
    requests
    yt-dlp
    dbus-python  # MPRIS2 for KDE Connect
    pygobject3   # GLib main loop for dbus-python
  ]);
in
pkgs.stdenv.mkDerivation {
  pname = "qplayer";
  version = "0.1.0";
  src = ./.;

  nativeBuildInputs = [ pkgs.makeWrapper ];
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p $out/share/qplayer $out/bin
    cp -r main.py iptv ui $out/share/qplayer/
    makeWrapper ${py}/bin/python3 $out/bin/qplayer \
      --add-flags "$out/share/qplayer/main.py" \
      --chdir "$out/share/qplayer" \
      --prefix LD_LIBRARY_PATH : "${pkgs.libglvnd}/lib:${pkgs.libGL}/lib" \
      --set LIBVA_DRIVER_NAME iHD \
      --set LC_NUMERIC C \
      --set QT_QPA_PLATFORM "wayland;xcb"
    runHook postInstall
  '';

  meta = with pkgs.lib; {
    description = "Qt6/libmpv IPTV player with Xtream Codes support";
    license = licenses.mit;
    platforms = platforms.linux;
    mainProgram = "qplayer";
  };
}
