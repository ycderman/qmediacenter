# Flathub submission staging

This directory is the staging area for the Flathub PR submission.

## What goes into the Flathub repo

The Flathub submission repository contains only two files at the root:

```
io.github.ycderman.qmediacenter.yml   ← copy from this directory
flathub.json                          ← (optional, for PR metadata)
```

## Current release

- Source: `type: git`, `tag: v0.7.0`
- Commit: `9193a174a8d0b312648949086ca4bec90a91245a`
- `SETUPTOOLS_SCM_PRETEND_VERSION=0.7.0`

## Build and test the manifest

Run from the repo root:

```bash
# Full build (takes 10–20 min first run; cached on subsequent runs)
flatpak-builder --force-clean build-dir \
  packaging/flatpak/flathub/io.github.ycderman.qmediacenter.yml

# Smoke tests
flatpak-builder --run build-dir \
  packaging/flatpak/flathub/io.github.ycderman.qmediacenter.yml qmediacenter --version
flatpak-builder --run build-dir \
  packaging/flatpak/flathub/io.github.ycderman.qmediacenter.yml qmediacenter --help
```

## Submitting to Flathub

1. Fork https://github.com/flathub/flathub
2. Create branch: `new-app/io.github.ycderman.qmediacenter`
3. Copy `io.github.ycderman.qmediacenter.yml` to repo root
4. Open PR against `flathub/flathub`

See `docs/FLATHUB_SUBMISSION.md` for the full submission checklist.

## Keeping in sync

When `packaging/flatpak/io.github.ycderman.qmediacenter.flathub.yml` changes
(new version, dependency update), copy it here and update the Flathub PR.
This directory intentionally mirrors the authoritative `.flathub.yml`.
