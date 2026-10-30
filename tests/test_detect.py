"""Detecting the printer that is really plugged in, and the XP-231.

No hardware: the Windows device list (spooler.usb_printers), the Windows queues and the
backend readings are replaced by fakes, and nothing here may start a backend process.
"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import app  # noqa: E402
import backend_cli as be  # noqa: E402
import cleaning  # noqa: E402
import detect  # noqa: E402
import history  # noqa: E402
import mapped_models  # noqa: E402
import pnp  # noqa: E402
import spooler  # noqa: E402
from widgets import QSS  # noqa: E402

DB = be.models()   # the real database, loaded once (this is the only backend process)


def unit(model, instance="6&aaa&0&0001", pid="1143"):
    """A printer as Windows reports it: the interface name, the generic bus name and the
    product string of the parent USB device."""
    return pnp.UsbPrinter(instance, (f"EPSON {model} Series", "USB2.0 Printer",
                                     f"{model} Series"), pid)


def info_for(description, serial="SER0001"):
    return {"device_identification": {"Description": [description], "FG": ["EPSON"],
                                      "Commands": ["ESCPL2,BDC,D4"], "CID": ["EpsonRGB"],
                                      "DDS": ["0"], "ELG": ["0"], "RID": ["0"]},
            "firmware_version": "FW 01", "serial_number": serial,
            "printer_status": {"ready": True, "status": (4, "Idle (ready to print)"),
                               "maintenance_box_1": "not full (0)",
                               "maintenance_box_2": "not full (0)"},
            "stats": {}, "snmp_info": {"Power Off Timer": ""}}


def pump(qapp, condition, limit=60.0):
    end = time.time() + limit
    while time.time() < end and not condition():
        qapp.processEvents()
        time.sleep(0.02)
    for _ in range(10):
        qapp.processEvents()
    return condition()


# Queues of printers that are no longer plugged in. Every one claims to be "active" (the
# worst case: stale ports that still carry an Epson description).
OLD_QUEUES = [spooler.Queue("EPSON L3110 Series (Copiar 1)", "USB019", True),
              spooler.Queue("EPSON L3150 Series (Copiar 3)", "USB016", True),
              spooler.Queue("EPSON L3150 Series", "USB006", True),
              spooler.Queue("EPSON L3210 Series (Copiar 1)", "USB076", True),
              spooler.Queue("EPSON L395 Series (Copiar 2)", "USB054", True)]


class WindowCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QApplication.instance() or QApplication([])
        cls.qapp.setStyleSheet(QSS)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.attached = []          # what Windows says is plugged in
        self.queues = list(OLD_QUEUES)
        self.declares = None        # what the printer answers; default: its own model
        self.in_error = False       # the printer reports status "Error" (not ready)
        self.no_serial = False      # the backend returns no serial number for the model
        self.reads, self.warnings = [], []

        def read_info(model):
            self.reads.append(model)
            info = info_for(self.declares or f"EPSON {model} Series")
            if self.in_error:
                info["printer_status"].update(ready=False, status=(0, "Error"))
            if self.no_serial:
                del info["serial_number"]
            return info

        for target, name, replacement in (
                (history, "DATA", Path(self.tmp.name) / "data"),
                (app, "BACKUP_DIR", Path(self.tmp.name) / "backups"),
                (spooler, "usb_printers", lambda: list(self.attached)),
                (spooler, "usb_instances", lambda: [p.instance for p in self.attached]),
                (spooler, "epson_queues", lambda hint="": list(self.queues)),
                (be, "read_info", read_info),
                (be, "read_cells", mock.Mock(side_effect=lambda m, addrs: {a: 0 for a in addrs})),
                (be, "reset", mock.Mock(return_value=(True, "done")))):
            patcher = mock.patch.object(target, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Qt classes are patched by hand, like tests/test_ui.py does
        saved = QMessageBox.warning, QMessageBox.information, QMessageBox.exec
        QMessageBox.warning = staticmethod(
            lambda *a, **k: self.warnings.append(a[2]) or QMessageBox.Ok)
        QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
        QMessageBox.exec = lambda box: QMessageBox.Yes      # every confirmation is accepted
        self.addCleanup(lambda: (setattr(QMessageBox, "warning", saved[0]),
                                 setattr(QMessageBox, "information", saved[1]),
                                 setattr(QMessageBox, "exec", saved[2])))
        # any backend process at all would go through subprocess.run
        patcher = mock.patch.object(be.subprocess, "run", mock.Mock(
            side_effect=AssertionError("a backend process was started")))
        self.spawn = patcher.start()
        self.addCleanup(patcher.stop)

    def open_window(self):
        win = app.MainWindow()
        win.show()
        self.addCleanup(win.close)
        self.assertTrue(pump(self.qapp, lambda: win.detection is not None and not win.busy),
                        "the window never finished looking for the printer")
        return win

    def refresh(self, win):
        win.refresh()
        self.assertTrue(pump(self.qapp, lambda: not win.busy))

    def choose(self, win, model):
        """Pick a model in the selector like the user does (this triggers a refresh)."""
        win.model.setCurrentIndex(win.model.findData(model))
        self.assertTrue(pump(self.qapp, lambda: not win.busy))

    def assertNothingEnabled(self, win):
        for button in win.guarded:
            self.assertFalse(button.isEnabled(), button.text())


class OneConnectedPrinter(WindowCase):
    def test_the_attached_printer_decides_not_the_old_queues(self):
        self.attached = [unit("L395", pid="1122")]
        win = self.open_window()
        self.assertEqual(win.model_name, "L395")
        self.assertEqual(self.reads, ["L395"], "no remembered model may be read first")
        self.assertEqual(win.model.currentIndex(), 0, "still on Automático")
        self.assertEqual(win.model.itemText(0), "Automático · L395")
        self.assertTrue(win.info)
        self.assertEqual([q.name for q in win.queues], ["EPSON L395 Series (Copiar 2)"])
        self.assertEqual(win.usb, ["6&aaa&0&0001"])
        self.assertNotIn("L3150", self.reads)

    def test_old_queues_alone_select_nothing(self):
        # five Epson queues, all "active", and no printer: the old code fell back to L3150
        self.attached = []
        win = self.open_window()
        self.assertEqual(win.model_name, "")
        self.assertEqual(win.model.currentIndex(), 0)
        self.assertNotEqual(win.model.currentText(), "L3150")


class NoPrinter(WindowCase):
    def test_it_says_so_and_starts_nothing(self):
        self.attached = []
        win = self.open_window()
        self.assertEqual(win.detection.status, detect.NONE)
        self.assertEqual(win.model_name, "")
        self.assertEqual(win.model.itemText(0), "Automático · sin impresora")
        self.assertFalse(win.info)
        self.assertEqual(self.reads, [], "no D4 session without a printer")
        be.read_cells.assert_not_called()
        self.spawn.assert_not_called()
        self.assertFalse(win.banner.isHidden())
        self.assertIn("ninguna impresora Epson conectada por USB", win.banner.text())
        self.assertNotIn("L3150", win.banner.text())
        self.assertEqual(win.subtitle.text(), "Sin impresora")
        self.assertEqual(win.chip.text(), "Sin conexión")
        self.assertEqual(win.usage["Páginas impresas"].text(), "--")
        self.assertNothingEnabled(win)
        self.assertIn("conéctala", win.btn_nozzle.toolTip())

    def test_unplugging_and_updating_in_automatic_forgets_the_model(self):
        self.attached = [unit("L3150")]
        win = self.open_window()
        self.assertEqual(win.model_name, "L3150")
        self.attached = []
        self.refresh(win)
        self.assertEqual(win.model_name, "")
        self.assertFalse(win.info)
        self.assertEqual(self.reads, ["L3150"], "the unplugged printer is not read again")
        self.attached = [unit("L395", pid="1122")]      # another one is plugged in
        self.refresh(win)
        self.assertEqual(win.model_name, "L395")
        self.assertEqual(self.reads, ["L3150", "L395"])
        self.assertTrue(win.info)


class SeveralPrinters(WindowCase):
    def test_two_printers_are_not_guessed(self):
        self.attached = [unit("L3150", "6&aaa&0&0001"), unit("L395", "6&bbb&0&0001", "1122")]
        win = self.open_window()
        self.assertEqual(win.detection.status, detect.SEVERAL)
        self.assertEqual(win.model_name, "")
        self.assertEqual(self.reads, [])
        self.spawn.assert_not_called()
        self.assertEqual(len(win.usb), 2)
        self.assertIn("2 impresoras Epson", win.banner.text())
        self.assertIn("EPSON L3150 Series", win.banner.text())
        self.assertIn("EPSON L395 Series", win.banner.text())
        self.assertNothingEnabled(win)


class UnsupportedModel(WindowCase):
    def test_a_model_the_backend_lacks_is_reported_not_guessed(self):
        self.attached = [unit("L3210")]
        win = self.open_window()
        self.assertEqual(win.detection.status, detect.UNKNOWN)
        self.assertEqual(win.model_name, "")
        self.assertEqual(self.reads, [])
        self.assertIn("EPSON L3210 Series", win.banner.text())
        self.assertIn("base del backend", win.banner.text())
        self.assertEqual(win.model.itemText(0), "Automático · modelo no soportado")
        self.assertNothingEnabled(win)


class ManualChoice(WindowCase):
    def test_the_user_choice_wins_until_automatic_is_picked_again(self):
        self.attached = [unit("L3150")]
        win = self.open_window()
        self.assertEqual(self.reads, ["L3150"])

        self.choose(win, "L4150")
        self.assertEqual(self.reads[-1], "L4150")
        self.assertEqual(win.model_name, "L4150")
        self.assertEqual(win.detected_model, "L3150", "what is plugged in is still known")
        rows = {win.details.item(r, 0).text(): win.details.item(r, 1)
                for r in range(win.details.rowCount()) if win.details.item(r, 1)}
        self.assertEqual(rows["Modelo usado"].text(), "L4150 (elegido a mano)")
        self.assertEqual(rows["Windows las llama"].text(), "EPSON L3150 Series")

        self.refresh(win)                       # F5 / Actualizar keeps the choice
        self.assertEqual(self.reads[-1], "L4150")
        self.attached = [unit("L395", pid="1122")]   # a different printer is plugged in
        self.refresh(win)
        self.assertEqual(self.reads[-1], "L4150", "a manual choice is never overridden")
        self.assertEqual(win.model_name, "L4150")
        self.assertEqual(win.model.itemText(0), "Automático · L395")
        self.assertIn("elegiste L4150 a mano", win.log.toPlainText())

        self.choose(win, "")                    # back to Automático
        self.assertEqual(win.model.currentIndex(), 0)
        self.assertEqual(self.reads[-1], "L395")
        self.assertEqual(win.model_name, "L395")

    def test_a_manual_choice_is_read_even_with_nothing_attached(self):
        """The escape hatch for a printer on a driver Windows does not list as USB print."""
        win = self.open_window()
        self.assertEqual(self.reads, [])
        self.choose(win, "L3150")
        self.assertEqual(self.reads, ["L3150"])
        self.assertEqual(win.model_name, "L3150")

    def test_the_selector_starts_on_automatic_and_lists_every_model(self):
        win = self.open_window()
        self.assertEqual(win.model.itemData(0), "")
        self.assertEqual(win.model.count(), 1 + len(DB))
        self.assertEqual([win.model.itemText(i) for i in range(1, win.model.count())],
                         sorted(DB))


class Xp231InTheApp(WindowCase):
    def setUp(self):
        super().setUp()
        self.queues = [spooler.Queue("EPSON XP-235 Series (Copiar 1)", "USB020", True)]
        self.attached = [unit("XP-231 235", pid="1130")]

    def test_it_is_in_the_selector_and_detected_from_its_windows_name(self):
        win = self.open_window()
        self.assertGreaterEqual(win.model.findData("XP-231"), 1)
        self.assertEqual(win.model_name, "XP-231")
        self.assertEqual(self.reads, ["XP-231"], "the app asks for the user-facing name")
        self.assertEqual(win.model.itemText(0), "Automático · XP-231")
        self.assertEqual(win.points["main_waste"][1], round(39.9 * 100))
        self.assertTrue(win.btn_perm.isEnabled())
        self.assertEqual([q.name for q in win.queues], ["EPSON XP-235 Series (Copiar 1)"],
                         "a queue under a sibling name still belongs to this printer")

    def test_it_says_it_is_mapped_and_unverified(self):
        win = self.open_window()
        text = win.waste_note.text()
        self.assertIn("XP-231 no figura por nombre en el backend", text)
        self.assertIn("XP-432", text)
        self.assertIn("No está verificado", text)
        self.assertIn("XP-432", win._mapped_note())

    def test_the_family_names_all_match_the_printer_description(self):
        win = self.open_window()
        for declared, expected in (("EPSON XP-231 235 Series", True), ("EPSON XP-235 Series", True),
                                   ("EPSON XP-230 Series", True), ("EPSON L3150 Series", False),
                                   ("EPSON XP-345 Series", False)):
            win.info = info_for(declared)
            self.assertEqual(win._model_matches(), expected, declared)

    def test_cleaning_stays_blocked_outside_the_l3150_family(self):
        win = self.open_window()
        self.assertFalse(win._clean_ok())
        self.assertFalse(win.btn_clean.isEnabled())
        self.assertIn("solo está verificada en la familia L3150", win.btn_clean.toolTip())
        self.assertIn("XP-231", win.btn_clean.toolTip())
        self.assertIn("la limpieza está desactivada", win.clean_note.text())

    def test_a_printer_that_is_not_an_xp231_blocks_the_permanent_reset(self):
        win = self.open_window()
        self.choose(win, "XP-231")
        self.declares = "EPSON L3150 Series"
        self.refresh(win)
        win.reset("perm")
        self.assertTrue(self.warnings, "the model mismatch must be reported")
        be.reset.assert_not_called()

    def test_other_models_have_no_mapped_note(self):
        self.attached = [unit("L3150")]
        self.queues = []
        win = self.open_window()
        self.assertEqual(win._mapped_note(), "")
        self.assertNotIn("no figura por nombre", win.waste_note.text())


class RealXp230(WindowCase):
    """The printer of this workshop: Windows calls it "EPSON XP-230 Series" (USB 04B8:1102),
    its queue sits on USB017 under a generic port description, and it reports status Error."""

    def setUp(self):
        super().setUp()
        self.attached = [pnp.UsbPrinter("6&29ba8cf&0&0001",
                                        ("EPSON XP-230 Series", "USB2.0 Printer",
                                         "EPSON XP-230 Series"), "1102", ("USB017",))]
        self.queues = [spooler.Queue("EPSON XP-230 Series", "USB017", True),
                       spooler.Queue("EPSON L3150 Series (Copiar 3)", "USB016", False),
                       spooler.Queue("EPSON L3150 Series", "USB006", False)]
        self.in_error = True
        self.no_serial = True       # the XP-432 record the XP-230 uses has no serial cells

    def test_it_is_detected_and_its_own_queue_is_the_connected_one(self):
        win = self.open_window()
        self.assertEqual(win.model_name, "XP-230")
        self.assertEqual(win.model.itemText(0), "Automático · XP-230")
        self.assertTrue(win._model_matches())
        self.assertEqual(win.title.text(), "EPSON XP-230 Series")
        self.assertEqual(win.print_queue.currentData().name, "EPSON XP-230 Series")
        self.assertIn("· conectada", win.print_queue.currentText())
        self.assertEqual([q.name for q in win.queues], ["EPSON XP-230 Series"])
        self.assertEqual(win.subtitle.text(), "Serie --", "the XP-432 record has no serial cells")

    def test_no_test_page_is_queued_for_a_printer_in_error(self):
        """It would sit in the Windows queue (as it did on the real XP-230) while the window
        waits for it."""
        win = self.open_window()
        with mock.patch.object(app.testpage, "print_pdf") as printed:
            win.print_test_page()
        printed.assert_not_called()
        self.assertIn("no está lista (Error)", self.warnings[-1])
        self.assertIn("atascado", self.warnings[-1])
        self.assertFalse(win.busy)

    def test_the_wait_says_why_when_windows_reports_a_problem(self):
        win = self.open_window()
        scheduled, saved = [], app.QTimer.singleShot
        app.QTimer.singleShot = staticmethod(lambda ms, fn: scheduled.append(ms))  # no real timers
        try:
            with mock.patch.object(spooler, "queue_state",
                                   return_value=(1, "impresora en error · trabajo con error")):
                win._spool_deadline = time.time() + 300
                win._check_spool("EPSON XP-230 Series")
                text = win.wait_label.text()
                self.assertIn("impresora en error · trabajo con error", text)
                self.assertIn("no está imprimiendo", text)
                self.assertRegex(text, r"espera \d:\d\d más")
                self.assertEqual(scheduled, [3000], "keeps watching the queue")
                scheduled.clear()
                win._spool_deadline = time.time() - 1        # the 5 minutes are over
                win._check_spool("EPSON XP-230 Series")
                self.assertEqual(scheduled, [12_000], "then it reads the printer again")
                self.assertIn("se deja de esperar", win.log.toPlainText())
            scheduled.clear()
            with mock.patch.object(spooler, "queue_state", return_value=(1, "")):
                win._spool_deadline = time.time() + 300
                win._check_spool("EPSON XP-230 Series")
                self.assertIn("Imprimiendo la página de prueba", win.wait_label.text())
                self.assertEqual(scheduled, [3000])
            scheduled.clear()
            with mock.patch.object(spooler, "queue_state", return_value=(0, "")):
                win._check_spool("EPSON XP-230 Series")      # queue empty: paper still ejecting
                self.assertEqual(scheduled, [12_000])
            with mock.patch.object(spooler, "queue_state", side_effect=OSError("spooler down")):
                scheduled.clear()
                win._check_spool("EPSON XP-230 Series")
                self.assertEqual(scheduled, [12_000], "an unreachable spooler is a fixed wait")
        finally:
            app.QTimer.singleShot = saved

    def test_a_paper_problem_during_a_job_shows_as_an_error(self):
        win = self.open_window()
        win.activity = ("printing", "Página de prueba MAG")
        scheduled, saved = [], app.QTimer.singleShot
        app.QTimer.singleShot = staticmethod(lambda ms, fn: scheduled.append(ms))
        try:
            with mock.patch.object(spooler, "queue_state",
                                   return_value=(1, "impresora sin papel · trabajo sin papel")):
                win._spool_deadline = time.time() + 300
                win._check_spool("EPSON L3250 Series")
                win._check_spool("EPSON L3250 Series")   # still there: reported once
            self.assertEqual(win.activity[0], "error")
            self.assertIn("Error: Sin papel o papel trabado", win.chip.text())
            self.assertEqual(win.log.toPlainText().count("ERROR durante"), 1)
            self.assertIsNotNone(win._spool_box)
            with mock.patch.object(spooler, "cancel_jobs", return_value=1) as cancel:
                next(b for b in win._spool_box.buttons()
                     if b.text() == "Cancelar el trabajo").click()
            cancel.assert_called_once()
            self.assertIn("Trabajo cancelado", win.log.toPlainText())
            with mock.patch.object(spooler, "queue_state", return_value=(1, "")):
                win._check_spool("EPSON L3250 Series")   # paper loaded: printing again
            self.assertEqual(win.activity[0], "printing")
        finally:
            app.QTimer.singleShot = saved

    def test_the_test_page_goes_to_the_connected_queue_only(self):
        self.in_error = False
        win = self.open_window()
        with mock.patch.object(app.testpage, "print_pdf",
                               side_effect=RuntimeError("stop: nothing is printed")) as printed:
            win.print_test_page()
        printed.assert_called_once_with(queue="EPSON XP-230 Series",
                                        path=app.testpage.version_path("D"))
        self.assertEqual(self.warnings, [])
        # the chosen version is printed, and remembered
        win.page_version.setCurrentIndex(win.page_version.findData("O"))
        with mock.patch.object(app.testpage, "print_pdf",
                               side_effect=RuntimeError("stop: nothing is printed")) as printed:
            win.print_test_page()
        printed.assert_called_once_with(queue="EPSON XP-230 Series", path=app.testpage.PDF)
        self.assertEqual(app.prefs.load().get("testpage_version"), "O")
        # a stale queue is refused, with the explanation
        win.print_queue.addItem("EPSON L3150 Series (Copiar 3)  (USB016)", self.queues[1])
        win.print_queue.setCurrentIndex(win.print_queue.count() - 1)
        with mock.patch.object(app.testpage, "print_pdf") as printed:
            win.print_test_page()
        printed.assert_not_called()
        self.assertIn("Elige la cola marcada como «conectada»", self.warnings[-1])

    def test_a_printer_in_error_gets_nothing_sent(self):
        win = self.open_window()
        self.assertTrue(win.chip.text().startswith("Error"),
                        "not 'Lista': the printer is in error")
        self.assertFalse(win.banner.isHidden(), "the error is explained under the ribbon")
        with mock.patch.object(spooler, "send_direct") as sent:
            win.maintenance("Test de inyectores", lambda: b"data", "check", False)
            self.assertTrue(pump(self.qapp, lambda: not win.busy))
        sent.assert_not_called()
        self.assertIn("Error al enviar: La impresora no está lista: Error", win.log.toPlainText())
        self.assertEqual(len(self.reads), 2, "the status was read fresh before sending")

    def test_cleaning_stays_blocked_on_the_real_printer(self):
        win = self.open_window()
        self.assertFalse(win.btn_clean.isEnabled())
        self.assertIn("XP-230", win.btn_clean.toolTip())
        be.reset.assert_not_called()


class QueueState(unittest.TestCase):
    """What Windows says about a queue: spooler reads only."""

    def state(self, printer_status, job_statuses):
        calls = []
        with mock.patch.object(spooler.win32print, "OpenPrinter", return_value="handle"), \
                mock.patch.object(spooler.win32print, "ClosePrinter",
                                  side_effect=lambda h: calls.append(h)), \
                mock.patch.object(spooler.win32print, "GetPrinter",
                                  return_value={"Status": printer_status}), \
                mock.patch.object(spooler.win32print, "EnumJobs",
                                  return_value=[{"Status": s} for s in job_statuses]):
            result = spooler.queue_state("EPSON XP-230 Series")
            self.assertEqual(calls, ["handle"], "the queue handle is always closed")
            self.assertEqual(spooler.pending_jobs("EPSON XP-230 Series"), result[0])
        return result

    def test_the_stuck_job_of_the_real_xp230(self):
        # printer status 0x2 (error); job 0x2012 = error + printing + retained
        self.assertEqual(self.state(0x2, [0x2012]), (1, "impresora en error · trabajo con error"))

    def test_a_healthy_queue_has_no_problem(self):
        self.assertEqual(self.state(0, [0x10]), (1, ""))      # a job that is printing
        self.assertEqual(self.state(0x400, [0x10]), (1, ""))  # printer busy printing
        self.assertEqual(self.state(0, []), (0, ""))

    def test_other_problems_are_named(self):
        self.assertEqual(self.state(0x80, []), (0, "impresora sin conexión"))
        self.assertEqual(self.state(0x10, [0x1]), (1, "impresora sin papel · trabajo en pausa"))
        self.assertEqual(self.state(0, [0x41]), (1, "trabajo en pausa · trabajo sin papel"))
        self.assertEqual(self.state(0x100000, [0x400]),
                         (1, "impresora requiere intervención · trabajo requiere intervención"))

    def test_the_handle_is_closed_when_the_spooler_fails(self):
        calls = []
        with mock.patch.object(spooler.win32print, "OpenPrinter", return_value="h"), \
                mock.patch.object(spooler.win32print, "ClosePrinter",
                                  side_effect=lambda h: calls.append(h)), \
                mock.patch.object(spooler.win32print, "GetPrinter", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                spooler.queue_state("x")
        self.assertEqual(calls, ["h"])


class QueuesOfThePc(unittest.TestCase):
    """Which Windows queue is the connected printer's: by port of the present device."""

    PRINTERS = [{"pPrinterName": "EPSON XP-230 Series", "pPortName": "USB017"},
                {"pPrinterName": "EPSON L3150 Series (Copiar 3)", "pPortName": "USB016"},
                {"pPrinterName": "EPSON L3150 Series", "pPortName": "USB006"},
                {"pPrinterName": "HP DeskJet 2700", "pPortName": "USB061"}]

    def queues(self, attached, hint=""):
        with mock.patch.object(spooler, "usb_printers", return_value=attached), \
                mock.patch.object(spooler.win32print, "EnumPrinters", return_value=self.PRINTERS), \
                mock.patch.object(spooler.win32print, "EnumPorts",
                                  side_effect=AssertionError("port descriptions decide nothing")):
            return spooler.epson_queues(hint)

    def test_only_the_queue_on_the_live_port_is_connected(self):
        live = pnp.UsbPrinter("x", ("EPSON XP-230 Series",), "1102", ("USB017",))
        found = self.queues([live])
        self.assertEqual([(q.name, q.active) for q in found],
                         [("EPSON XP-230 Series", True),
                          ("EPSON L3150 Series", False),
                          ("EPSON L3150 Series (Copiar 3)", False)])
        self.assertEqual([q.name for q in self.queues([live], "XP-230")], ["EPSON XP-230 Series"])

    def test_nothing_attached_means_no_queue_is_connected(self):
        self.assertFalse(any(q.active for q in self.queues([])))
        # a printer whose driver exposes no port is not matched by luck
        self.assertFalse(any(q.active for q in self.queues([pnp.UsbPrinter("x", (), "1102")])))

    def test_every_attached_unit_counts(self):
        two = [pnp.UsbPrinter("a", (), "1", ("USB017",)), pnp.UsbPrinter("b", (), "2", ("USB006",))]
        self.assertEqual(sorted(q.name for q in self.queues(two) if q.active),
                         ["EPSON L3150 Series", "EPSON XP-230 Series"])


class Xp231Data(unittest.TestCase):
    def test_it_is_in_the_database_next_to_the_backend_models(self):
        self.assertIn("XP-231", DB)
        native = [m for m, entry in DB.items() if "backend_model" not in entry]
        self.assertGreaterEqual(len(native), 117)
        self.assertEqual(sorted(set(DB) - set(native)),
                         sorted(m for m in mapped_models.MAPPED if m in DB))
        self.assertIn("XP-235", native)

    def test_it_shares_the_cells_and_keys_of_xp432(self):
        mapped, base = DB["XP-231"], DB["XP-432"]
        for field in ("pads", "reset_cells", "read_key", "write_key"):
            self.assertEqual(mapped[field], base[field], field)
        self.assertEqual(mapped["backend_model"], "XP-432")
        self.assertEqual(mapped["read_key"], [133, 5], "0x0585")
        self.assertEqual(mapped["reset_cells"], [24, 25, 26, 27, 28, 29, 30, 34, 46, 47, 49])
        self.assertEqual(mapped["pads"]["main_waste"]["oids"], [24, 25, 30])
        self.assertEqual(mapped["pads"]["borderless_waste"]["oids"], [26, 27, 34])
        for sibling in ("XP-230", "XP-235", "XP-432", "XP-433", "XP-435"):
            self.assertIn(sibling, mapped["identifies_as"])
        self.assertNotIn("XP-231", mapped["identifies_as"])
        self.assertNotIn("backend_model", base, "backend models stay untouched")

    def test_the_backend_is_run_with_the_name_it_knows(self):
        done = SimpleNamespace(stdout="", stderr="")
        with mock.patch.object(be.subprocess, "run", return_value=done) as run:
            be.run("XP-231", ["-i"])
            be.run("L3150", ["-i"])
        mapped, plain = (call.args[0] for call in run.call_args_list)
        self.assertEqual(mapped[mapped.index("-m") + 1], "XP-432")
        self.assertEqual(plain[plain.index("-m") + 1], "L3150")
        self.assertIn("--usb", mapped)

    def test_helpers_for_mapped_and_plain_models(self):
        self.assertEqual(be.backend_model("XP-231"), "XP-432")
        self.assertEqual(be.backend_model("XP-230"), "XP-432")
        self.assertEqual(be.backend_model("L3150"), "L3150")
        self.assertTrue(be.is_mapped("XP-231"))
        self.assertFalse(be.is_mapped("XP-235"))
        self.assertEqual(be.family("L3151"), ["L3151"], "plain models keep exact matching")
        self.assertEqual(be.family("XP-231")[0], "XP-231")
        self.assertTrue(be.can_reset("XP-231"))
        self.assertEqual(be.cells_for("XP-231"), be.cells_for("XP-432"))
        self.assertEqual(be.main_pad_cells("XP-231"), [24, 25, 30])

    def test_cleaning_commands_are_refused_before_touching_usb(self):
        def no_usb():
            raise AssertionError("a USB session was opened")

        with mock.patch.object(cleaning, "TRANSPORT_FACTORY", no_usb):
            for model in ("XP-231", "XP-230", "XP-432", "L4150"):
                self.assertNotIn(model, cleaning.SUPPORTED_MODELS)
                with self.assertRaises(cleaning.CleaningError):
                    cleaning.run(model, "cl1")

    def test_l3250_cleaning_is_the_l3150_command_with_its_own_read_key(self):
        self.assertIn("L3250", cleaning.SUPPORTED_MODELS)
        self.assertNotIn("L3250", cleaning.VERIFIED_MODELS, "matched, not captured")
        read_key, _write_key = be.keys("L3250")
        self.assertEqual(cleaning.cleaning_command(read_key, 0x01).hex(" "),
                         "1b 7c 00 06 00 4a 36 84 7b 42 01")

    def test_l3250_shares_the_cells_and_keys_of_et2812(self):
        for model in ("L3250", "L3258"):
            mapped, base = DB[model], DB["ET-2812"]
            for field in ("pads", "reset_cells", "read_key", "write_key"):
                self.assertEqual(mapped[field], base[field], field)
            self.assertEqual(mapped["backend_model"], "ET-2812")
            self.assertEqual(mapped["read_key"], [74, 54], "0x364A")
            self.assertEqual(mapped["reset_cells"],
                             [28, 47, 48, 49, 50, 51, 52, 53, 54, 55, 252, 253, 254, 255])
            self.assertEqual(mapped["pads"]["main_waste"]["oids"], [48, 49, 47])
            self.assertEqual(mapped["pads"]["borderless_waste"]["oids"], [50, 51, 47])
            self.assertEqual(mapped["pads"]["third_waste"]["oids"], [252, 253, 254])
            self.assertIn("ET-2814", mapped["identifies_as"])
        self.assertEqual(be.backend_model("L3250"), "ET-2812")
        self.assertEqual(detect.detect(DB, [unit("L3250", pid="118A")]).model, "L3250")

    def test_mapping_rules(self):
        base = {"read_key": [1, 2], "pads": {}, "reset_cells": [], "write_key": None}
        db = {"XP-432": dict(base), "XP-435": dict(base)}
        added = mapped_models.apply(db, {"XP-231": "XP-432", "XP-230": "XP-432"})
        self.assertEqual(added, ["XP-230", "XP-231"])
        self.assertEqual(db["XP-231"]["identifies_as"], ["XP-230", "XP-432", "XP-435"])
        # the backend gaining the model itself wins over the mapping
        native = {"XP-432": dict(base), "XP-231": {"read_key": [9, 9]}}
        self.assertEqual(mapped_models.apply(native, {"XP-231": "XP-432"}), [])
        self.assertEqual(native["XP-231"], {"read_key": [9, 9]})
        # no base, nothing to copy
        self.assertEqual(mapped_models.apply({}, {"XP-231": "XP-432"}), [])


class Naming(unittest.TestCase):
    def test_windows_names_resolve_to_backend_models(self):
        cases = {
            "EPSON L3150 Series": "L3150",
            "L3150 Series": "L3150",
            "EPSON L395 Series": "L395",
            "EPSON XP-231 235 Series": "XP-231",
            "EPSON XP-235 Series": "XP-235",
            "EPSON XP-230 Series": "XP-230",
            "EPSON XP-205 207 Series": "XP-205",
            "EPSON ET-2810 Series": "ET-2810",
            "EPSON Stylus Photo PX730WD Series": "Stylus Photo PX730WD",
            "EPSON L315 Series": "",          # a prefix of a model is not that model
            "EPSON L31500 Series": "",
            "EPSON L3250 Series": "L3250",    # mapped onto ET-2812
            "EPSON L3210 Series": "",         # not in the backend
            "USB2.0 Printer": "",
            "": "",
        }
        for name, expected in cases.items():
            self.assertEqual(detect.resolve([name], DB), expected, name)

    def test_the_first_name_that_resolves_wins(self):
        self.assertEqual(detect.resolve(["USB2.0 Printer", "L3150 Series"], DB), "L3150")
        self.assertEqual(detect.resolve(["EPSON L395 Series", "L3150 Series"], DB), "L395")
        self.assertEqual(detect.resolve([], DB), "")

    def test_candidates_of_a_family_name(self):
        self.assertEqual(detect.candidates("EPSON XP-231 235 Series"),
                         ["XP-231 235", "XP-231", "XP-235"])
        self.assertEqual(detect.candidates("EPSON L3150 Series"), ["L3150"])

    def test_detection_states(self):
        self.assertEqual(detect.detect(DB, []).status, detect.NONE)
        self.assertEqual(detect.detect(DB, [unit("L3150")]).model, "L3150")
        many = detect.detect(DB, [unit("L3150", "a"), unit("L395", "b")])
        self.assertEqual((many.status, many.model), (detect.SEVERAL, ""))
        odd = detect.detect(DB, [unit("L3210")])
        self.assertEqual((odd.status, odd.model), (detect.UNKNOWN, ""))
        self.assertIn("EPSON L3210 Series", odd.message)


class WindowsRegistryOnly(unittest.TestCase):
    """The detection must never talk to a printer."""

    def test_listing_the_printers_is_a_registry_read_that_never_raises(self):
        found = pnp.epson_usb_printers()
        self.assertIsInstance(found, list)
        self.assertTrue(all(isinstance(p, pnp.UsbPrinter) and p.instance for p in found))
        self.assertEqual(pnp.epson_usb_printers("00000000-0000-0000-0000-000000000000"), [])

    def test_the_detection_code_cannot_open_a_device(self):
        for module in ("pnp.py", "detect.py"):
            source = (ROOT / module).read_text(encoding="utf-8")
            for forbidden in ("CreateFile", "open_transport", "WriteFile", "ReadFile",
                              "subprocess", "win32print", "backend_cli", "import epson_usb",
                              "from epson_usb"):
                self.assertNotIn(forbidden, source, f"{module} must not use {forbidden}")

    def test_display_name(self):
        self.assertEqual(unit("L3150").name, "EPSON L3150 Series")
        self.assertEqual(pnp.UsbPrinter("x", ("USB2.0 Printer", "L3150 Series")).name,
                         "L3150 Series")
        self.assertEqual(pnp.UsbPrinter("x", (), "1143").name, "Epson USB (PID 1143)")


if __name__ == "__main__":
    unittest.main()
