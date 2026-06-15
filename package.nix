# Build:  nix-build package.nix      Run:  ./result/bin/qtiptv
{ pkgs ? import <nixpkgs> { } }:
let
  py = pkgs.python3.withPackages (ps: with ps; [
    pyside6
    mpv          # python-mpv
    pyopengl
    requests
    yt-dlp
  ]);
in
pkgs.stdenv.mkDerivation {
  pname = "qtiptv";
  version = "0.1.0";
  src = ./.;

  nativeBuildInputs = [ pkgs.makeWrapper ];
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p $out/share/qtiptv $out/bin
    cp -r main.py iptv ui $out/share/qtiptv/
    makeWrapper ${py}/bin/python3 $out/bin/qtiptv \
      --add-flags "$out/share/qtiptv/main.py" \
      --chdir "$out/share/qtiptv" \
      --set LIBVA_DRIVER_NAME iHD \
      --set LC_NUMERIC C \
      --set QT_QPA_PLATFORM "wayland;xcb"
    runHook postInstall
  '';

  meta = with pkgs.lib; {
    description = "Qt6/libmpv IPTV player with Xtream Codes support";
    license = licenses.mit;
    platforms = platforms.linux;
    mainProgram = "qtiptv";
  };
}
