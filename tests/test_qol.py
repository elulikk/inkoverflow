"""Quality-of-life helpers that need neither a printer nor a window."""
import os
import struct
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "brand"))

from PySide6.QtGui import QImage  # noqa: E402

import app  # noqa: E402
import history  # noqa: E402
import make_brand  # noqa: E402
import prefs  # noqa: E402
import report  # noqa: E402


class TempData(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = history.DATA
        history.DATA = Path(self.tmp.name) / "data"

    def tearDown(self):
        history.DATA = self.saved
        self.tmp.cleanup()


class Prefs(TempData):
    def test_missing_or_damaged_file_gives_defaults(self):
        self.assertEqual(prefs.load(), {})
        history.DATA.mkdir()
        (history.DATA / "prefs.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(prefs.load(), {})
        self.assertEqual(prefs.get_int("page", 0, 0, 4), 0)

    def test_save_merges_and_get_int_clamps(self):
        prefs.save(page=2)
        prefs.save(eeprom_end=9999, geometry="abc")
        self.assertEqual(prefs.load()["page"], 2)
        self.assertEqual(prefs.get_int("page", 0, 0, 4), 2)
        self.assertEqual(prefs.get_int("eeprom_end", 255, 0, 2047), 2047)
        prefs.save(page=-3)
        self.assertEqual(prefs.get_int("page", 0, 0, 4), 0)
        prefs.save(page="2", eeprom_start=True)           # wrong types are ignored
        self.assertEqual(prefs.get_int("page", 1, 0, 4), 1)
        self.assertEqual(prefs.get_int("eeprom_start", 7, 0, 2047), 7)

    def test_nothing_dangerous_has_a_slot(self):
        """The cleaning mode and the restore box are never remembered."""
        prefs.save(page=1)
        self.assertEqual(set(prefs.load()), {"page"})


class PrinterList(TempData):
    def test_printers_newest_first_without_blank_serials(self):
        history.record("copia", "L3150", "AAA")
        history.record("limpieza", "L3150", "BBB")
        history.record("informe", "L3110", "")             # no serial: not a printer
        history.record("copia", "L3150", "AAA")
        printers = history.printers()
        self.assertEqual([p["serial"] for p in printers], ["AAA", "BBB"])
        self.assertEqual(printers[0]["model"], "L3150")
        self.assertTrue(printers[0]["last"])

    def test_no_history_no_printers(self):
        self.assertEqual(history.printers(), [])


class CustomerSummary(unittest.TestCase):
    def test_summary_has_the_report_figures(self):
        data = report.sample()
        text = report.summary_text(data)
        self.assertIn("EPSON L3150 Series · serie X5E9205615", text)
        self.assertIn("Almohadilla principal: 5718 / 6346 puntos (90.1% · Crítico)", text)
        self.assertIn("Almohadilla del platen: 0 / 3416 puntos (0.0% · Normal)", text)
        self.assertIn("Páginas impresas: 67", text)
        self.assertTrue(text.rstrip().endswith("MAG Tecnología · 24/10/2026 12:00"))
        self.assertNotIn("sin contar", text)

    def test_uncounted_ink_is_stated(self):
        data = dict(report.sample(), hidden=100, when=datetime(2026, 10, 24, 12, 0))
        text = report.summary_text(data)
        self.assertIn("Tinta sin contar: 100 puntos", text)
        self.assertIn("5818 / 6346 (91.7%)", text)


class ProgressHelpers(unittest.TestCase):
    def test_bar_never_reaches_100_by_itself(self):
        self.assertEqual(app.clean_progress(0, 190), 0)
        self.assertEqual(app.clean_progress(95, 190), 50)
        self.assertEqual(app.clean_progress(190, 190), 99)
        self.assertEqual(app.clean_progress(900, 190), 99)

    def test_remaining_text(self):
        self.assertEqual(app.remaining_text(0, 190), "quedan unos 3:10")
        self.assertEqual(app.remaining_text(130, 190), "quedan unos 1:00")
        self.assertEqual(app.remaining_text(188, 190), "debería terminar enseguida")
        self.assertIn("más de lo habitual", app.remaining_text(400, 190))

    def test_cell_tooltip(self):
        self.assertEqual(app.cell_tooltip(48, 0x3A),
                         "Celda 48 (0x0030) = 0x3A · 58 · 00111010b")
        self.assertIn("sin lectura", app.cell_tooltip(1, None))
        self.assertIn("reseteo", app.cell_tooltip(49, 0x16, True))


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class BrandKit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.files = make_brand.build(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_whole_kit_is_written(self):
        expected = {"icon.svg", "inkoverflow.ico", "mark_dark.svg", "mark_light.svg",
                    "logo_dark.svg", "logo_dark.png", "logo_light.svg", "logo_light.png",
                    "banner.svg", "banner.png", "muestrario.png",
                    *(f"icon_{s}.png" for s in make_brand.ICON_SIZES)}
        self.assertEqual(set(self.files), expected)
        self.assertTrue(all(p.stat().st_size > 400 for p in self.files.values()))

    def test_icon_pngs_have_the_size_in_their_name(self):
        for size in make_brand.ICON_SIZES:
            image = QImage(str(self.files[f"icon_{size}.png"]))
            self.assertEqual((image.width(), image.height()), (size, size))
            self.assertTrue(image.hasAlphaChannel())

    def test_ico_is_well_formed(self):
        data = self.files["inkoverflow.ico"].read_bytes()
        reserved, kind, count = struct.unpack_from("<HHH", data)
        self.assertEqual((reserved, kind, count), (0, 1, len(make_brand.ICO_SIZES)))
        sizes = []
        for i in range(count):
            width, height, _c, _r, planes, bits, length, offset = struct.unpack_from(
                "<BBBBHHII", data, 6 + 16 * i)
            sizes.append(width or 256)
            self.assertEqual((width, planes, bits), (height, 1, 32))
            self.assertEqual(data[offset:offset + 8], PNG_SIGNATURE)
            self.assertLessEqual(offset + length, len(data))
        self.assertEqual(sizes, list(make_brand.ICO_SIZES))

    def test_text_is_outlines_not_fonts(self):
        """The SVGs must look the same on a machine without Segoe UI."""
        for name in ("logo_dark.svg", "logo_light.svg", "banner.svg"):
            svg = self.files[name].read_text(encoding="utf-8")
            self.assertNotIn("<text", svg)
            self.assertNotIn("font-family", svg)
        # a missing font would leave the wordmark empty or tiny
        self.assertGreater(len(self.files["logo_dark.svg"].read_text(encoding="utf-8")), 3000)

    def test_logo_is_wide_and_uses_the_app_palette(self):
        image = QImage(str(self.files["logo_dark.png"]))
        self.assertEqual(image.width(), 1600)
        self.assertGreater(image.width() / image.height(), 3.5)
        svg = self.files["logo_dark.svg"].read_text(encoding="utf-8")
        self.assertIn(app.C["accent"], svg)          # "Overflow" in the app's accent colour

    def test_shipped_files_are_the_generator_output(self):
        """brand/ in the project must not drift from the code that makes it. Only the
        icon is compared exactly: the logos hold text outlines, which can differ by a
        fraction of a pixel between Qt font engines."""
        shipped = Path(make_brand.HERE)
        self.assertEqual((shipped / "icon.svg").read_text(encoding="utf-8"),
                         make_brand.icon_svg())
        self.assertEqual((shipped / "inkoverflow.ico").read_bytes()[:6],
                         self.files["inkoverflow.ico"].read_bytes()[:6])
        for name in ("logo_dark.png", "logo_light.png", "banner.png"):
            self.assertTrue((shipped / name).is_file(), name)

    def test_ico_packing_of_arbitrary_images(self):
        ico = make_brand.ico_bytes({16: PNG_SIGNATURE + b"a", 256: PNG_SIGNATURE + b"bb"})
        self.assertEqual(struct.unpack_from("<HHH", ico), (0, 1, 2))
        self.assertEqual(ico[6], 16)                 # first entry: 16 px
        self.assertEqual(ico[6 + 16], 0)             # 256 is stored as 0
        self.assertTrue(ico.endswith(PNG_SIGNATURE + b"bb"))


if __name__ == "__main__":
    unittest.main()
