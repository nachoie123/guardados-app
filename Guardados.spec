# -*- mode: python ; coding: utf-8 -*-
# Construir con ./build.sh (antes copia la web y rules.py de ~/Projects/ig-saved).
a = Analysis(
    ['app.py'],
    pathex=['vendor'],
    binaries=[('build/geo', '.'), ('build/sello', '.')],   # Apple Maps (tools/geo.swift) y candado AES-GCM (tools/sello.swift), universal2: los compila build.sh
    datas=[('web/panel', 'web/panel'), ('web/guardados', 'web/guardados'), ('web/mac', 'web/mac')],
    hiddenimports=['rules', 'selftest', 'probe', 'segno'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'faster_whisper', 'ctranslate2', 'av', 'numpy', 'PIL'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Guardados', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          disable_windowed_traceback=False, argv_emulation=False, target_arch='universal2',
          codesign_identity=None, entitlements_file=None, icon=['build_assets/icon.icns'])
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, upx_exclude=[], name='Guardados')
app = BUNDLE(coll, name='Guardados.app', icon='build_assets/icon.icns',
             # .mac: el de la app de iPhone es com.nachosanbenito.guardados y en los Mac con Apple silicon pueden coincidir
             bundle_identifier='com.nachosanbenito.guardados.mac',
             info_plist={'CFBundleShortVersionString': '1.1', 'CFBundleVersion': '1.1', 'NSHighResolutionCapable': True,
                         'LSMinimumSystemVersion': '11.0', 'NSHumanReadableCopyright': 'Guardados'})
