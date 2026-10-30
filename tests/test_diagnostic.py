"""Diagnostic pattern: the page is printed (to PDF), "scanned" (rendered, turned,
scaled, blurred, noisy, placed on a bigger platen) and analysed. Faults are painted
on the page before the scan, as a worn printer would leave them."""
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QTransform  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import diagnostic as dg  # noqa: E402

DPI = 300
K = DPI / 25.4


def page(faults=()):
    """The pattern at 300 ppp with the given faults painted on it."""
    image = dg.render(DPI, stamp="prueba")
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    white, black = QColor(255, 255, 255), QColor(0, 0, 0)

    def rect(x, y, w, h):
        return QRectF(x * K, y * K, w * K, h * K)

    for fault in faults:
        if fault == "cyan_clogged":  # three missing nozzles: thin white lines
            x, y, w, h = dg.SOLIDS["C"]
            for ly in (36.0, 42.5, 49.0):
                painter.fillRect(rect(x, ly, w, 0.2), white)
        if fault == "magenta_empty":
            painter.fillRect(rect(*dg.SOLIDS["M"]), white)
        if fault == "yellow_weak":
            painter.fillRect(rect(*dg.SOLIDS["Y"]), QColor(255, 255, 190))
        if fault == "cyan_mixed":  # magenta ink in the cyan tank: violet-blue
            painter.fillRect(rect(*dg.SOLIDS["C"]), QColor(60, 60, 255))
        if fault == "misaligned":  # every other 3 mm pass lands 0.3 mm to the right
            x, y, w, h = dg.VLINES
            painter.fillRect(rect(x - 0.5, y, w + 1, h), white)
            band = 3.0
            for i in range(int(h / band) + 1):
                top = y + i * band
                tall = min(band, y + h - top)
                shift = 0.3 if i % 2 else 0.0
                for lx in dg.V_XS:
                    painter.fillRect(rect(lx - dg.LINE_W / 2 + shift, top, dg.LINE_W, tall), black)
        if fault == "feed":  # two lines out of place
            x, y, w, h = dg.HLINES
            for ly, shift in ((dg.H_YS[5], 0.4), (dg.H_YS[9], -0.35)):
                painter.fillRect(rect(x, ly - 0.3, w, 0.6), white)
                painter.fillRect(rect(x, ly + shift - dg.LINE_W / 2, w, dg.LINE_W), black)
        if fault == "stain":
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(40, 40, 60))
            painter.drawEllipse(QPointF(120 * K, 200 * K), 3 * K, 2 * K)
            painter.drawEllipse(QPointF(60 * K, 150 * K), 1.5 * K, 1.5 * K)
    painter.end()
    return image


def scan(image, angle=1.2, scale=1.0, flip=False, platen=(216, 297), seed=1, blur=True):
    """What a flatbed would give back: the sheet slightly turned (or upside down) on a
    white platen, softened and noisy."""
    width, height = round(platen[0] * K * scale), round(platen[1] * K * scale)
    out = QImage(width, height, QImage.Format_RGB32)
    out.fill(QColor(250, 250, 248))
    painter = QPainter(out)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    t = QTransform()
    t.translate(width / 2, height / 2)
    t.rotate(angle + (180 if flip else 0))
    t.scale(scale, scale)
    t.translate(-image.width() / 2, -image.height() / 2)
    painter.setTransform(t)
    painter.drawImage(0, 0, image)
    painter.end()
    rgb = dg.to_array(out).astype(np.float32)
    if blur:  # a scanner is a little soft: 3 x 3 box
        padded = np.pad(rgb, ((1, 1), (1, 1), (0, 0)), mode="edge")
        rgb = sum(padded[dy:dy + rgb.shape[0], dx:dx + rgb.shape[1]]
                  for dy in range(3) for dx in range(3)) / 9
    rng = np.random.default_rng(seed)
    rgb = rgb * 0.94 + 8 + rng.normal(0, 3, rgb.shape)  # paper is never pure white
    return dg.from_array(rgb)


def titles(result, level=None):
    return [f.title for f in result.findings if level is None or f.level == level]


class Diagnostic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QApplication.instance() or QApplication([])

    def test_clean_page_has_no_problems(self):
        result = dg.analyze(scan(page()))
        self.assertEqual(result.problems(), [], titles(result))
        self.assertEqual(result.level, "ok")
        self.assertIn("sin fallas", result.summary())

    def test_upside_down_and_smaller_scan(self):
        result = dg.analyze(scan(page(["cyan_clogged"]), angle=-2.0, scale=0.55, flip=True))
        self.assertEqual(result.metrics["turn"], 180)
        self.assertIn("Cian: inyectores tapados", titles(result))
        self.assertEqual(len(result.problems()), 1, titles(result))

    def test_clogged_nozzles(self):
        result = dg.analyze(scan(page(["cyan_clogged"])))
        found = [f for f in result.findings if f.title == "Cian: inyectores tapados"]
        self.assertEqual(len(found), 1, titles(result))
        self.assertEqual(result.metrics["C"]["streaks"], 3)
        self.assertEqual(result.metrics["M"]["streaks"], 0)
        self.assertIn("limpieza", found[0].action)

    def test_missing_and_weak_colour(self):
        result = dg.analyze(scan(page(["magenta_empty", "yellow_weak"])))
        self.assertIn("Magenta: no sale", titles(result, "bad"))
        self.assertIn("Amarillo: sale flojo", titles(result, "warn"))
        self.assertIn("Cian: bien", titles(result, "ok"))

    def test_mixed_ink(self):
        result = dg.analyze(scan(page(["cyan_mixed"])))
        self.assertIn("Cian: tono raro", titles(result))

    def test_misaligned_head(self):
        result = dg.analyze(scan(page(["misaligned"])))
        self.assertIn("Cabezal desalineado", titles(result), titles(result))
        self.assertGreater(result.metrics["step_mm"], 0.2)

    def test_paper_feed(self):
        result = dg.analyze(scan(page(["feed"])))
        self.assertIn("Avance de papel irregular", titles(result))

    def test_feed_scale(self):
        """The sheet came out 3 % taller than it should: the feed roller slips the other way."""
        image = page()
        taller = image.scaled(image.width(), round(image.height() * 1.03),
                              Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        result = dg.analyze(scan(taller, angle=0.3, platen=(216, 310)))
        self.assertTrue(result.metrics["flatbed"])
        self.assertIn("El papel avanza de más", titles(result))

    def test_stains(self):
        result = dg.analyze(scan(page(["stain"])))
        found = [f for f in result.findings if f.title == "Manchas en el papel"]
        self.assertEqual(len(found), 1, titles(result))
        self.assertGreaterEqual(len(found[0].areas), 2)

    def test_dust_is_not_a_stain(self):
        image = scan(page())
        rgb = dg.to_array(image)
        rng = np.random.default_rng(3)
        for _ in range(40):  # single-pixel specks of dust on the glass
            y, x = rng.integers(1400, 3000), rng.integers(300, 2200)
            rgb[y, x] = 30
        result = dg.analyze(dg.from_array(rgb))
        self.assertNotIn("Manchas en el papel", titles(result))

    def test_not_the_pattern(self):
        blank = QImage(2480, 3508, QImage.Format_RGB32)
        blank.fill(QColor(255, 255, 255))
        with self.assertRaises(dg.PatternNotFound):
            dg.analyze(blank)
        cropped = scan(page()).copy(0, 0, 2000, 3508)  # right-hand marks cut off
        with self.assertRaises(dg.PatternNotFound):
            dg.analyze(cropped)

    def test_print_to_pdf_and_annotate(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "patron.pdf"
            dg.print_pattern(output=out, stamp="L3150 · X5E9205615")
            self.assertGreater(out.stat().st_size, 1000)
        result = dg.analyze(scan(page(["cyan_clogged", "stain"])))
        image = dg.annotated(result)
        self.assertEqual(image.width(), round(dg.PAGE_W * dg.PREVIEW_PPM))
        self.assertFalse(image.isNull())


if __name__ == "__main__":
    unittest.main()
