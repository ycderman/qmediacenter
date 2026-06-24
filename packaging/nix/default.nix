{ pkgs ? import <nixpkgs> {} }:

let
  # Filter out build artifacts so the Nix sandbox doesn't pick up local
  # dist/*.whl files, which would cause pypaInstallHook to install each
  # wheel twice and fail with FileExistsError.
  repoRoot = pkgs.lib.cleanSourceWith {
    src = ../..;
    filter = path: type:
      let rel = pkgs.lib.removePrefix (toString ../.. + "/") path;
      in !pkgs.lib.hasPrefix "dist/" rel
      && !pkgs.lib.hasPrefix "build/" rel
      && !pkgs.lib.hasPrefix "result" rel
      && !pkgs.lib.hasSuffix ".egg-info" rel
      && !pkgs.lib.hasPrefix "__pycache__" (builtins.baseNameOf path);
  };
in

pkgs.callPackage ./qmediacenter.nix {
  src     = repoRoot;
  version = "0.0.0+dev";
}
