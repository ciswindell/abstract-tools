# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["main.py"],
    pathex=["src"],
    binaries=[],
    # Bundle the Excel template into aa_tool/resources/ inside the one-file build,
    # matching the layout resource_path() expects under sys._MEIPASS.
    datas=[
        ("src/aa_tool/resources/Template File Documents.xlsx", "aa_tool/resources"),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="AA State Abstract Tool",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
