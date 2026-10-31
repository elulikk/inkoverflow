"""InkOverflow brand kit: icon, logos, .ico, banner and a contact sheet.

Regenerate everything with:   .venv\\Scripts\\python.exe brand\\make_brand.py

The mark is a cup (the waste-ink pad) whose four-colour (CMYK) ink domes over the rim and runs down the
outside: overflow. Text is converted to outlines with Qt, so the SVGs do not depend on
any installed font. Colours come from the application's own palette (widgets.C).
"""
import struct
import sys
from pathlib import Path
from typing import Dict

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

HERE = Path(__file__).resolve().parent
NAME = "InkOverflow"
TAGLINE = "El contador miente. Nosotros llevamos la cuenta."

CYAN, MAGENTA, YELLOW = "#00a0e0", "#e0007a", "#f2c800"
DARK = {"cup": "#e6e9ef", "word": "#e6e9ef", "flow": "#3dd6c6", "muted": "#8b93a1", "k": "#5b6472"}
LIGHT = {"cup": "#17202b", "word": "#17202b", "flow": "#0e93a8", "muted": "#5b6270", "k": "#1f2328"}
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

#: left, top, right, bottom of the mark in its own 512-unit drawing space
MARK_BOX = (133, 172, 416, 420)


# -- the mark -------------------------------------------------------------------------
def mark_group(cup: str, defs: bool = True, k: str = "#1f2328", halo: str = "") -> str:
    """Cup, four-colour ink dome above the rim (C M Y K), a stream over the wall and the drop."""
    shape = "M159 240C159 150 353 150 353 240V348A31 31 0 0 1 322 379H190A31 31 0 0 1 159 348Z"
    stops = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in (
        (0, CYAN), (0.25, CYAN), (0.25, MAGENTA), (0.5, MAGENTA),
        (0.5, YELLOW), (0.75, YELLOW), (0.75, k), (1, k)))
    head = (f'<defs><linearGradient id="cmyk" gradientUnits="userSpaceOnUse" x1="159" y1="0" '
            f'x2="353" y2="0">{stops}</linearGradient></defs>') if defs else ""
    outline = "M146 214V348A44 44 0 0 0 190 392H322A44 44 0 0 0 366 348V214"
    stream = "M340 238C382 224 392 246 392 282V336"
    drop = "M392 364C392 364 372 388 372 400A20 20 0 0 0 412 400C412 388 392 364 392 364Z"
    ring = (f'<path d="{outline}" fill="none" stroke="{halo}" stroke-width="40" stroke-linecap="round" '
            f'stroke-linejoin="round"/><path d="{stream}" fill="none" stroke="{halo}" stroke-width="38" '
            f'stroke-linecap="round"/><path d="{drop}" fill="{halo}" stroke="{halo}" stroke-width="14" '
            f'stroke-linejoin="round"/>') if halo else ""
    return (
        head + ring +
        f'<path d="{shape}" fill="url(#cmyk)"/>'
        f'<path d="M146 214V348A44 44 0 0 0 190 392H322A44 44 0 0 0 366 348V214" fill="none" '
        f'stroke="{cup}" stroke-width="26" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M340 238C382 224 392 246 392 282V336" fill="none" stroke="{k}" '
        'stroke-width="24" stroke-linecap="round"/>'
        '<path d="M392 364C392 364 372 388 372 400A20 20 0 0 0 412 400C412 388 392 364 392 364Z" '
        f'fill="{k}"/>')


def icon_svg() -> str:
    """App icon: the four-colour mark on a transparent background, with a white halo so it
    reads on dark and light taskbars alike."""
    cx, cy = (MARK_BOX[0] + MARK_BOX[2]) / 2, (MARK_BOX[1] + MARK_BOX[3]) / 2
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">'
        f'<g transform="translate(256 256) scale(1.3) translate({-cx} {-cy})">'
        f'{mark_group(LIGHT["cup"], k=LIGHT["k"], halo="#ffffff")}</g></svg>')


def mark_svg(theme: Dict[str, str]) -> str:
    x, y, r, b = MARK_BOX
    pad = 16
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x - pad} {y - pad} '
            f'{r - x + 2 * pad} {b - y + 2 * pad}">{mark_group(theme["cup"], k=theme["k"])}</svg>')


# -- text as outlines -------------------------------------------------------------------
def ui_font(pixels: int, weight=QFont.Weight.DemiBold) -> QFont:
    font = QFont("Segoe UI")
    font.setPixelSize(pixels)
    font.setWeight(weight)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def text_path(text: str, font: QFont, x: float = 0.0) -> QPainterPath:
    path = QPainterPath()
    path.addText(x, 0.0, font, text)   # baseline at y = 0
    return path


def svg_path(path: QPainterPath, dx: float = 0.0, dy: float = 0.0) -> str:
    out, i, count, is_open = [], 0, path.elementCount(), False
    while i < count:
        e = path.elementAt(i)
        if e.isMoveTo():
            if is_open:
                out.append("Z")
            out.append(f"M{e.x + dx:.2f} {e.y + dy:.2f}")
            is_open = True
        elif e.isLineTo():
            out.append(f"L{e.x + dx:.2f} {e.y + dy:.2f}")
        elif e.isCurveTo():
            c2, end = path.elementAt(i + 1), path.elementAt(i + 2)
            out.append(f"C{e.x + dx:.2f} {e.y + dy:.2f} {c2.x + dx:.2f} {c2.y + dy:.2f} "
                       f"{end.x + dx:.2f} {end.y + dy:.2f}")
            i += 2
        i += 1
    if is_open:
        out.append("Z")
    return "".join(out)


def logo_block(theme: Dict[str, str], mark_h: float = 170, defs: bool = True):
    """(svg fragment, width, height): mark followed by the wordmark, origin top-left."""
    scale = mark_h / (MARK_BOX[3] - MARK_BOX[1])
    mark_w = (MARK_BOX[2] - MARK_BOX[0]) * scale
    font = ui_font(round(mark_h * 0.72))
    advance = QFontMetricsF(font).horizontalAdvance("Ink")
    ink, flow = text_path("Ink", font), text_path("Overflow", font, advance)
    both = QPainterPath(ink)
    both.addPath(flow)
    bounds = both.boundingRect()
    tx = mark_w + mark_h * 0.16 - bounds.left()
    ty = mark_h / 2 - (bounds.top() + bounds.bottom()) / 2
    fragment = (
        f'<g transform="translate({-MARK_BOX[0] * scale:.2f} {-MARK_BOX[1] * scale:.2f}) '
        f'scale({scale:.4f})">{mark_group(theme["cup"], defs, theme["k"])}</g>'
        f'<path d="{svg_path(ink, tx, ty)}" fill="{theme["word"]}"/>'
        f'<path d="{svg_path(flow, tx, ty)}" fill="{theme["flow"]}"/>')
    return fragment, tx + bounds.right(), mark_h


def logo_svg(theme: Dict[str, str]) -> str:
    fragment, width, height = logo_block(theme)
    pad = height * 0.14
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width + 2 * pad:.1f} '
            f'{height + 2 * pad:.1f}" width="{width + 2 * pad:.0f}" height="{height + 2 * pad:.0f}">'
            f'<g transform="translate({pad:.1f} {pad:.1f})">{fragment}</g></svg>')


def banner_svg() -> str:
    width, height = 1280, 320
    fragment, block_w, block_h = logo_block(DARK, mark_h=170)
    tag_font = ui_font(30, QFont.Weight.Normal)
    tag = text_path(TAGLINE, tag_font)
    x0 = 96
    watermark = mark_group(DARK["cup"], defs=False, k=DARK["k"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">'
        '<defs><radialGradient id="glow" cx="0.18" cy="0.4" r="0.75"><stop offset="0" '
        'stop-color="#3dd6c6" stop-opacity="0.20"/><stop offset="1" stop-color="#3dd6c6" '
        'stop-opacity="0"/></radialGradient></defs>'
        f'<rect width="{width}" height="{height}" fill="#0f1217"/>'
        f'<rect width="{width}" height="{height}" fill="url(#glow)"/>'
        '<g opacity="0.10" transform="translate(867 -144)">' + watermark + '</g>'
        f'<g transform="translate({x0} 42)">{fragment}</g>'
        f'<path d="{svg_path(tag, x0, 268)}" fill="{DARK["muted"]}"/>'
        '</svg>')


# -- rendering and packing --------------------------------------------------------------
def render(svg: str, width: int, height: int) -> QImage:
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("invalid SVG")
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter, QRectF(0, 0, width, height))
    painter.end()
    return image


def png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def ico_bytes(pngs: Dict[int, bytes]) -> bytes:
    """A Windows .ico whose images are PNG-compressed (supported since Vista)."""
    sizes = sorted(pngs)
    offset = 6 + 16 * len(sizes)
    directory, blobs = b"", b""
    for size in sizes:
        data = pngs[size]
        directory += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32,
                                 len(data), offset)
        offset += len(data)
        blobs += data
    return struct.pack("<HHH", 0, 1, len(sizes)) + directory + blobs


def contact_sheet(logo_dark: QImage, logo_light: QImage, icons: Dict[int, QImage],
                  banner: QImage) -> QImage:
    sheet = QImage(1280, 810, QImage.Format.Format_ARGB32)
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.fillRect(0, 0, 640, 810, QColor("#0f1217"))
    painter.fillRect(640, 0, 640, 810, QColor("#ffffff"))
    for image, x in ((logo_dark, 40), (logo_light, 680)):
        painter.drawImage(QRectF(x, 40, 560, 560 * image.height() / image.width()), image)
    for base in (40, 680):
        x = base
        for size in (256, 128, 64, 32, 16):     # real pixel sizes, centred on one line
            painter.drawImage(x, 330 - size // 2, icons[size])
            x += size + 16
    painter.drawImage(QRectF(40, 490, 1200, 300), banner)
    painter.end()
    return sheet


def build(out: Path = HERE) -> Dict[str, Path]:
    """Write the whole kit into `out`; returns name -> path."""
    if QApplication.instance() is None:
        QApplication(sys.argv[:1])
    out.mkdir(parents=True, exist_ok=True)
    written: Dict[str, Path] = {}

    def put(name: str, data) -> None:
        path = out / name
        path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
        written[name] = path

    icon = icon_svg()
    put("icon.svg", icon)
    icons = {size: render(icon, size, size) for size in ICON_SIZES}
    for size, image in icons.items():
        put(f"icon_{size}.png", png_bytes(image))
    put("inkoverflow.ico", ico_bytes({s: png_bytes(icons[s]) for s in ICO_SIZES}))

    put("mark_dark.svg", mark_svg(DARK))
    put("mark_light.svg", mark_svg(LIGHT))
    renders = {}
    for name, theme in (("dark", DARK), ("light", LIGHT)):
        svg = logo_svg(theme)
        put(f"logo_{name}.svg", svg)
        ratio = QSvgRenderer(QByteArray(svg.encode("utf-8"))).defaultSize()
        renders[name] = render(svg, 1600, round(1600 * ratio.height() / ratio.width()))
        put(f"logo_{name}.png", png_bytes(renders[name]))
    banner = banner_svg()
    put("banner.svg", banner)
    banner_image = render(banner, 1280, 320)
    put("banner.png", png_bytes(banner_image))
    put("muestrario.png", png_bytes(contact_sheet(renders["dark"], renders["light"],
                                                  icons, banner_image)))
    return written


if __name__ == "__main__":
    for name, path in build().items():
        print(f"{name:20s} {path.stat().st_size:>8d} bytes")
