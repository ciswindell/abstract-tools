# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["main.py"],
    pathex=["src"],
    binaries=[],
    # Bundle the Excel template into abstract_tools/resources/ inside the one-file build,
    # matching the layout resource_path() expects under sys._MEIPASS.
    datas=[
        ("src/abstract_tools/resources/Template File Documents.xlsx", "abstract_tools/resources"),
        ("src/abstract_tools/resources/fonts/*.ttf", "abstract_tools/resources/fonts"),
        ("src/abstract_tools/resources/icons/*.svg", "abstract_tools/resources/icons"),
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
        # The SRP Parser reads/writes Excel via pandas, whose numeric backend
        # PyInstaller's static scan can miss.
        "pandas",
        "numpy",
        # Version stamped into _build_version.py by CI before the build;
        # imported lazily in version.py so list it explicitly.
        "abstract_tools._build_version",
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
