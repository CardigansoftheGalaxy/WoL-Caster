# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for WoL-Caster
Builds GUI and CLI versions for all platforms
"""

import sys
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.building.osx import BUNDLE

# Common settings
block_cipher = None
app_name = 'WoL-Caster'
script_name = 'wol_caster.py'

# Analysis for main application
a = Analysis(
    [script_name],
    pathex=[],
    binaries=[],
    datas=[
        ('README.md', '.'),
        ('requirements.txt', '.'),
    ],
    hiddenimports=[
        'netifaces',
        'tkinter',
        'tkinter.messagebox',
        'ipaddress',
        'socket',
        'threading',
        'concurrent.futures',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'PIL',
        'scipy',
        'pandas',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# GUI version (windowed)
exe_gui = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=f'{app_name}-GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console for GUI version
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
)

# CLI version (console)
exe_cli = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=f'{app_name}-CLI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Console for CLI version
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
)

# Universal version (smart detection)
exe_universal = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Enable console but app will detect mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
)

# macOS App Bundle (GUI version)
if sys.platform == 'darwin':
    app = BUNDLE(
        exe_gui,
        name=f'{app_name}.app',
        icon='assets/icon.icns' if os.path.exists('assets/icon.icns') else None,
        bundle_identifier='com.cardigansofthegalaxy.wolcaster',
        version='1.0.0',
        info_plist={
            'CFBundleDisplayName': 'WoL-Caster',
            'CFBundleName': 'WoL-Caster',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'LSMinimumSystemVersion': '10.10.0',
            'NSHighResolutionCapable': True,
            'NSSupportsAutomaticGraphicsSwitching': True,
            'CFBundleDocumentTypes': [],
            'LSEnvironment': {
                'PATH': '/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin'
            }
        }
    )

# Collection for distribution
coll = COLLECT(
    exe_universal,
    exe_gui,
    exe_cli,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=app_name
)
