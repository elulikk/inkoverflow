"""MAG test page: preview and printing of the chosen version (see VERSIONS).

Printed through a normal Windows queue (a rendered image on a full A4 page),
which the Epson V4 driver accepts, unlike the RAW maintenance data.
"""
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSize
from PySide6.QtGui import QImage, QPageLayout, QPageSize, QPainter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

ASSETS = Path(__file__).resolve().parent / "assets"
PDF = ASSETS / "prueba_impresion_mag.pdf"  # the original, full-colour header and footer

# key -> (name shown in the app, file, ink note). The alternatives are made by
# assets/alternativas/generar.py; "ink" is relative to the original page.
VERSIONS = {
    "D": ("Ahorro máximo", ASSETS / "alternativas" / "prueba_mag_D.pdf", "~25 % de la tinta original"),
    "A": ("Blanca con acentos", ASSETS / "alternativas" / "prueba_mag_A.pdf", "~45 % de la tinta original"),
    "C": ("Logo en tarjeta", ASSETS / "alternativas" / "prueba_mag_C.pdf", "~50 % de la tinta original"),
    "B": ("Franja angosta", ASSETS / "alternativas" / "prueba_mag_B.pdf", "~60 % de la tinta original"),
    "O": ("Original (mucha tinta)", PDF, "cabecera y pie a todo color"),
}
DEFAULT = "D"


def version_path(key):
    """PDF of a version; the default one for an unknown key."""
    return VERSIONS.get(key, VERSIONS[DEFAULT])[1]
A4_300DPI = QSize(2480, 3508)  # enough detail for 4 pt text without giant buffers


def _load(path=PDF):
    doc = QPdfDocument()
    doc.load(str(path))
    if doc.status() != QPdfDocument.Status.Ready or doc.pageCount() < 1:
        raise RuntimeError(f"No se pudo abrir el PDF: {path.name}")
    return doc


def render_page(width, path=PDF):
    """First page scaled to the given width, as a QImage (for the preview)."""
    doc = _load(path)
    size = doc.pagePointSize(0)
    height = round(width * size.height() / size.width())
    return doc.render(0, QSize(width, height))


def print_pdf(queue=None, output=None, path=PDF):
    """Print every page on A4, no margins. queue: Windows printer name; output:
    a .pdf path to print to a file instead (used to test without paper)."""
    doc = _load(path)
    if output:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(output))
    else:
        info = QPrinterInfo.printerInfo(queue)
        if info.isNull():
            raise RuntimeError(f"Windows no encuentra la cola «{queue}».")
        printer = QPrinter(info, QPrinter.PrinterMode.ScreenResolution)
    printer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4),
                                      QPageLayout.Orientation.Portrait,
                                      QMarginsF(0, 0, 0, 0)))
    printer.setFullPage(True)
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("No se pudo iniciar la impresión en esa cola.")
    try:
        for index in range(doc.pageCount()):
            if index:
                printer.newPage()
            image = doc.render(index, A4_300DPI)
            if image.isNull():
                raise RuntimeError(f"No se pudo dibujar la página {index + 1}.")
            painter.drawImage(painter.viewport(), image)
    finally:
        painter.end()
    return doc.pageCount()
