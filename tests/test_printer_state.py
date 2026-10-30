"""Ink levels and printer warnings (printer_state.py), with no hardware.

The status blocks are the real L3150 replies of the USB capture (captured_frames.json) and
synthetic ones built with the same function the fake printer uses (build_st2), decoded by
the backend's own parser exactly as `-i` does. The window tests reuse the fakes of
test_detect.py: no backend process and no USB session is started.
"""
import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "backend"))

from epson_print_conf import EpsonPrinter  # noqa: E402
from epson_usb.status import build_st2  # noqa: E402

import printer_state as ps  # noqa: E402
import report  # noqa: E402
from test_detect import WindowCase, info_for, unit  # noqa: E402

FX = json.loads((HERE / "captured_frames.json").read_text())


def decode(block):
    """What the backend puts in info['printer_status'] for this status block."""
    return EpsonPrinter.status_parser(None, block)


def captured(name):
    return decode(bytes.fromhex(FX[name])[6:])    # without the 6-byte D4 header


def synthetic(*elements):
    return decode(build_st2(list(elements)))


# A cartridge printer (like the XP-230): black, cyan, magenta, yellow with real levels.
CARTRIDGES = (0x0F, bytes([3, 1, 0, 20, 3, 1, 80, 4, 2, 55, 5, 3, 9]))
IDLE = (0x01, b"\x04")


class RealL3150Replies(unittest.TestCase):
    def test_idle_tanks_are_not_measured_and_nothing_is_wrong(self):
        status = captured("status_idle")
        inks = ps.inks(status)
        self.assertEqual([i.name for i in inks], ["Negro", "Cian", "Magenta", "Amarillo"])
        self.assertTrue(all(i.level is None for i in inks), "105 is not a level")
        self.assertIs(ps.ink_measured(status), False)
        self.assertEqual(ps.alerts(status), [])
        self.assertEqual(ps.chip(status, []), ("Lista", "ok"))
        self.assertEqual(ps.status_text(status), "En reposo")

    def test_cleaning_is_busy_not_an_error(self):
        status = captured("status_cleaning")
        self.assertEqual(ps.alerts(status), [])
        self.assertEqual(ps.chip(status, []), ("Limpiando", "warn"))

    def test_full_pads_error_is_explained_once(self):
        status = captured("status_error")
        found = ps.alerts(status)
        self.assertEqual(len(found), 1, "the full box is the same problem as the error code")
        self.assertEqual(found[0].severity, ps.ERROR)
        self.assertEqual(found[0].title, "Almohadillas de tinta residual llenas")
        self.assertIn("reseteá el contador", found[0].action)
        self.assertEqual(found[0].light, ps.PADS_LIGHTS)
        self.assertEqual(ps.chip(status, found),
                         ("Error: Almohadillas de tinta residual llenas", "bad"))

    def test_box_full_while_still_cleaning_warns_before_the_lock(self):
        # seen in the capture: the box reads "full" two polls before the printer errors
        status = synthetic((0x01, b"\x07"), (0x37, b"\x02\x02\x00\x00\x00"))
        found = ps.alerts(status)
        self.assertEqual([a.title for a in found], ["Depósito de tinta residual principal lleno"])
        self.assertEqual(found[0].severity, ps.ERROR)


class SyntheticReplies(unittest.TestCase):
    def test_cartridge_levels_are_shown_black_first(self):
        status = synthetic(IDLE, CARTRIDGES)
        self.assertIs(ps.ink_measured(status), True)
        self.assertEqual([(i.name, i.level) for i in ps.inks(status)],
                         [("Negro", 20), ("Cian", 80), ("Magenta", 55), ("Amarillo", 9)])

    def test_paper_out(self):
        status = synthetic((0x01, b"\x00"), (0x02, b"\x06"))
        found = ps.alerts(status)
        self.assertEqual([(a.severity, a.title, a.light) for a in found],
                         [(ps.ERROR, "Sin papel", ps.PAPER_LIGHT)])
        self.assertEqual(ps.chip(status, found), ("Error: Sin papel", "bad"))

    def test_paper_jam_is_not_reported_twice(self):
        status = synthetic((0x01, b"\x00"), (0x02, b"\x04"), (0x35, b"\x01"))
        self.assertEqual([a.title for a in ps.alerts(status)], ["Atasco de papel"])

    def test_ink_low_on_a_cartridge_printer_is_a_warning(self):
        status = synthetic(IDLE, CARTRIDGES, (0x04, b"\x10"))
        found = ps.alerts(status)
        self.assertEqual([(a.severity, a.title) for a in found],
                         [(ps.WARNING, "Tinta baja (negro o amarillo)")])
        self.assertIn("cartucho", found[0].action)
        self.assertEqual(ps.chip(status, found), ("Lista · 1 aviso", "warn"))

    def test_ink_out_on_tanks_says_the_level_is_estimated(self):
        tanks = (0x0F, bytes([3, 1, 0, 105, 3, 1, 105]))
        found = ps.alerts(synthetic((0x01, b"\x00"), (0x02, b"\x05"), tanks))
        self.assertEqual(found[0].title, "Sin tinta")
        self.assertIn("no mide", found[0].action)

    def test_unknown_error_keeps_its_code(self):
        found = ps.alerts(synthetic((0x01, b"\x00"), (0x02, b"\x99")))
        self.assertEqual(found[0].title, "Error de la impresora sin descripción")
        self.assertEqual(found[0].code, "código 153")

    def test_error_without_a_cause(self):
        found = ps.alerts(synthetic((0x01, b"\x00")))
        self.assertEqual([a.title for a in found], ["La impresora está en error"])

    def test_nearly_full_pads_warn_before_the_printer_does(self):
        status = synthetic(IDLE)
        self.assertEqual(ps.alerts(status, pads_pct=50), [])
        found = ps.alerts(status, pads_pct=93.4)
        self.assertEqual([a.title for a in found], ["Almohadillas al 93 %"])

    def test_errors_come_before_warnings(self):
        status = synthetic((0x01, b"\x00"), (0x02, b"\x02"), CARTRIDGES, (0x04, b"\x11"))
        self.assertEqual([a.severity for a in ps.alerts(status)], [ps.ERROR, ps.WARNING])

    def test_every_backend_error_code_has_a_translation(self):
        source = (ROOT / "backend" / "epson_print_conf.py").read_text(encoding="utf-8")
        start = source.index("errcode_ids = {")
        block = source[start:source.index("}", start)]
        names = [line.split(":", 1)[1].strip().strip(",").strip('"').strip()
                 for line in block.splitlines()[1:] if ":" in line]
        missing = [n for n in names if n not in ps.ERRORS]
        self.assertEqual(missing, [])


class Report(unittest.TestCase):
    def data(self, **extra):
        return {**report.sample(), **extra}

    def test_report_and_summary_list_ink_and_errors(self):
        data = self.data(inks=[("Negro", None), ("Cian", None)], refills="N 2 · C 1",
                         alerts=[(ps.ERROR, "Sin papel: Cargá papel.")])
        html = report.build_html(data)
        self.assertIn("Tinta y avisos", html)
        self.assertIn("no mide los tanques", html)
        self.assertIn("Recargas registradas", html)
        self.assertIn("Sin papel", html)
        text = report.summary_text(data)
        self.assertIn("Tinta: Negro no medido · Cian no medido", text)
        self.assertIn("Error: Sin papel", text)

    def test_old_data_without_ink_still_builds(self):
        self.assertNotIn("Tinta y avisos", report.build_html(report.sample()))
        report.summary_text(report.sample())


class InTheWindow(WindowCase):
    def setUp(self):
        super().setUp()
        self.attached = [unit("L3150")]
        self.status = None

    def read(self, model):
        self.reads.append(model)
        info = info_for(f"EPSON {model} Series")
        if self.status is not None:
            info["printer_status"] = self.status
        return info

    def open(self, status):
        self.status = status
        from unittest import mock
        import backend_cli as be
        patcher = mock.patch.object(be, "read_info", self.read)
        patcher.start()
        self.addCleanup(patcher.stop)
        return self.open_window()

    def test_tanks_and_no_warnings(self):
        win = self.open(captured("status_idle"))
        self.assertEqual(win.chip.text(), "Lista")
        self.assertEqual(win.ink_row.count() - 1, 4, "four tanks and a stretch")
        self.assertIn("no mide", win.ink_note.text())
        self.assertIn("Sin avisos", win.alerts_label.text())
        self.assertTrue(win.banner.isHidden())
        self.assertEqual(win.usage["Estado"].text(), "En reposo")

    def test_full_pads_show_in_the_chip_banner_and_details(self):
        win = self.open(captured("status_error"))
        self.assertEqual(win.chip.text(), "Error: Almohadillas de tinta residual llenas")
        self.assertEqual(win.usage["Depósito mantenimiento"].text(), "lleno")
        self.assertFalse(win.banner.isHidden())
        self.assertIn("Almohadillas de tinta residual llenas", win.banner.text())
        self.assertIn("Almohadillas de tinta residual llenas", win.alerts_label.text())
        self.assertIn("En la impresora", win.alerts_label.text())
        details = "\n".join(
            win.details.item(r, 1).text() for r in range(win.details.rowCount())
            if win.details.item(r, 1))
        self.assertIn("Ink overflow error", details)
        self.assertIn("Aviso de la impresora: Almohadillas", win.log.toPlainText())
        data = win._report_data()
        self.assertEqual(data["alerts"][0][0], ps.ERROR)
        self.assertEqual(data["inks"][0], ("Negro", None))

    def test_cartridge_levels(self):
        win = self.open(synthetic(IDLE, CARTRIDGES, (0x04, b"\x10")))
        self.assertEqual(win.chip.text(), "Lista · 1 aviso")
        self.assertIn("Nivel estimado", win.ink_note.text())
        self.assertIn("Tinta baja", win.alerts_label.text())

    def test_unplugging_clears_ink_and_warnings(self):
        win = self.open(captured("status_error"))
        self.attached = []
        self.refresh(win)
        self.assertEqual(win.alerts, [])
        self.assertEqual(win.ink_row.count(), 1, "only the stretch is left")
        self.assertEqual(win.alerts_label.text(), "Sin lectura.")


if __name__ == "__main__":
    unittest.main()
