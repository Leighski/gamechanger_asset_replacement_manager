# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — build: pyinstaller gamechanger_rename_manager/build/pyinstaller.spec

import sys
from pathlib import Path

import os

_spec_dir = os.path.dirname(os.path.abspath(SPEC))
ROOT = Path(_spec_dir).resolve().parent
REPO = ROOT.parent

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(REPO)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "customtkinter",
        "PIL",
        "PIL._tkinter_finder",
        "boto3",
        "botocore",
        "requests",
        "pandas",
        "openpyxl",
    ],
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
    name="Gamechanger Rename Manager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Gamechanger Rename Manager",
)
app = BUNDLE(
    coll,
    name="Gamechanger Rename Manager.app",
    icon=None,
    bundle_identifier="com.gamechanger.rename-manager",
    info_plist={
        "CFBundleName": "Gamechanger Rename Manager",
        "CFBundleDisplayName": "Gamechanger Rename Manager",
        "NSHighResolutionCapable": True,
    },
)
