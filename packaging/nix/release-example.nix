# Example: how to pin qmediacenter.nix to a specific release tag.
#
# This file is NOT used by nix-build directly — it is a reference for:
#   - Nixpkgs PR submissions
#   - Flake inputs
#   - Home-manager overlays
#
# Usage:
#   nix-build release-example.nix
#
# IMPORTANT: replace lib.fakeHash with the real hash after running once.
# The build will fail with a hash mismatch and print the correct value.

{ pkgs ? import <nixpkgs> {} }:

pkgs.callPackage ./qmediacenter.nix {
  version = "0.7.0";
  src = pkgs.fetchFromGitHub {
    owner  = "ycderman";
    repo   = "qmediacenter";
    rev    = "v0.7.0";
    # Run the following to get the correct hash after tagging:
    #   nix-prefetch-url --unpack \
    #     https://github.com/ycderman/qmediacenter/archive/refs/tags/v0.7.0.tar.gz
    # Or with nix flakes:
    #   nix flake prefetch github:ycderman/qmediacenter/v0.7.0
    hash = pkgs.lib.fakeHash;
  };
}
