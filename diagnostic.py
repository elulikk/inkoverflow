"""Patrón de diagnóstico: una hoja A4 que se imprime, se escanea y se analiza sola.

La hoja (todo en mm, vertical) lleva:
  * cuatro marcas de esquina (como las de un código QR) y un cuadrito negro junto a la
    de arriba a la izquierda, que dice qué lado es arriba. Con ellas el escaneo se
    endereza aunque la hoja esté torcida, girada 180° o sea una foto en perspectiva;
  * 1 · un bloque macizo de cian, magenta, amarillo y negro: un inyector tapado deja
    una raya blanca horizontal (el cabezal se mueve de lado a lado); un color que falta,
    que sale flojo o con otro tono también se ve ahí;
  * 2 · líneas verticales finas: si la impresión de ida y la de vuelta no coinciden
    (alineación bidireccional), las líneas salen escalonadas o dobles;
  * 3 · líneas horizontales finas: si el papel avanza a tirones, quedan mal espaciadas;
  * 4 · una zona en blanco: manchas, marcas de rodillos o del cabezal que roza.

Gasta mucha menos tinta que la página MAG «Ahorro máximo». Se imprime por la cola de
Windows (como la página MAG), en vectores. El análisis solo usa numpy.
"""
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPen
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

PAGE_W, PAGE_H = 210.0, 297.0
MODULE = 1.5  # mm; each corner mark is 7 x 7 modules (black, white, black core)
FIDUCIALS = {"tl": (15.0, 15.0), "tr": (195.0, 15.0), "br": (195.0, 282.0), "bl": (15.0, 282.0)}
ORIENT = (24.0, 12.5, 5.0, 5.0)  # x, y, w, h: solid square that marks the top
# (key, name, RGB sent to the driver, absorbing channel: 0 R, 1 G, 2 B, None all, hue)
INKS = (("C", "Cian", (0, 255, 255), 0, 195.0),
        ("M", "Magenta", (255, 0, 255), 1, 325.0),
        ("Y", "Amarillo", (255, 255, 0), 2, 55.0),
        ("K", "Negro", (0, 0, 0), None, None))
SOLIDS = {key: (25.0 + i * 42.0, 30.0, 34.0, 26.0) for i, (key, *_r) in enumerate(INKS)}
VLINES = (25.0, 72.0, 60.0, 28.0)   # block of vertical lines (alignment)
HLINES = (105.0, 72.0, 80.0, 28.0)  # block of horizontal lines (paper feed)
BLANK = (25.0, 115.0, 160.0, 150.0)  # must stay white
LINE_W, LINE_PITCH = 0.35, 2.0
V_XS = [VLINES[0] + 1.0 + i * LINE_PITCH for i in range(30)]
H_YS = [HLINES[1] + 1.0 + j * LINE_PITCH for j in range(14)]
VERSION = "1"

LEVELS = {"ok": 0, "info": 0, "warn": 1, "bad": 2}


# ---- the page --------------------------------------------------------------------
def draw(painter, k, stamp=""):
    """Paint the pattern; k = device pixels per mm, origin at the paper corner."""
    def rect(x, y, w, h):
        return QRectF(x * k, y * k, w * k, h * k)

    def text(x, y, w, h, size_mm, value, bold=False, align=Qt.AlignLeft | Qt.AlignVCenter,
             color=QColor(0, 0, 0)):
        font = QFont("Arial")
        font.setPixelSize(max(1, round(size_mm * k)))
        font.setBold(bold)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(rect(x, y, w, h), int(align), value)

    painter.save()
    painter.setPen(Qt.NoPen)
    black = QColor(0, 0, 0)
    for cx, cy in FIDUCIALS.values():
        for size, color in ((7, black), (5, QColor(255, 255, 255)), (3, black)):
            half = size * MODULE / 2
            painter.fillRect(rect(cx - half, cy - half, 2 * half, 2 * half), color)
    painter.fillRect(rect(*ORIENT), black)

    text(33, 10, 145, 5, 3.6, "InkOverflow · Patrón de diagnóstico", bold=True)
    text(33, 15, 145, 4, 2.4, stamp or f"v{VERSION}")

    text(25, 23.5, 160, 5, 3.0, "1 · Inyectores y color", bold=True)
    for key, name, rgb, _ch, _hue in INKS:
        x, y, w, h = SOLIDS[key]
        painter.fillRect(rect(x, y, w, h), QColor(*rgb))
        text(x, y + h + 0.8, w, 4, 2.6, name, align=Qt.AlignHCenter | Qt.AlignVCenter)

    text(25, 65.5, 70, 5, 3.0, "2 · Alineación del cabezal", bold=True)
    x, y, w, h = VLINES
    for lx in V_XS:
        painter.fillRect(rect(lx - LINE_W / 2, y, LINE_W, h), black)
    text(105, 65.5, 80, 5, 3.0, "3 · Avance del papel", bold=True)
    x, y, w, h = HLINES
    for ly in H_YS:
        painter.fillRect(rect(x, ly - LINE_W / 2, w, LINE_W), black)

    text(25, 106, 160, 5, 3.0, "4 · Zona en blanco: se buscan manchas y marcas de rodillos",
         bold=True)
    text(25, 110.5, 160, 4, 2.4, "No escribas ni apoyes nada en esta zona.",
         color=QColor(90, 90, 90))
    text(33, 277.5, 140, 4, 2.4, "Escanear en color (300 ppp) con las cuatro marcas de las "
         "esquinas dentro de la imagen.", align=Qt.AlignHCenter | Qt.AlignVCenter)
    text(33, 281.5, 140, 4, 2.4, "La hoja puede ir torcida o al revés: se endereza sola.",
         align=Qt.AlignHCenter | Qt.AlignVCenter, color=QColor(90, 90, 90))
    painter.restore()


def render(dpi=150, stamp=""):
    """The pattern as a white A4 QImage (preview and tests)."""
    k = dpi / 25.4
    image = QImage(round(PAGE_W * k), round(PAGE_H * k), QImage.Format_RGB32)
    image.fill(QColor(255, 255, 255))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    draw(painter, k, stamp)
    painter.end()
    return image


def print_pattern(queue=None, output=None, stamp=""):
    """Print the pattern on A4, no margins, as vectors. queue: Windows printer name;
    output: a .pdf path instead (to test without paper)."""
    if output:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(output))
    else:
        info = QPrinterInfo.printerInfo(queue)
        if info.isNull():
            raise RuntimeError(f"Windows no encuentra la cola «{queue}».")
        printer = QPrinter(info, QPrinter.PrinterMode.HighResolution)
    printer.setDocName("InkOverflow - Patrón de diagnóstico")
    printer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4),
                                      QPageLayout.Orientation.Portrait,
                                      QMarginsF(0, 0, 0, 0)))
    printer.setFullPage(True)
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("No se pudo iniciar la impresión en esa cola.")
    try:
        draw(painter, printer.resolution() / 25.4, stamp)
    finally:
        painter.end()


# ---- results -----------------------------------------------------------------------
@dataclass
class Finding:
    level: str          # "ok", "info", "warn" or "bad"
    title: str
    detail: str = ""
    action: str = ""
    areas: list = field(default_factory=list)  # (x, y, w, h) mm to outline on the page


@dataclass
class Result:
    findings: list
    page: QImage        # the scan, straightened to the page (PREVIEW_PPM px per mm)
    metrics: dict

    @property
    def level(self):
        return max((f.level for f in self.findings), key=LEVELS.get, default="ok")

    def problems(self):
        return [f for f in self.findings if LEVELS[f.level] > 0]

    def summary(self):
        bad = self.problems()
        if not bad:
            return "Patrón de diagnóstico: sin fallas a la vista."
        return "Patrón de diagnóstico: " + "; ".join(f.title for f in bad) + "."


PREVIEW_PPM = 3.0


def annotated(result):
    """The straightened scan with every finding outlined (green ok, amber, red)."""
    ppm = PREVIEW_PPM
    image = result.page.convertToFormat(QImage.Format_RGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    colors = {"ok": QColor(46, 139, 58), "info": QColor(43, 108, 176),
              "warn": QColor(224, 138, 0), "bad": QColor(200, 49, 42)}
    for finding in sorted(result.findings, key=lambda f: LEVELS[f.level]):
        pen = QPen(colors[finding.level])
        pen.setWidthF(max(1.5, 0.6 * ppm))
        painter.setPen(pen)
        for x, y, w, h in finding.areas:
            painter.drawRect(QRectF((x - 1) * ppm, (y - 1) * ppm, (w + 2) * ppm, (h + 2) * ppm))
    painter.end()
    return image


class PatternNotFound(RuntimeError):
    pass


# ---- image helpers -------------------------------------------------------------------
MAX_SIDE = 3600  # about 300 ppp for an A4 scan; bigger images are scaled down first


def load(path):
    """A saved scan: any image Qt reads, or the first page of a PDF (many scanner apps
    save PDF), drawn at 300 ppp."""
    if str(path).lower().endswith(".pdf"):
        from PySide6.QtCore import QSize
        from PySide6.QtPdf import QPdfDocument
        doc = QPdfDocument()
        doc.load(str(path))
        if doc.status() != QPdfDocument.Status.Ready or doc.pageCount() < 1:
            raise RuntimeError(f"No se pudo abrir el PDF: {path}")
        size = doc.pagePointSize(0)
        image = doc.render(0, QSize(round(size.width() * 300 / 72),
                                    round(size.height() * 300 / 72)))
        if image.isNull():
            raise RuntimeError(f"No se pudo dibujar el PDF: {path}")
        return image
    image = QImage(str(path))
    if image.isNull():
        raise RuntimeError(f"No se pudo abrir la imagen: {path}")
    return image


def to_array(image):
    """QImage -> uint8 H x W x 3 (RGB), scaled down to MAX_SIDE."""
    if max(image.width(), image.height()) > MAX_SIDE:
        image = image.scaled(MAX_SIDE, MAX_SIDE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    image = image.convertToFormat(QImage.Format_RGB888)
    w, h, bpl = image.width(), image.height(), image.bytesPerLine()
    raw = np.frombuffer(image.constBits(), np.uint8, count=bpl * h).reshape(h, bpl)
    return raw[:, :w * 3].reshape(h, w, 3).copy()


def from_array(rgb):
    rgb = np.ascontiguousarray(np.clip(rgb, 0, 255).astype(np.uint8))
    h, w = rgb.shape[:2]
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


def _box_means(integral, r):
    """Mean of every (2r+1)^2 box, for centers at least r from the border."""
    s = 2 * r + 1
    total = (integral[s:, s:] - integral[:-s, s:] - integral[s:, :-s] + integral[:-s, :-s])
    return total / (s * s)


def _darkness(gray):
    white = float(np.percentile(gray, 95))
    black = float(np.percentile(gray, 0.5))
    return np.clip((white - gray) / max(white - black, 40.0), 0.0, 1.0)


def _find_marks(rgb):
    """Centers (x, y) in image pixels of the four corner marks, by image quadrant:
    {"TL", "TR", "BR", "BL"}."""
    gray = rgb.astype(np.float32).mean(axis=2)
    dark = _darkness(gray)
    h, w = dark.shape
    step = max(1, max(h, w) // 1000)
    small = dark[:h - h % step, :w - w % step]
    small = small.reshape(small.shape[0] // step, step, small.shape[1] // step, step).mean(axis=(1, 3))
    sh, sw = small.shape
    integral = np.zeros((sh + 1, sw + 1))
    integral[1:, 1:] = small.cumsum(0).cumsum(1)
    best = {}
    side = min(sh, sw)  # the page's short side (140 modules) is 40-100 % of it
    for m in np.geomspace(side / 360, side / 135, 12):
        r1, r2, r3 = (max(1, round(f * m)) for f in (1.5, 2.5, 3.5))
        if r2 <= r1:
            r2 = r1 + 1
        if r3 <= r2:
            r3 = r2 + 1
        if 2 * r3 + 2 >= min(sh, sw):
            continue
        a1, a2, a3 = ((2 * r + 1) ** 2 for r in (r1, r2, r3))
        b3 = _box_means(integral, r3)
        b2 = _box_means(integral, r2)[r3 - r2:sh - 2 * r2 - (r3 - r2), r3 - r2:sw - 2 * r2 - (r3 - r2)]
        b1 = _box_means(integral, r1)[r3 - r1:sh - 2 * r1 - (r3 - r1), r3 - r1:sw - 2 * r1 - (r3 - r1)]
        ring = (b2 * a2 - b1 * a1) / (a2 - a1)
        outer = (b3 * a3 - b2 * a2) / (a3 - a2)
        score = np.minimum(b1, outer) - ring
        oh, ow = score.shape
        cy, cx = sh / 2 - r3, sw / 2 - r3  # image center in score coordinates
        for name, ys, xs in (("TL", slice(0, int(cy)), slice(0, int(cx))),
                             ("TR", slice(0, int(cy)), slice(int(cx), ow)),
                             ("BR", slice(int(cy), oh), slice(int(cx), ow)),
                             ("BL", slice(int(cy), oh), slice(0, int(cx)))):
            part = score[ys, xs]
            if part.size == 0:
                continue
            index = np.unravel_index(int(np.argmax(part)), part.shape)
            value = float(part[index])
            if value > best.get(name, (-9,))[0]:
                y = (index[0] + ys.start + r3 + 0.5) * step
                x = (index[1] + xs.start + r3 + 0.5) * step
                best[name] = (value, x, y, m * step)
    missing = [n for n in ("TL", "TR", "BR", "BL") if best.get(n, (0,))[0] < 0.45]
    if missing:
        raise PatternNotFound(
            "No se encontraron las cuatro marcas de las esquinas del patrón. Escanea la hoja "
            "entera (las cuatro marcas tienen que verse), en color y sin recortar.")
    return {name: _refine(dark, x, y, m) for name, (_v, x, y, m) in best.items()}


def _refine(dark, x, y, m):
    """Center of the mark's black core: the dark pixels inside the white ring."""
    h, w = dark.shape
    for _ in range(3):
        r = 2.2 * m
        x0, x1 = max(0, int(x - r)), min(w, int(x + r) + 1)
        y0, y1 = max(0, int(y - r)), min(h, int(y + r) + 1)
        win = dark[y0:y1, x0:x1]
        weight = np.where(win > 0.5, win, 0.0)
        total = weight.sum()
        if total <= 0:
            break
        yy, xx = np.mgrid[y0:y1, x0:x1]
        x = float((weight * (xx + 0.5)).sum() / total)
        y = float((weight * (yy + 0.5)).sum() / total)
    return x, y


def _homography(src, dst):
    """3x3 H with dst ~ H @ src for four point pairs."""
    rows, rhs = [], []
    for (x, y), (u, v) in zip(src, dst):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        rhs += [u, v]
    h = np.linalg.solve(np.array(rows, float), np.array(rhs, float))
    return np.append(h, 1.0).reshape(3, 3)


class Page:
    """The scan seen in page millimetres."""

    def __init__(self, rgb, H):
        self.rgb, self.H = rgb, H

    def to_image(self, x, y):
        p = self.H @ np.stack([np.asarray(x, float), np.asarray(y, float), np.ones_like(x, float)])
        return p[0] / p[2], p[1] / p[2]

    def sample(self, x, y, w, h, ppm):
        """RGB (float) of the region on a grid of ppm pixels per mm, bilinear."""
        nx, ny = max(1, round(w * ppm)), max(1, round(h * ppm))
        gx = x + (np.arange(nx) + 0.5) / ppm
        gy = y + (np.arange(ny) + 0.5) / ppm
        X, Y = np.meshgrid(gx, gy)
        u, v = self.to_image(X.ravel(), Y.ravel())
        ih, iw = self.rgb.shape[:2]
        u = np.clip(u - 0.5, 0, iw - 1.001)
        v = np.clip(v - 0.5, 0, ih - 1.001)
        u0, v0 = u.astype(int), v.astype(int)
        fu, fv = (u - u0)[:, None], (v - v0)[:, None]
        img = self.rgb
        out = (img[v0, u0] * (1 - fu) * (1 - fv) + img[v0, u0 + 1] * fu * (1 - fv)
               + img[v0 + 1, u0] * (1 - fu) * fv + img[v0 + 1, u0 + 1] * fu * fv)
        return out.reshape(ny, nx, 3).astype(np.float32)


def _locate(rgb):
    """Page of the scan, whatever way up it was scanned."""
    marks = _find_marks(rgb)
    corners = [marks[n] for n in ("TL", "TR", "BR", "BL")]
    sides = [np.hypot(*np.subtract(corners[i], corners[(i + 1) % 4])) for i in range(4)]
    ratio = max(sides[0] + sides[2], sides[1] + sides[3]) / max(1e-6, min(sides[0] + sides[2],
                                                                         sides[1] + sides[3]))
    expected = (FIDUCIALS["bl"][1] - FIDUCIALS["tl"][1]) / (FIDUCIALS["tr"][0] - FIDUCIALS["tl"][0])
    if abs(ratio / expected - 1) > 0.15:
        raise PatternNotFound(
            "Las marcas encontradas no tienen la forma del patrón (¿se recortó la hoja o hay "
            "otro papel en el escáner?). Escanea solo la hoja del patrón, entera.")
    page_pts = [FIDUCIALS[n] for n in ("tl", "tr", "br", "bl")]
    ox, oy, ow, oh = ORIENT
    best = None
    for turn in range(4):
        image_pts = corners[turn:] + corners[:turn]
        page = Page(rgb, _homography(page_pts, image_pts))
        patch = page.sample(ox + 1, oy + 1, ow - 2, oh - 2, 4).mean()
        if best is None or patch < best[0]:
            best = (patch, turn, page, image_pts)
    _patch, turn, page, image_pts = best
    white = page.sample(*BLANK, 1).reshape(-1, 3).mean(axis=1)
    paper = float(np.median(white))
    if _patch > 0.55 * paper:
        raise PatternNotFound(
            "Se ven las marcas de las esquinas pero no el cuadrito que indica dónde va "
            "arriba. ¿Es la hoja del patrón de diagnóstico de InkOverflow?")
    return page, turn, image_pts


# ---- analysis ------------------------------------------------------------------------
CLEAN_HINT = ("Haz una limpieza de cabezales (CL1) y vuelve a imprimir y escanear el "
              "patrón. Si sigue igual, CL2. Si dos limpiezas no cambian nada, deja reposar "
              "la impresora unas horas y repite.")
HP_CLEAN_HINT = ("Limpia los cabezales desde el panel de la impresora o desde HP Smart "
                 "(Herramientas › Limpiar cabezales) y vuelve a imprimir y escanear el patrón.")


def _running_median(values, window):
    half = window // 2
    padded = np.pad(values, half, mode="edge")
    view = np.lib.stride_tricks.sliding_window_view(padded, window)
    return np.median(view, axis=1)


def _hue(rgb):
    r, g, b = (float(c) for c in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx - mn < 1e-6:
        return None
    if mx == r:
        h = ((g - b) / (mx - mn)) % 6
    elif mx == g:
        h = (b - r) / (mx - mn) + 2
    else:
        h = (r - g) / (mx - mn) + 4
    return 60.0 * h


def _hue_gap(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _streaks(absorb_rows_left, absorb_rows_right, density, ppm):
    """Rows (y in mm from the top of the sampled region) lighter than their
    surroundings across the whole width: a missing nozzle draws a white line."""
    rows = []
    window = int(3 * ppm) | 1
    halves = []
    for profile in (absorb_rows_left, absorb_rows_right):
        base = _running_median(profile, window)
        halves.append((base - profile) / max(density, 1e-3))
    drop = np.minimum(*halves)
    hit = drop > 0.12
    start = None
    for i, flag in enumerate(np.append(hit, False)):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            rows.append((start / ppm, (i - start) / ppm, float(drop[start:i].max())))
            start = None
    return rows


def _solids(page, white, hp):
    findings, metrics = [], {}
    ppm, inset = 12, 2.5
    for key, name, _rgb, channel, hue in INKS:
        x, y, w, h = SOLIDS[key]
        rx, ry, rw, rh = x + inset, y + inset, w - 2 * inset, h - 2 * inset
        rgb = page.sample(rx, ry, rw, rh, ppm)
        absorb = np.clip(1 - rgb / white, 0, 1)
        primary = absorb.mean(axis=2) if channel is None else absorb[:, :, channel]
        density = float(np.median(primary))
        color = np.median(rgb.reshape(-1, 3), axis=0)
        half = primary.shape[1] // 2
        streaks = _streaks(primary[:, :half].mean(axis=1), primary[:, half:].mean(axis=1),
                           density, ppm)
        pale = float((primary < 0.6 * density).mean()) if density > 0.05 else 1.0
        measured_hue = _hue(color)
        chroma = float((color.max() - color.min()) / max(white.mean(), 1))
        metrics[key] = {"density": round(density, 3), "streaks": len(streaks),
                        "pale_fraction": round(pale, 4), "rgb": [round(float(c)) for c in color],
                        "hue": None if measured_hue is None else round(measured_hue, 1),
                        "chroma": round(chroma, 3)}
        hint = HP_CLEAN_HINT if hp else CLEAN_HINT
        area = [(x, y, w, h)]
        weak = 0.55 if key == "K" else 0.40
        if density < 0.12:
            findings.append(Finding(
                "bad", f"{name}: no sale",
                f"El bloque de {name.lower()} está casi en blanco (densidad {density:.0%}).",
                ("Mira si el tanque o cartucho de ese color tiene tinta. Si tiene, el "
                 "cabezal de ese color está tapado o hay aire en la manguera: " + hint),
                area))
            continue
        if density < weak:
            findings.append(Finding(
                "warn", f"{name}: sale flojo",
                f"El {name.lower()} sale más claro de lo normal (densidad {density:.0%}).",
                "Revisa el nivel de tinta de ese color. " + hint, area))
        if streaks:
            many = len(streaks) > 2 or pale > 0.03
            lines = ", ".join(f"{ry + s:.1f} mm" for s, _l, _d in streaks[:6])
            findings.append(Finding(
                "bad" if many else "warn",
                f"{name}: inyectores tapados",
                f"{len(streaks)} raya(s) blanca(s) en el bloque de {name.lower()} (a {lines} "
                "del borde superior de la hoja).",
                hint,
                [(x, ry + s - 0.6, w, length + 1.2) for s, length, _d in streaks]))
        if hue is not None and measured_hue is not None and chroma > 0.15 \
                and _hue_gap(measured_hue, hue) > 35:
            findings.append(Finding(
                "warn", f"{name}: tono raro",
                f"El {name.lower()} sale con un tono de {measured_hue:.0f}° (lo normal es "
                f"unos {hue:.0f}°).",
                ("Puede haber tinta de otro color mezclada en ese canal (pasa al recargar el "
                 "tanque equivocado): hacen falta varias limpiezas hasta que salga limpio. "
                 "Si la hoja se ve bien a simple vista, es el escáner el que corrige el color."),
                area))
        if key == "K" and chroma > 0.25:
            findings.append(Finding(
                "warn", "Negro: sale de color",
                "El bloque negro tiene un tono de color: la impresora está armando el negro "
                "con los colores, o el negro sale muy flojo.",
                "Revisa la tinta negra. " + hint, area))
        if not any(f.title.startswith(name) for f in findings):
            findings.append(Finding("ok", f"{name}: bien",
                                    f"Densidad {density:.0%}, sin rayas.", "", area))
    return findings, metrics


def _line_positions(darkness, centers, ppm, axis_len):
    """Centroid (mm) of each line in every row of `darkness` (rows x columns, lines
    run along the rows' direction). centers: expected positions in mm."""
    out = []
    coords = (np.arange(axis_len) + 0.5) / ppm
    for c in centers:
        lo, hi = int((c - 0.9) * ppm), int((c + 0.9) * ppm) + 1
        win = np.clip(darkness[:, lo:hi] - 0.12, 0, None)
        total = win.sum(axis=1)
        pos = np.where(total > 0, (win * coords[lo:hi]).sum(axis=1) / np.maximum(total, 1e-9),
                       np.nan)
        out.append(pos)
    return np.array(out)  # lines x rows


def _alignment(page, white):
    ppm = 20
    x, y, w, h = VLINES
    rgb = page.sample(x, y + 1, w, h - 2, ppm)
    dark = np.clip(1 - rgb / white, 0, 1).mean(axis=2)
    pos = _line_positions(dark, [c - x for c in V_XS], ppm, dark.shape[1])
    rows = pos.shape[1]
    block = int(0.5 * ppm)
    usable = rows - rows % block
    blocks = np.nanmean(pos[:, :usable].reshape(pos.shape[0], -1, block), axis=2)
    t = np.arange(blocks.shape[1], dtype=float)
    residuals = []
    for line in blocks:
        ok = ~np.isnan(line)
        if ok.sum() < 5:
            continue
        fit = np.polyfit(t[ok], line[ok], 1)
        residuals.append(np.where(ok, line - np.polyval(fit, t), np.nan))
    metrics = {}
    if len(residuals) < 10:
        return [Finding("bad", "Líneas verticales: no se ven",
                        "No se encontraron las líneas finas del bloque 2.",
                        "Revisa la tinta negra y los inyectores del negro.", [VLINES])], metrics
    common = np.nanmedian(np.array(residuals), axis=0)  # misalignment moves every line alike
    p2p = float(np.nanmax(common) - np.nanmin(common))
    profile = dark.mean(axis=0)
    widths = []
    for c in V_XS:
        lo, hi = int((c - x - 0.9) * ppm), int((c - x + 0.9) * ppm) + 1
        seg = profile[lo:hi]
        if seg.max() > 0.2:
            widths.append((seg > seg.max() / 2).sum() / ppm)
    width = float(np.median(widths)) if widths else 0.0
    metrics.update(step_mm=round(p2p, 3), line_width_mm=round(width, 3))
    hint = ("Alinea el cabezal desde el driver de Windows (Preferencias de impresión › "
            "Mantenimiento › Alineación de cabezales). Mientras tanto, imprimir con «Alta "
            "velocidad» desactivada (solo en un sentido) evita el problema.")
    findings = []
    if p2p > 0.15:
        findings.append(Finding(
            "bad" if p2p > 0.3 else "warn", "Cabezal desalineado",
            f"Las líneas verticales salen escalonadas (saltos de {p2p:.2f} mm entre pasadas).",
            hint, [VLINES]))
    if width > 0.75:
        findings.append(Finding(
            "warn", "Líneas dobles o borrosas",
            f"Las líneas finas miden {width:.2f} mm (se imprimieron de {LINE_W} mm): la "
            "ida y la vuelta del cabezal no caen en el mismo lugar, o el papel absorbe de más.",
            hint, [VLINES]))
    if not findings:
        findings.append(Finding("ok", "Alineación: bien",
                                f"Escalones de {p2p:.2f} mm, líneas de {width:.2f} mm.", "",
                                [VLINES]))
    return findings, metrics


def _feed(page, white, marks_image):
    ppm = 20
    x, y, w, h = HLINES
    rgb = page.sample(x + 1, y, w - 2, h, ppm)
    dark = np.clip(1 - rgb / white, 0, 1).mean(axis=2).T  # columns become rows
    pos = _line_positions(dark, [c - y for c in H_YS], ppm, dark.shape[1])
    found = np.nanmedian(pos, axis=1)
    metrics, findings = {}, []
    ok = ~np.isnan(found)
    if ok.sum() < 8:
        return [Finding("bad", "Líneas horizontales: no se ven",
                        "No se encontraron las líneas finas del bloque 3.",
                        "Revisa la tinta negra y los inyectores del negro.", [HLINES])], metrics
    expected = np.array([c - y for c in H_YS])
    fit = np.polyfit(expected[ok], found[ok], 1)
    residual = found[ok] - np.polyval(fit, expected[ok])
    worst = float(np.abs(residual).max())
    metrics["feed_jitter_mm"] = round(worst, 3)

    # Whole-page feed: the page's height against its width, straight from the four marks.
    # Only a flatbed scan keeps that ratio; a photo in perspective does not.
    tl, tr, br, bl = marks_image
    top, bottom = np.hypot(*np.subtract(tr, tl)), np.hypot(*np.subtract(br, bl))
    left, right = np.hypot(*np.subtract(bl, tl)), np.hypot(*np.subtract(br, tr))
    flat = abs(top / bottom - 1) < 0.006 and abs(left / right - 1) < 0.006
    span_x = FIDUCIALS["tr"][0] - FIDUCIALS["tl"][0]
    span_y = FIDUCIALS["bl"][1] - FIDUCIALS["tl"][1]
    scale_error = ((left + right) / (top + bottom)) / (span_y / span_x) - 1
    metrics.update(flatbed=bool(flat), feed_scale_error=round(float(scale_error), 4))
    hint = ("Limpia el rodillo de arrastre (el de goma que toma la hoja) con un paño apenas "
            "húmedo, usa papel común no satinado y no cargues hojas onduladas.")
    if worst > 0.12:
        findings.append(Finding(
            "bad" if worst > 0.25 else "warn", "Avance de papel irregular",
            f"Las líneas horizontales quedan mal espaciadas (hasta {worst:.2f} mm de error).",
            hint, [HLINES]))
    if flat and abs(scale_error) > 0.015:
        findings.append(Finding(
            "warn", "El papel avanza " + ("de más" if scale_error > 0 else "de menos"),
            f"La hoja impresa mide un {abs(scale_error):.1%} "
            f"{'más' if scale_error > 0 else 'menos'} de alto de lo que debería.",
            hint, [HLINES]))
    if not findings:
        text = f"Error de espaciado máximo {worst:.2f} mm."
        if flat:
            text += f" Escala vertical {scale_error:+.1%}."
        findings.append(Finding("ok", "Avance de papel: bien", text, "", [HLINES]))
    return findings, metrics


def _stains(page, white):
    ppm = 4
    x, y, w, h = BLANK
    rgb = page.sample(x, y, w, h, ppm)
    dark = np.clip(1 - rgb / white, 0, 1).max(axis=2)
    # 2 x 2 blocks (0.5 mm): a speck of dust on the scanner glass is smaller than that
    hh, ww = dark.shape[0] // 2 * 2, dark.shape[1] // 2 * 2
    blocks = dark[:hh, :ww].reshape(hh // 2, 2, ww // 2, 2).mean(axis=(1, 3))
    spots = blocks > 0.22
    area = float(spots.sum()) * 0.25  # mm^2
    cells = []
    cell = 20  # 10 mm cells of 0.5 mm blocks
    for cy in range(0, spots.shape[0], cell):
        for cx in range(0, spots.shape[1], cell):
            if spots[cy:cy + cell, cx:cx + cell].sum() >= 3:
                cells.append((x + cx / 2, y + cy / 2, cell / 2, cell / 2))
    metrics = {"stain_mm2": round(area, 1), "stain_cells": len(cells)}
    if area > 3 and cells:
        return [Finding(
            "bad" if area > 40 else "warn", "Manchas en el papel",
            f"Hay {area:.0f} mm² manchados en la zona que tendría que estar en blanco "
            f"({len(cells)} zona(s)).",
            ("Limpia los rodillos de salida y la bandeja con un paño apenas húmedo. Si las "
             "manchas aparecen siempre en el mismo lugar o como un rastro a lo largo de la "
             "hoja, el cabezal roza el papel (papel ondulado o grueso) o gotea tinta: revisa "
             "que no haya tinta acumulada bajo el carro."),
            cells[:12])], metrics
    return [Finding("ok", "Zona en blanco: limpia", f"{area:.0f} mm² con marcas.", "",
                    [BLANK])], metrics


def analyze(image, hp=False):
    """Read a scan (QImage) of the printed pattern. Raises PatternNotFound when the
    page cannot be found in it."""
    rgb = to_array(image)
    page, turn, marks_image = _locate(rgb)
    white = np.median(page.sample(*BLANK, 1).reshape(-1, 3), axis=0)
    white = np.maximum(white, 60.0)
    findings, metrics = [], {"turn": turn * 90, "paper_rgb": [round(float(c)) for c in white]}
    for part in (_solids(page, white, hp), _alignment(page, white),
                 _feed(page, white, marks_image), _stains(page, white)):
        findings += part[0]
        metrics.update(part[1] if isinstance(part[1], dict) else {})
    if white.mean() < 150:
        findings.insert(0, Finding(
            "info", "Escaneo oscuro",
            "El papel se ve gris en el escaneo: las densidades pueden no ser exactas.",
            "Escanea con la tapa cerrada y sin «corrección automática» de brillo."))
    preview = page.sample(0, 0, PAGE_W, PAGE_H, PREVIEW_PPM)
    order = sorted(findings, key=lambda f: -LEVELS[f.level])
    return Result(order, from_array(preview), metrics)


def stamp_text(model="", serial=""):
    who = " · ".join(p for p in (model, serial) if p)
    return f"v{VERSION} · {datetime.now():%d/%m/%Y %H:%M}" + (f" · {who}" if who else "")
