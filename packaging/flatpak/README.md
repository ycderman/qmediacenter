# Flatpak packaging

```bash
flatpak-builder --force-clean /tmp/qmc-build io.github.ycderman.qmediacenter.yml
flatpak-builder --run /tmp/qmc-build io.github.ycderman.qmediacenter.yml qmediacenter --version
```

See `docs/FLATPAK.md` for full documentation.
