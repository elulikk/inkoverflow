"""Toolbar icons, drawn as small SVGs (32x32 grid) and rendered at every size Qt asks for.

Kept in code so the app needs no icon files and every icon shares one palette.
"""
from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

INK = "#3b4148"       # outlines
PAPER = "#ffffff"
EDGE = "#7a828c"      # paper edges
GREY = "#6d7680"
BLUE = "#2b6cb0"
GREEN = "#2e8b3a"
RED = "#c8312a"
ORANGE = "#e08a00"
TEAL = "#11869a"
GOLD = "#e8b740"
CMYK = ("#1f2328", "#00a0e0", "#e0007a", "#f2c800")

SIZES = (16, 20, 24, 32, 40, 48, 64)


def _doc(x=6, y=3, w=20, h=26, fold=6):
    """A sheet with a folded corner."""
    r = x + w
    return (f'<path d="M{x} {y}h{w - fold}l{fold} {fold}v{h - fold}H{x}z" fill="{PAPER}" '
            f'stroke="{EDGE}" stroke-width="1.2" stroke-linejoin="round"/>'
            f'<path d="M{r - fold} {y}v{fold}h{fold}" fill="#e6e9ed" stroke="{EDGE}" '
            f'stroke-width="1.2" stroke-linejoin="round"/>')


def _lines(x1, x2, ys, color="#9aa3ad", width=1.6):
    return "".join(f'<path d="M{x1} {y}H{x2}" stroke="{color}" stroke-width="{width}" '
                   'stroke-linecap="round"/>' for y in ys)


def _badge(color, glyph, cx=24, cy=24, r=7):
    """Round badge in the lower right corner with a white glyph."""
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" stroke="#fff" '
            f'stroke-width="1.6"/>{glyph}')


def _chip(x=5, y=5, s=18):
    pins = []
    for i in range(3):
        p = x + 4 + i * (s - 8) / 2
        pins.append(f'<path d="M{p} {y - 3}v3M{p} {y + s}v3M{x - 3} {p}h3M{x + s} {p}h3" '
                    f'stroke="{GREY}" stroke-width="1.8" stroke-linecap="round"/>')
    return ("".join(pins) + f'<rect x="{x}" y="{y}" width="{s}" height="{s}" rx="2" '
            f'fill="#4a5560" stroke="{INK}" stroke-width="1"/>'
            f'<circle cx="{x + 4}" cy="{y + 4}" r="1.4" fill="#9aa3ad"/>')


def _folder():
    return (f'<path d="M3 7h9l3 3h14v17H3z" fill="#d9a531" stroke="#b07f1a" '
            'stroke-width="1" stroke-linejoin="round"/>'
            f'<path d="M3 12h26v15H3z" fill="#f6d06b" stroke="#c9971f" stroke-width="1" '
            'stroke-linejoin="round"/>')


def _stairs(x0, color):
    """One colour of a nozzle-check pattern: short dashes stepping down."""
    out = []
    for i in range(7):
        y = 8 + i * 2.6
        dx = (i % 3) * 1.6
        out.append(f'<path d="M{x0 + dx} {y}h2.6" stroke="{color}" stroke-width="1.5"/>')
    return "".join(out)


def _drop(x, y, color="#2b8fd6", s=1.0):
    return (f'<path transform="translate({x} {y}) scale({s})" d="M0 0c-2.6 3.6-3.6 5.2-3.6 6.7'
            f'a3.6 3.6 0 0 0 7.2 0c0-1.5-1-3.1-3.6-6.7z" fill="{color}" '
            'stroke="#1c6aa8" stroke-width="0.8"/>')


def _clock(color, cx=16, cy=17, r=11):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{PAPER}" stroke="{color}" stroke-width="2.6"/>'
            + "".join(f'<path d="M{cx} {cy - r + 2.5}v1.8" stroke="{INK}" stroke-width="1.2" '
                      f'transform="rotate({a} {cx} {cy})"/>' for a in range(0, 360, 90))
            + f'<path d="M{cx} {cy - 6.5}V{cy}l4.5 3" fill="none" stroke="{INK}" '
              'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')


ARROW_WHITE = ('<path d="M27 24a3 3 0 1 1-0.9-2.1" fill="none" stroke="#fff" stroke-width="1.6" '
               'stroke-linecap="round"/><path d="M27.6 19.6v3.2h-3.2z" fill="#fff"/>')

BODIES = {
    "refresh": (
        f'<path d="M26.5 16A10.5 10.5 0 1 1 23.4 8.6" fill="none" stroke="{GREEN}" '
        'stroke-width="3.4" stroke-linecap="round"/>'
        f'<path d="M28.2 3.6v9.3h-9.3z" fill="{GREEN}" stroke="{GREEN}" stroke-width="1" '
        'stroke-linejoin="round"/>'),
    "printer": (
        f'<rect x="8" y="3" width="16" height="10" fill="{PAPER}" stroke="{EDGE}" stroke-width="1.2"/>'
        f'<rect x="3" y="11" width="26" height="12" rx="2.5" fill="{GREY}" stroke="{INK}" stroke-width="1.2"/>'
        f'<rect x="3" y="11" width="26" height="4" rx="2" fill="#8b949e"/>'
        f'<rect x="8" y="19" width="16" height="10" fill="{PAPER}" stroke="{EDGE}" stroke-width="1.2"/>'
        + _lines(11, 21, (23, 26), width=1.3)
        + f'<circle cx="25" cy="18" r="1.4" fill="#5fe08a"/>'),
    "detect": (
        f'<rect x="7" y="3" width="13" height="8" fill="{PAPER}" stroke="{EDGE}" stroke-width="1.2"/>'
        f'<rect x="2" y="9" width="23" height="11" rx="2.5" fill="{GREY}" stroke="{INK}" stroke-width="1.2"/>'
        f'<rect x="7" y="17" width="13" height="7" fill="{PAPER}" stroke="{EDGE}" stroke-width="1.2"/>'
        f'<circle cx="22" cy="21" r="5.5" fill="#dbeef8" stroke="{BLUE}" stroke-width="2.4"/>'
        f'<path d="M26 25l4 4" stroke="{INK}" stroke-width="3.2" stroke-linecap="round"/>'),
    "save": (
        f'<path d="M4 4h19.5L28 8.5V28H4z" fill="{BLUE}" stroke="#1d4f86" stroke-width="1.2" '
        'stroke-linejoin="round"/>'
        '<rect x="8.5" y="4" width="14" height="8.5" fill="#e9eef5"/>'
        f'<rect x="17.5" y="5.5" width="3" height="5.5" fill="{BLUE}"/>'
        f'<rect x="7.5" y="16.5" width="17" height="11.5" fill="{PAPER}"/>'
        + _lines(10, 22, (20, 23.5), width=1.3)),
    "simulate": (
        _doc(4, 3, 19, 25)
        + _lines(8, 18, (11, 14.5, 18), width=1.4)
        + f'<circle cx="20" cy="20" r="6" fill="#dbeef8" fill-opacity="0.9" stroke="{BLUE}" stroke-width="2.4"/>'
        f'<path d="M24.4 24.4L29 29" stroke="{INK}" stroke-width="3.4" stroke-linecap="round"/>'),
    "reset_temp": (
        _clock(ORANGE)
        + f'<path d="M2.5 4.5l1.6 8.3 6.6-5.2z" fill="{ORANGE}" stroke="{ORANGE}" '
          'stroke-width="0.8" stroke-linejoin="round"/>'),
    "reset_perm": _chip(4, 4, 20) + _badge(RED, ARROW_WHITE),
    "chip": _chip(7, 7, 18),
    "chip_read": (
        _chip(4, 4, 20)
        + _badge(GREEN, '<path d="M24 19.8v7.4M20.9 24.3l3.1 3.1 3.1-3.1" fill="none" '
                        'stroke="#fff" stroke-width="1.8" stroke-linecap="round" '
                        'stroke-linejoin="round"/>')),
    "pdf": (
        _doc(7, 2, 20, 27)
        + _lines(11, 22, (8, 11), width=1.3)
        + f'<rect x="3" y="15" width="21" height="10" rx="1" fill="{RED}"/>'
        '<text x="13.5" y="23" font-family="Segoe UI, Arial" font-weight="bold" font-size="8.2" '
        'fill="#fff" text-anchor="middle">PDF</text>'),
    "copy": (
        _doc(11, 2, 17, 21, 5) + _lines(14, 23, (10, 13, 16), width=1.3)
        + _doc(4, 9, 17, 21, 5) + _lines(7, 16, (17, 20, 23, 26), color=BLUE, width=1.3)),
    "clipboard": (
        '<rect x="5" y="5" width="22" height="25" rx="2" fill="#b07a3c" stroke="#7e5426" stroke-width="1"/>'
        f'<rect x="8" y="9" width="16" height="18" fill="{PAPER}"/>'
        + _lines(11, 21, (14, 17.5, 21), color=TEAL, width=1.5)
        + f'<rect x="11" y="2.5" width="10" height="5" rx="1.5" fill="#c0c6cd" stroke="{INK}" stroke-width="1"/>'),
    "json": (
        _doc(5, 3, 22, 26)
        + f'<text x="16" y="23" font-family="Consolas, Courier New" font-weight="bold" '
          f'font-size="12" fill="{TEAL}" text-anchor="middle">{{}}</text>'),
    "csv": (
        _doc(5, 3, 22, 26)
        + f'<rect x="8.5" y="12" width="15" height="13" fill="#e3f2e5" stroke="{GREEN}" stroke-width="1.2"/>'
        f'<path d="M8.5 16.3h15M8.5 20.6h15M13.5 12v13M18.5 12v13" stroke="{GREEN}" stroke-width="1"/>'),
    "nozzle": (
        f'<rect x="4" y="3" width="24" height="26" fill="{PAPER}" stroke="{EDGE}" stroke-width="1.2"/>'
        + "".join(_stairs(6.5 + i * 5.5, c) for i, c in enumerate(CMYK))),
    "nozzle2": (
        f'<rect x="4" y="3" width="24" height="26" fill="{PAPER}" stroke="{EDGE}" stroke-width="1.2"/>'
        + "".join(_stairs(6.5 + i * 5.5, c) for i, c in enumerate(CMYK))
        + _badge(BLUE, '<text x="24" y="27.3" font-family="Segoe UI, Arial" font-weight="bold" '
                       'font-size="9" fill="#fff" text-anchor="middle">2</text>')),
    "color": (
        f'<rect x="3" y="3" width="26" height="26" fill="{PAPER}" stroke="{EDGE}" stroke-width="1.2"/>'
        f'<rect x="6" y="6" width="9.5" height="9.5" fill="{CMYK[1]}"/>'
        f'<rect x="16.5" y="6" width="9.5" height="9.5" fill="{CMYK[2]}"/>'
        f'<rect x="6" y="16.5" width="9.5" height="9.5" fill="{CMYK[3]}"/>'
        f'<rect x="16.5" y="16.5" width="9.5" height="9.5" fill="{CMYK[0]}"/>'),
    "clean": (
        f'<rect x="5" y="3" width="22" height="10" rx="2" fill="{GREY}" stroke="{INK}" stroke-width="1.2"/>'
        f'<rect x="5" y="3" width="22" height="3.5" rx="1.5" fill="#8b949e"/>'
        f'<path d="M8 13h16v2.5H8z" fill="{INK}"/>'
        + _drop(10, 17.5, s=0.95) + _drop(16, 19.5) + _drop(22, 17.5, s=0.95)),
    "testpage": (
        f'<rect x="6" y="2" width="20" height="28" fill="{PAPER}" stroke="{EDGE}" stroke-width="1.2"/>'
        f'<rect x="6" y="2" width="20" height="5" fill="{TEAL}"/>'
        + _lines(9, 23, (11, 14), width=1.3)
        + "".join(f'<rect x="{9 + i * 3.5}" y="17" width="3.5" height="5" fill="{c}"/>'
                  for i, c in enumerate(CMYK))
        + "".join(f'<rect x="{9 + i * 3.5}" y="23" width="3.5" height="3" fill="{g}"/>'
                  for i, g in enumerate(("#333", "#777", "#aaa", "#ddd")))),
    "feed": (  # a sheet leaving between two rollers
        f'<rect x="9" y="2" width="14" height="17" fill="{PAPER}" stroke="{EDGE}" stroke-width="1.2"/>'
        + _lines(12, 20, (6, 9, 12), width=1.2)
        + f'<circle cx="9" cy="23" r="4.5" fill="{GREY}" stroke="{INK}" stroke-width="1.2"/>'
        f'<circle cx="23" cy="23" r="4.5" fill="{GREY}" stroke="{INK}" stroke-width="1.2"/>'
        f'<path d="M16 21v9M12.8 27l3.2 3.2 3.2-3.2" fill="none" stroke="{TEAL}" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'),
    "folder": _folder(),
    "diag_print": (  # the diagnostic sheet: corner marks and four ink blocks
        f'<rect x="5" y="2" width="22" height="28" fill="{PAPER}" stroke="{EDGE}" stroke-width="1.2"/>'
        + "".join(f'<rect x="{x}" y="{y}" width="4" height="4" fill="{INK}"/>'
                  f'<rect x="{x + 1.2}" y="{y + 1.2}" width="1.6" height="1.6" fill="{PAPER}"/>'
                  for x, y in ((7, 4), (21, 4), (7, 24), (21, 24)))
        + "".join(f'<rect x="{8 + i * 4.2}" y="10" width="3.6" height="5" fill="{c}"/>'
                  for i, c in enumerate(CMYK[1:] + CMYK[:1]))
        + "".join(f'<path d="M{8.5 + i * 1.6} 17.5v4.5" stroke="{INK}" stroke-width="0.7"/>'
                  for i in range(5))
        + _lines(17, 24, (18, 20, 22), color=INK, width=0.7)),
    "scan": (  # flatbed with its lid up and the light bar
        f'<path d="M4 11L25 4l1.4 3.6L5.4 14.6z" fill="#8b949e" stroke="{INK}" '
        'stroke-width="1" stroke-linejoin="round"/>'
        f'<rect x="3" y="15" width="26" height="12" rx="2" fill="{GREY}" stroke="{INK}" '
        'stroke-width="1.2"/>'
        f'<rect x="5.5" y="17" width="21" height="4" fill="#dbeef8" stroke="{EDGE}" stroke-width="0.8"/>'
        f'<path d="M14 16.4v5.2" stroke="#5fe08a" stroke-width="2.2"/>'
        + _badge(GREEN, '<path d="M20.8 24.2l2.2 2.2 4-4.2" fill="none" stroke="#fff" '
                        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>')),
    "diag_open": (
        _folder()
        + f'<circle cx="21" cy="20" r="5.5" fill="#dbeef8" fill-opacity="0.95" stroke="{BLUE}" '
          'stroke-width="2.2"/>'
        + f'<path d="M25 24l4 4" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>'),
    "folder_report": _folder() + _badge(RED,'<path d="M21.5 21h5M21.5 24h5M21.5 27h3" '
                                              'stroke="#fff" stroke-width="1.4"/>'),
    "folder_backup": _folder() + _badge(BLUE, '<rect x="20.8" y="20.8" width="6.4" height="6.4" '
                                               'fill="#fff"/><rect x="22" y="20.8" width="4" '
                                               f'height="2.4" fill="{BLUE}"/>'),
    "history": (
        _clock(BLUE)
        + f'<path d="M2.5 4.5l1.6 8.3 6.6-5.2z" fill="{BLUE}" stroke="{BLUE}" '
          'stroke-width="0.8" stroke-linejoin="round"/>'),
    "summary": (
        f'<path d="M4 23A12 12 0 0 1 9 13.3" fill="none" stroke="{GREEN}" stroke-width="4"/>'
        f'<path d="M10.3 12.4A12 12 0 0 1 21.7 12.4" fill="none" stroke="{GOLD}" stroke-width="4"/>'
        f'<path d="M23 13.3A12 12 0 0 1 28 23" fill="none" stroke="{RED}" stroke-width="4"/>'
        f'<path d="M16 23L22.5 14.5" stroke="{INK}" stroke-width="2.4" stroke-linecap="round"/>'
        f'<circle cx="16" cy="23" r="3" fill="{INK}"/>'
        f'<path d="M3 27.5h26" stroke="{EDGE}" stroke-width="1.4"/>'),
    "details": (
        _doc(5, 3, 22, 26)
        + "".join(f'<rect x="8.5" y="{y - 1.3}" width="2.6" height="2.6" fill="{BLUE}"/>'
                  for y in (11, 15.5, 20, 24.5))
        + _lines(13.5, 22.5, (11, 15.5, 20, 24.5), width=1.4)),
    "maintenance": (
        f'<path d="M20.5 3.5a6.5 6.5 0 0 0-6 8.9L4.6 22.3a2.6 2.6 0 0 0 3.7 3.7l9.9-9.9'
        f'a6.5 6.5 0 0 0 8.9-6l-3.9 3.9-3.7-1-1-3.7z" fill="#9aa3ad" stroke="{INK}" '
        'stroke-width="1.2" stroke-linejoin="round"/>'
        + _drop(25, 18, s=0.9)),
    "warning": (
        f'<path d="M16 3L30 28H2z" fill="#f6c343" stroke="#b7860b" stroke-width="1.4" '
        'stroke-linejoin="round"/>'
        f'<path d="M16 11v9" stroke="{INK}" stroke-width="2.8" stroke-linecap="round"/>'
        f'<circle cx="16" cy="24" r="1.7" fill="{INK}"/>'),
    "info": (
        f'<circle cx="16" cy="16" r="13" fill="{BLUE}" stroke="#1d4f86" stroke-width="1"/>'
        '<circle cx="16" cy="9.5" r="2" fill="#fff"/>'
        '<path d="M16 14v10" stroke="#fff" stroke-width="3.2" stroke-linecap="round"/>'),
    "exit": (
        f'<rect x="4" y="3" width="15" height="26" fill="#c9a77a" stroke="#7e5426" stroke-width="1.2"/>'
        f'<circle cx="15.5" cy="16.5" r="1.2" fill="{INK}"/>'
        f'<path d="M19 16h10M25 12l4 4-4 4" fill="none" stroke="{RED}" stroke-width="2.6" '
        'stroke-linecap="round" stroke-linejoin="round"/>'),
    "status_ok": f'<circle cx="16" cy="16" r="11" fill="{GREEN}" stroke="#1d6127" stroke-width="1.4"/>',
}


def svg(name):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" '
            f'height="32">{BODIES[name]}</svg>')


def pixmap(name, size):
    renderer = QSvgRenderer(QByteArray(svg(name).encode("utf-8")))
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QPixmap.fromImage(image)


@lru_cache(maxsize=None)
def icon(name):
    result = QIcon()
    for size in SIZES:
        result.addPixmap(pixmap(name, size))
    return result
