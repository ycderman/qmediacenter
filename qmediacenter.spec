# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    datas=[('data', 'data')],
    hiddenimports=['media.plex', 'media.emby'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

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
