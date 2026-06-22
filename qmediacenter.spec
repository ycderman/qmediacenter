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

# Drop bundled libstdc++/libgcc so the system version (which matches the
# system's libavfilter/libmpv) is used instead of the older build-host one.
a.binaries = [b for b in a.binaries
              if not b[0].startswith(('libstdc++', 'libgcc_s', 'libgcc'))]

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
