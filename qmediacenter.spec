# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    datas=[('data', 'data')],
    hiddenimports=['media.plex', 'media.emby', 'dbus', 'dbus.mainloop.glib', 'gi', 'gi.repository.GLib'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# Exclude system libraries that vary by distro/version; let the OS supply them.
# Bundling these causes GLIBCXX / OPENSSL version conflicts on newer targets.
_EXCLUDE_PREFIXES = (
    'libstdc++', 'libgcc_s', 'libgcc',
    'libssl', 'libcrypto',
    'libva', 'libdrm',
    'libc.', 'libm.', 'libdl.', 'libpthread.', 'librt.',
)
a.binaries = [b for b in a.binaries
              if not any(b[0].startswith(p) for p in _EXCLUDE_PREFIXES)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='qmediacenter',
    debug=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='qmediacenter',
)
