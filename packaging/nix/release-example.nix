# Pinned release build for v0.7.0.
# Use this as a template for Nixpkgs PRs, flake inputs, and home-manager overlays.
# Update version, rev, and hash for each new release.
# Get hash with: nix-build with lib.fakeHash; copy from error output.
# NOTE: fetchFromGitHub uses NAR hash (not raw tarball sha256).

{ pkgs ? import <nixpkgs> {} }:

pkgs.callPackage ./qmediacenter.nix {
  version = "0.7.0";
  src = pkgs.fetchFromGitHub {
    owner  = "ycderman";
    repo   = "qmediacenter";
    rev    = "v0.7.0";
    hash   = "sha256-Z51m1k8AV2BxcevYKfrTJo1upCzezvqK/+ypX+LcYcY=";
  };
}
