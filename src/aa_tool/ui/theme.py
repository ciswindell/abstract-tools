"""Application theme: bundled fonts + a warm "archival paper" Qt stylesheet.

The visual language (paper tones, pine accent, Fraunces/Hanken/Spline Sans Mono
type) is shared across every screen so the app reads as one cohesive tool.
"""

from PySide6 import QtGui, QtWidgets

from aa_tool.resources import resource_path

# Font family names as registered by their TTFs (used in the stylesheet below).
# A clean modern grotesque throughout for a contemporary app feel; a mono face
# for numeric/source data.
SANS = "Hanken Grotesk"
MONO = "Spline Sans Mono"

_FONT_FILES = [
    "HankenGrotesk.ttf",
    "SplineSansMono.ttf",
]

# Palette
PAPER = "#f4efe5"
PAPER_2 = "#ebe4d6"
CARD = "#fbf8f1"
INK = "#211d17"
INK_SOFT = "#5c5347"
LINE = "#d9d0bf"
PINE = "#1d5c54"
PINE_DEEP = "#16463f"
MAT = "#2a2620"
GREEN = "#2f7d4f"
YELLOW = "#d8a72a"

STYLESHEET = f"""
* {{
    font-family: "{SANS}";
    font-size: 14px;
    color: {INK};
}}
QMainWindow, QWidget#screen {{ background: {PAPER}; }}

/* ---- Header ---- */
QWidget#header {{ background: {CARD}; border-bottom: 1px solid {LINE}; }}
QLabel#brand {{ font-family: "{SANS}"; font-size: 20px; font-weight: 700; letter-spacing: -0.2px; }}
QLabel#step {{
    font-size: 11px; color: {INK_SOFT};
    padding: 4px 12px; border-radius: 11px; background: transparent;
}}
QLabel#stepActive {{
    font-size: 11px; color: white; font-weight: 600;
    padding: 4px 12px; border-radius: 11px; background: {PINE};
}}
QLabel#status {{ font-family: "{MONO}"; font-size: 12px; color: {INK_SOFT}; }}
QLabel#pillText {{ font-size: 12px; font-weight: 600; color: {INK}; }}
QProgressBar#pill {{
    background: #d9d0bf; border: none; border-radius: 4px;
    max-height: 7px; min-height: 7px; min-width: 64px;
}}
QProgressBar#pill::chunk {{ background: {GREEN}; border-radius: 4px; }}

/* ---- Rail ---- */
QScrollArea#rail, QWidget#railInner {{ background: {PAPER_2}; border: none; }}
QWidget#rail {{ border-right: 1px solid {LINE}; }}
QLabel#railTitle {{
    font-size: 11px; color: {INK_SOFT}; font-weight: 600; padding: 4px 6px;
}}
QLabel#railTitle {{
    font-size: 11px; color: {INK_SOFT}; font-weight: 600; padding: 4px 6px;
}}
/* Classification dots in front of each page row. */
QFrame#dotNone {{ background: transparent; border-radius: 4px; }}
QFrame#dotFirst {{ background: {GREEN}; border-radius: 4px; }}
QFrame#dotCont {{ background: {YELLOW}; border-radius: 4px; }}
/* Hairline between source files. */
QFrame#railSep {{ background: #d3c9b6; }}
QFrame#pageRow {{ background: transparent; border-radius: 7px; }}
QFrame#pageRow:hover {{ background: #e2d9c8; }}
QFrame#pageRowCur {{ background: {CARD}; border-radius: 7px; border: 2px solid {PINE}; }}
QLabel#pageLabel {{ color: {INK_SOFT}; }}
QLabel#pageLabelCur {{ color: {INK}; font-weight: 700; }}
QLabel#pageSrc {{ font-family: "{MONO}"; font-size: 11px; color: {INK_SOFT}; }}

/* ---- Control strip ---- */
QWidget#controls {{ background: {PAPER_2}; border-bottom: 1px solid {LINE}; }}
QPushButton#nav {{
    background: {CARD}; border: 1px solid {LINE}; border-radius: 9px;
    font-size: 18px; min-width: 44px; min-height: 48px;
}}
QPushButton#nav:hover {{ background: white; }}
QPushButton#zoom {{
    background: {CARD}; border: 1px solid {LINE}; border-radius: 7px;
    font-weight: 600; padding: 8px 11px;
}}
QPushButton#zoom:hover {{ background: white; }}
QLabel#zoomLabel {{ font-family: "{MONO}"; font-size: 12px; color: {INK_SOFT}; }}
QPushButton#finish {{
    background: {INK}; color: {PAPER}; border: none; border-radius: 10px;
    font-weight: 700; font-size: 14px; padding: 0 20px; min-height: 48px;
}}
QPushButton#finish:hover {{ background: #000; }}

/* ---- Classify buttons (color state shows current classification) ---- */
QPushButton#classify {{
    background: {CARD}; border: 2px solid {LINE}; border-radius: 10px;
    color: {INK_SOFT}; font-weight: 700; font-size: 15px; min-height: 48px;
}}
QPushButton#classify:hover {{ background: white; }}
QPushButton#classify[active="true"][kind="first"] {{
    background: {GREEN}; border-color: {GREEN}; color: white;
}}
QPushButton#classify[active="true"][kind="cont"] {{
    background: {YELLOW}; border-color: {YELLOW}; color: #3a2e08;
}}
QPushButton#classify:disabled {{ color: #b3a994; border-color: {LINE}; }}

/* ---- Canvas / preview ---- */
QScrollArea#canvas {{ background: {MAT}; border: none; }}
QWidget#canvasInner {{ background: {MAT}; }}
QLabel#pageImage {{ background: white; }}

/* ---- Footer legend ---- */
QWidget#legend {{ background: {CARD}; border-top: 1px solid {LINE}; }}
QLabel#legend {{ font-size: 12px; color: {INK_SOFT}; }}

/* ---- Generic / folder + export screens ---- */
QLabel#h1 {{ font-family: "{SANS}"; font-size: 28px; font-weight: 700; letter-spacing: -0.4px; }}
QLabel#sub {{ font-size: 15px; color: {INK_SOFT}; }}
QPushButton#primary {{
    background: {PINE}; color: white; border: none; border-radius: 10px;
    font-weight: 700; font-size: 15px; padding: 13px 26px;
}}
QPushButton#primary:hover {{ background: {PINE_DEEP}; }}
QPushButton#ghost {{
    background: {CARD}; color: {INK}; border: 1px solid {LINE};
    border-radius: 10px; font-weight: 600; font-size: 14px; padding: 12px 20px;
}}
QPushButton#ghost:hover {{ background: white; }}
QLabel#chip {{
    background: {PAPER_2}; border: 1px solid {LINE}; border-radius: 18px;
    padding: 8px 16px; font-weight: 600; font-size: 13px;
}}
QLabel#warn {{ color: #7a5c00; font-size: 13px; }}
QLabel#success {{ color: {GREEN}; font-size: 15px; font-weight: 700; }}

/* Dialogs (kept readable and on-theme) */
QMessageBox {{ background: {CARD}; }}
QMessageBox QLabel {{ color: {INK}; }}
QMessageBox QPushButton {{
    background: {PINE}; color: white; border: none; border-radius: 8px;
    font-weight: 600; padding: 7px 18px; min-width: 64px;
}}
QMessageBox QPushButton:hover {{ background: {PINE_DEEP}; }}
QLabel#savePath {{
    font-family: "{MONO}"; font-size: 12px; color: {INK_SOFT};
    background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; padding: 10px 12px;
}}

/* ---- Home board ---- */
QWidget#boardTop {{ background: {CARD}; border-bottom: 1px solid {LINE}; }}
QWidget#boardBody {{ background: {PAPER}; }}
QLabel#boardBrand {{ font-family: "{SANS}"; font-size: 19px; font-weight: 800; letter-spacing: -0.3px; }}
QLabel#boardHero {{ font-family: "{SANS}"; font-size: 34px; font-weight: 800; letter-spacing: -0.8px; }}
QLabel#boardHeroSub {{ font-size: 15px; color: {INK_SOFT}; }}
QLabel#secHead {{ font-size: 13px; font-weight: 700; color: {INK_SOFT}; }}
QFrame#secRule {{ background: {LINE}; max-height: 1px; min-height: 1px; }}
QFrame#toolCard {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 14px; }}
QFrame#toolCard:hover {{ border-color: {PINE}; }}
QLabel#toolCardName {{ font-size: 16px; font-weight: 700; }}
QLabel#toolCardDesc {{ font-size: 13px; color: {INK_SOFT}; }}
QLabel#toolCardIcon {{ background: #e7efe9; border-radius: 11px; }}

/* ---- Back to Tools link ---- */
QPushButton#backToTools {{
    background: transparent; border: none; color: {PINE};
    font-weight: 700; font-size: 14px; padding: 0; text-align: left;
}}
QPushButton#backToTools:hover {{ color: {PINE_DEEP}; }}
QFrame#hdrDivider {{ background: {LINE}; max-width: 1px; min-width: 1px; }}
"""


def load_fonts() -> None:
    """Register the bundled TTFs so the stylesheet font-family names resolve."""
    for name in _FONT_FILES:
        QtGui.QFontDatabase.addApplicationFont(str(resource_path(f"fonts/{name}")))


def apply_theme(app: QtWidgets.QApplication) -> None:
    load_fonts()
    app.setStyleSheet(STYLESHEET)
