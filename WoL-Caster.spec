# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['wol_caster.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/oui_database.txt', 'assets'), ('assets/Wol-Caster.icns', 'assets')],
    hiddenimports=['tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'tkinter.filedialog'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WoL-Caster',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/Wol-Caster.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WoL-Caster',
)
app = BUNDLE(
    coll,
    name='WoL-Caster.app',
    icon='assets/Wol-Caster.icns',
    bundle_identifier='com.wolcaster.app',
    force_menu_bar=False,
    info_plist={
        'CFBundleName': 'WoL-Caster',
        'CFBundleDisplayName': 'WoL-Caster',
        'CFBundleIdentifier': 'com.wolcaster.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': '© 2025 Cardigans of the Galaxy. MIT License.',

        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.12.0',
        'NSRequiresAquaSystemAppearance': False,
        'NSMainNibFile': '',
        'NSPrincipalClass': 'NSApplication',
        'LSBackgroundOnly': False,
        'LSUIElement': False,
        'NSRequiresAquaSystemAppearance': False,
        'CFBundleDocumentTypes': [],
        'CFBundleURLTypes': [],
        'NSAppleEventsUsageDescription': '',
        'NSSupportsAutomaticTermination': True,
        'NSSupportsSuddenTermination': True,
    },
)
