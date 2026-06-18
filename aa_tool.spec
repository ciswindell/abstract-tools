# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["main.py"],
    pathex=["src"],
    binaries=[],
    # Bundle the Excel template into aa_tool/resources/ inside the one-file build,
    # matching the layout resource_path() expects under sys._MEIPASS.
    datas=[
        ("src/aa_tool/resources/Template File Documents.xlsx", "aa_tool/resources"),
        ("src/aa_tool/resources/fonts/*.ttf", "aa_tool/resources/fonts"),
        ("src/aa_tool/resources/icons/*.svg", "aa_tool/resources/icons"),
    ],
    # Pillow loads its format handlers dynamically, so PyInstaller's static
    # scan can miss them. The Batch TIFF→PDF Converter needs the TIFF reader,
    # the JPEG handler (old-style JPEG-compressed scans), and the PDF SAVE
    # handler; pypdf assembles the output. List them so they're always bundled.
    hiddenimports=[
        "PIL.TiffImagePlugin",
        "PIL.JpegImagePlugin",
        "PIL.PdfImagePlugin",
        "pypdf",
    ],
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
    name="Abstract Tools",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
