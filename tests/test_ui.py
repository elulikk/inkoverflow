"""End-to-end UI test on a fake printer (no hardware, nothing written anywhere real).

Dialogs are answered automatically; history, backups and reports go to a temp folder;
the backend's real reset command is replaced by a recorder.
"""
import csv
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from epson_usb.backends.mock import MockTransport  # noqa: E402
from PySide6.QtGui import QCloseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox  # noqa: E402

import app  # noqa: E402
import backend_cli as be  # noqa: E402
import cleaning  # noqa: E402
import history  # noqa: E402
import pnp  # noqa: E402
import prefs  # noqa: E402
import report  # noqa: E402
import spooler  # noqa: E402
from fake_printer import FakeL3150  # noqa: E402
from widgets import QSS  # noqa: E402

SERIAL = "X5E9205615"
INFO = {
    "device_identification": {"Description": ["EPSON L3150 Series"], "FG": ["EPSON"],
                              "Commands": ["ESCPL2,BDC,D4"], "CID": ["EpsonRGB"],
                              "DDS": ["022500"], "ELG": ["1163"], "RID": ["30"]},
    "firmware_version": "VD02JA 02 Oct 2019", "serial_number": SERIAL,
    "printer_status": {"ready": True, "status": (4, "Idle (ready to print)"),
                       "maintenance_box_1": "not full (0)", "maintenance_box_2": "not full (0)"},
    "stats": {"First TI received time": "16 Mar 2020", "Total print page counter": 67,
              "Total print pass counter": 1271420, "Total scan counter": 676},
    "snmp_info": {"Power Off Timer": "@BDC PS\r\not:01FFFF;\x0c"},
}


def pump(qapp, condition, limit=60.0):
    end = time.time() + limit
    while time.time() < end and not condition():
        qapp.processEvents()
        time.sleep(0.02)
    for _ in range(10):
        qapp.processEvents()
    return condition()


class UiFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QApplication.instance() or QApplication([])
        cls.qapp.setStyleSheet(QSS)
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        cls.saved = {
            "data": history.DATA, "backup": app.BACKUP_DIR, "build": report.build,
            "info": be.read_info, "cells": be.read_cells, "reset": be.reset,
            "queues": spooler.epson_queues, "usb": spooler.usb_instances,
            "printers": spooler.usb_printers,
            "factory": cleaning.TRANSPORT_FACTORY, "startfile": os.startfile,
            "q_info": QMessageBox.information, "q_warn": QMessageBox.warning,
            "q_question": QMessageBox.question, "q_exec": QMessageBox.exec,
            "c_exec": app.ConfirmDialog.exec,
            "reports": report.REPORTS, "beep": QApplication.beep, "alert": QApplication.alert,
            "save_dialog": QFileDialog.getSaveFileName,
        }
        history.DATA = tmp / "data"
        app.BACKUP_DIR = tmp / "backups"
        report.REPORTS = tmp / "reports"
        cls.beeps, cls.csv_path = [], None
        QApplication.beep = staticmethod(lambda: cls.beeps.append(1))   # no real sound
        QApplication.alert = staticmethod(lambda *a: None)
        QFileDialog.getSaveFileName = staticmethod(
            lambda *a, **k: (cls.csv_path, "CSV (*.csv)"))
        original_build = report.build
        report.build = lambda data: original_build(data, tmp / "reports")

        cls.printer = FakeL3150(counter=5690)
        be.read_info = lambda model: INFO
        be.read_cells = lambda model, addrs: {a: cls.printer.config.eeprom.get(a, 0) for a in addrs}
        cls.resets = []

        def recorded_reset(model, mode):
            cls.resets.append(mode)
            return True, "Reset waste ink levels done."

        be.reset = recorded_reset
        spooler.epson_queues = lambda hint="": [spooler.Queue("EPSON L3150 Series (Copiar 3)",
                                                              "USB016", True)]
        spooler.usb_instances = lambda: ["6&f8b792&0&0001"]
        spooler.usb_printers = lambda: [pnp.UsbPrinter(
            "6&f8b792&0&0001", ("EPSON L3150 Series", "USB2.0 Printer", "L3150 Series"), "1143")]

        def new_transport():
            cls.printer.in_d4, cls.printer._inbuf = False, b""   # a fresh USB session
            transport = MockTransport(printer=cls.printer)
            transport.open()
            return transport

        cleaning.TRANSPORT_FACTORY = new_transport
        cls.opened = []
        os.startfile = lambda path: cls.opened.append(Path(path))
        QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
        QMessageBox.warning = staticmethod(lambda *a, **k: cls.warnings.append(a[2]) or QMessageBox.Ok)
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
        QMessageBox.exec = lambda self: QMessageBox.Yes
        app.ConfirmDialog.exec = lambda self: QDialog.Accepted
        cls.warnings = []

        cls.win = app.MainWindow()
        cls.win.show()
        assert pump(cls.qapp, lambda: cls.win.info and not cls.win.busy, 90), "window never loaded"

    @classmethod
    def tearDownClass(cls):
        s = cls.saved
        cls.win.close()  # first: closing writes the preferences into the temp folder
        history.DATA, app.BACKUP_DIR, report.build = s["data"], s["backup"], s["build"]
        report.REPORTS = s["reports"]
        QApplication.beep, QApplication.alert = s["beep"], s["alert"]
        QFileDialog.getSaveFileName = s["save_dialog"]
        be.read_info, be.read_cells, be.reset = s["info"], s["cells"], s["reset"]
        spooler.epson_queues, spooler.usb_instances = s["queues"], s["usb"]
        spooler.usb_printers = s["printers"]
        cleaning.TRANSPORT_FACTORY, os.startfile = s["factory"], s["startfile"]
        QMessageBox.information, QMessageBox.warning = s["q_info"], s["q_warn"]
        QMessageBox.question, QMessageBox.exec = s["q_question"], s["q_exec"]
        app.ConfirmDialog.exec = s["c_exec"]
        cls.tmp.cleanup()

    def settle(self):
        """Wait until nothing is running (the refresh after an operation included)."""
        pump(self.qapp, lambda: False, 0.3)
        self.assertTrue(pump(self.qapp, lambda: not self.win.busy, 90))
        pump(self.qapp, lambda: False, 0.3)
        self.assertTrue(pump(self.qapp, lambda: not self.win.busy, 90))

    def counter(self):
        e = self.printer.config.eeprom
        return e[48] + (e[49] << 8) + (e[47] << 16)

    # the tests share one window and run in alphabetical order on purpose
    def test_1_loads_and_detects_the_model(self):
        w = self.win
        self.assertEqual(w.model_name, "L3150")
        self.assertEqual(w.points["main_waste"], (5690, 6346))
        self.assertEqual(list(w.gauges), ["main_waste", "borderless_waste"])
        self.assertTrue(w.btn_clean.isEnabled())
        self.assertTrue(all(b.isEnabled() for b in w.reset_buttons))
        self.assertEqual(w.clean_mode.count(), 4)
        self.assertFalse(w.restore_check.isChecked(), "the counter-hiding box must start off")

    def test_2_cleaning_lets_the_counter_rise_and_reports_it(self):
        w = self.win
        w.clean_mode.setCurrentIndex(0)
        w.clean_heads()
        self.settle()
        self.assertEqual(self.counter(), 5690 + 28)
        self.assertEqual(w.points["main_waste"][0], 5718)
        self.assertEqual(history.hidden_points(SERIAL), 0)
        last = history.load()[0]
        self.assertEqual(last["kind"], "limpieza")
        self.assertIn("+28", last["detail"])
        self.assertEqual(len(self.printer.data_packets), 1)
        self.assertTrue(self.beeps, "the user must be called back when the cleaning ends")

    def test_3_restoring_the_counter_is_tallied_and_shown(self):
        w = self.win
        w.clean_mode.setCurrentIndex(1)       # CL2: +60 points on the fake
        w.restore_check.setChecked(True)
        w.clean_heads()
        self.settle()
        self.assertEqual(self.counter(), 5718, "counter rewound to the value before")
        self.assertEqual(history.hidden_points(SERIAL), 60)
        self.assertEqual(w.points["main_waste"][0], 5718)
        label, real, maximum = w._worst_pad()
        self.assertEqual((real, maximum), (5778, 6346))
        self.assertIn("real", w.gauges["main_waste"].detail)
        self.assertIn("sin contar", history.load()[0]["detail"])
        w.restore_check.setChecked(False)

    def test_4_pdf_report_is_written_and_opened(self):
        self.win.make_report()
        self.assertTrue(self.opened, "report was not opened")
        pdf = self.opened[-1]
        self.assertTrue(pdf.exists() and pdf.stat().st_size > 5000)
        self.assertEqual(pdf.read_bytes()[:4], b"%PDF")

    def test_5_history_page_lists_the_operations(self):
        w = self.win
        w._render_history()
        self.assertEqual(w.history_table.rowCount(), len(history.load(200, serial=SERIAL)))
        kinds = {w.history_table.item(r, 1).text() for r in range(w.history_table.rowCount())}
        self.assertTrue({"limpieza", "informe"} <= kinds)

    def test_6_permanent_reset_backs_up_and_clears_the_tally(self):
        w = self.win
        self.assertEqual(history.hidden_points(SERIAL), 60)
        w.reset("perm")
        self.settle()
        self.assertEqual(self.resets, ["perm"])
        self.assertEqual(history.hidden_points(SERIAL), 0)
        backups = list((Path(self.tmp.name) / "backups").glob("L3150_*.json"))
        self.assertEqual(len(backups), 1)

    def test_7_wrong_model_blocks_the_permanent_reset(self):
        w = self.win
        self.resets.clear()
        w.model.blockSignals(True)
        w.model.setCurrentText("L4150")
        w.model.blockSignals(False)
        w.reset("perm")
        pump(self.qapp, lambda: False, 0.3)
        self.assertEqual(self.resets, [])
        self.assertTrue(self.warnings)
        self.assertFalse(w.btn_clean.isEnabled() and w._clean_ok())
        w.model.blockSignals(True)
        w.model.setCurrentText("L3150")
        w.model.blockSignals(False)
        w._set_busy(False)

    # -- quality of life ------------------------------------------------------
    def test_8_disabled_buttons_say_why(self):
        w = self.win
        w._set_busy(False)
        self.assertTrue(w.btn_nozzle.isEnabled())
        self.assertEqual(w.btn_nozzle.toolTip(), "")
        w.usb = []
        w._set_busy(False)
        self.assertFalse(w.btn_nozzle.isEnabled())
        self.assertIn("ninguna impresora Epson", w.btn_nozzle.toolTip())
        w.usb = ["a", "b"]
        w._set_busy(False)
        self.assertIn("2 impresoras", w.btn_clean.toolTip())
        self.assertTrue(w.btn_perm.isEnabled(), "the reset does not depend on the USB count")
        w.usb = ["a"]
        w.model.blockSignals(True)
        w.model.setCurrentText("L3151")       # verified family, but not this printer
        w.model.blockSignals(False)
        w._set_busy(False)
        self.assertFalse(w.btn_clean.isEnabled())
        self.assertIn("no coincide", w.btn_clean.toolTip())
        w.model.blockSignals(True)
        w.model.setCurrentText("L3150")
        w.model.blockSignals(False)
        w._set_busy(True)
        self.assertIn("en curso", w.btn_report.toolTip())
        w._set_busy(False)
        self.assertEqual(w.btn_report.toolTip(), "")
        self.assertTrue(w.btn_clean.isEnabled())

    def test_9_no_printer_shows_a_banner_and_keeps_the_history(self):
        w = self.win
        working = be.read_info

        def unplugged(model):
            raise be.BackendError("EEPROM no disponible")

        be.read_info = unplugged
        try:
            w.refresh()
            self.settle()
        finally:
            be.read_info = working
        self.assertFalse(w.info)
        self.assertFalse(w.banner.isHidden())
        self.assertIn("Actualizar", w.banner.text())
        self.assertEqual(w.usage["Páginas impresas"].text(), "--", "no stale numbers")
        self.assertEqual(w.details.rowCount(), 0)
        self.assertEqual(w.windowTitle(), app.APP_NAME)
        self.assertFalse(w.btn_nozzle.isEnabled())
        self.assertIn("conéctala", w.btn_nozzle.toolTip())
        self.assertIn("Sin lectura", w.waste_note.text())
        # past work stays readable without the printer
        self.assertEqual(w._history_serial(), "")
        self.assertGreater(w.history_table.rowCount(), 0)
        w.refresh()
        self.settle()
        self.assertTrue(w.info)
        self.assertTrue(w.banner.isHidden())
        self.assertIn(SERIAL, w.windowTitle())

    def test_a_history_printer_list_and_opening_files(self):
        w = self.win
        w.backup()
        self.settle()
        self.assertEqual(w._history_serial(), SERIAL, "the connected printer by default")
        self.assertTrue(w.history_table.isColumnHidden(3))
        w.history_who.setCurrentIndex(0)
        w._history_picked(0)
        self.assertEqual(w._history_serial(), "")
        self.assertFalse(w.history_table.isColumnHidden(3))
        w.refresh()
        self.settle()
        self.assertEqual(w._history_serial(), "", "a refresh must not undo the user's choice")

        def row_of(kind):
            return next(r for r in range(w.history_table.rowCount())
                        if w.history_table.item(r, 1).text() == kind)

        w._history_open(row_of("informe"), 0)
        self.assertEqual(self.opened[-1].parent, report.REPORTS)
        self.assertEqual(self.opened[-1].suffix, ".pdf")
        w._history_open(row_of("copia"), 0)
        self.assertEqual(self.opened[-1].parent, app.BACKUP_DIR)
        before = len(self.opened)
        self.opened[-1].unlink()
        w._history_open(row_of("copia"), 0)
        self.assertEqual(len(self.opened), before, "a deleted file is not opened")
        self.assertIn("ya no existe", w.log.toPlainText())
        w._history_open(row_of("limpieza"), 0)   # nothing to open: no error
        w._history_pinned = False
        w._render_history()

    def test_b_history_and_eeprom_export_to_csv(self):
        w = self.win
        w._history_pinned = False
        w._render_history()
        type(self).csv_path = str(Path(self.tmp.name) / "historial.csv")
        w.export_history()
        with open(self.csv_path, newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0], ["fecha", "operacion", "detalle", "modelo", "serie"])
        self.assertEqual(len(rows) - 1, len(history.load(10 ** 9, serial=SERIAL)))
        self.assertEqual(rows[1][4], SERIAL)
        w.dump_cells = {0: 0x3A, 1: None}
        type(self).csv_path = str(Path(self.tmp.name) / "eeprom.csv")
        w.export_dump()
        with open(self.csv_path, newline="", encoding="utf-8") as fh:
            self.assertEqual(list(csv.reader(fh))[1:], [["0", "3A", "58"], ["1", "", ""]])

    def test_c_copy_summary_for_the_customer(self):
        self.win.copy_summary()
        text = QApplication.clipboard().text()
        self.assertIn(SERIAL, text)
        self.assertIn("Almohadilla principal: 5718 / 6346 puntos", text)
        self.assertIn("MAG Tecnología", text)

    def test_d_closing_is_refused_while_a_cleaning_runs(self):
        w = self.win
        self.warnings.clear()
        w._clean_timer.start(1000)
        try:
            self.assertFalse(w.close())
        finally:
            w._clean_timer.stop()
        self.assertTrue(w.isVisible())
        self.assertIn("no se puede cancelar", self.warnings[-1])

    def test_e_shortcuts_follow_the_same_rules_as_the_buttons(self):
        w = self.win
        for index, shortcut in enumerate(w._shortcuts[2:]):   # Ctrl+1 ... Ctrl+5
            shortcut.activated.emit()
            self.assertEqual(w.stack.currentIndex(), index)
        w.nav.button(0).click()
        calls = []
        w.refresh = lambda *a, **k: calls.append(1)
        try:
            w._shortcuts[0].activated.emit()     # F5, idle
            w._set_busy(True)
            w._shortcuts[1].activated.emit()     # Ctrl+R, busy: no new USB session
            w._set_busy(False)
        finally:
            del w.refresh
        self.assertEqual(calls, [1])

    def test_f_cleaning_progress_bar_and_preferences(self):
        w = self.win
        w._show_wait("", determinate=True)
        w._clean_state = {"text": "CL1 (débil): estado 7", "elapsed": 95.0, "typical": 190}
        w._tick_clean()
        self.assertEqual((w.wait_bar.maximum(), w.wait_bar.value()), (100, 50))
        self.assertIn("quedan unos 1:35", w.wait_label.text())
        w.wait_bar.hide()
        w.wait_label.setText("")
        prefs.save(page=3, eeprom_start=16, eeprom_end=47)
        w._restore_prefs()
        self.assertEqual((w.stack.currentIndex(), w.sp_start.value(), w.sp_end.value()),
                         (3, 16, 47))
        w.nav.button(2).click()
        w.closeEvent(QCloseEvent())
        saved = prefs.load()
        self.assertEqual(saved["page"], 2)
        self.assertIsInstance(saved["geometry"], str)
        self.assertNotIn("clean_mode", saved)
        self.assertNotIn("restore", " ".join(saved))
        w.nav.button(0).click()

    def test_g_brand_is_in_the_window(self):
        w = self.win
        self.assertFalse(w.windowIcon().isNull())
        self.assertIn(32, [s.width() for s in w.windowIcon().availableSizes()])
        self.assertIsNotNone(w.logo.pixmap())
        self.assertFalse(w.logo.pixmap().isNull())
        self.assertIn(app.APP_NAME, w.logo.toolTip())
        app.set_taskbar_identity()                 # must never raise, on any platform

    def test_h_3d_view_gets_the_data_and_resets_through_the_same_gate(self):
        w = self.win
        self.settle()
        data = w.bridge3d.data
        self.assertTrue(data["connected"])
        self.assertEqual(data["model"], "L3150")
        self.assertEqual(data["serial"], SERIAL)
        self.assertEqual([p["label"] for p in data["pads"]],
                         [be.PAD_LABELS["main_waste"], be.PAD_LABELS["borderless_waste"]])
        self.assertAlmostEqual(data["worst"], w._worst_pct())
        self.assertEqual(len(data["inks"]), 4)
        self.assertTrue(data["canReset"])
        self.assertEqual(w.stack.widget(0), w.page3d)    # the 3D view is the first page
        before = list(self.resets)
        w._set_busy(True)
        w.bridge3d.reset("dry")                          # busy: ignored, as the buttons are
        self.assertFalse(w.bridge3d.data["canReset"])
        w._set_busy(False)
        w.bridge3d.reset("dry")
        self.settle()
        self.assertEqual(self.resets, before + ["dry"])

    def test_i_3d_actions_activity_and_preferences(self):
        w = self.win
        self.settle()
        import printer3d
        data = w.bridge3d.data
        self.assertEqual(set(data["actions"]), set(printer3d.ACTIONS))
        self.assertEqual(data["actions"]["clean"] == "", w.btn_clean.isEnabled())
        self.assertEqual(data["actions"]["feed"] == "", w.btn_feed.isEnabled())
        self.assertIn(w.btn_feed, w.maint_buttons)       # same gate as the nozzle check
        self.assertTrue(data["pageName"])
        w._set_busy(True)                                # busy: every 3D action is off
        self.assertTrue(all(w.bridge3d.data["actions"].values()))
        w._set_busy(False)
        clicked = []
        w.btn_nozzle.clicked.disconnect()
        w.btn_nozzle.clicked.connect(lambda: clicked.append("nozzle"))
        w.btn_nozzle.setEnabled(True)
        w.bridge3d.action("nozzle")                      # through the ribbon button
        w.bridge3d.action("format_c")                    # unknown: ignored
        self.assertEqual(clicked, [])                    # not inside the QML click...
        self.settle()
        self.assertEqual(clicked, ["nozzle"])            # ...but right after it
        w._set_activity("printing", "Test")
        self.assertEqual(w.bridge3d.data["activity"], "printing")
        w._set_activity()
        self.assertEqual(w.bridge3d.data["activity"], "")
        w.bridge3d.pinned = True                         # remembered
        self.assertIs(prefs.load()["view3d_pinned"], True)
        w.bridge3d.pinned = False
        low = []
        w.bridge3d.lowFps.connect(low.append)
        w.bridge3d.reportLowFps(12.0)
        self.assertEqual(low, [12.0])
        w.page3d.disable_3d(12.0)                        # off, and stays off
        self.assertEqual(prefs.load()["view3d_off"], 12.0)
        self.assertFalse(w.page3d.view)
        w.page3d.enable_3d(guard=False)
        self.assertIsNone(prefs.load()["view3d_off"])
        self.assertFalse(w.bridge3d.fpsGuard)
        w.bridge3d.reportLowFps(5.0)                     # guard off: no shutdown
        self.assertEqual(low, [12.0])
        w.bridge3d.fpsGuard = True
        w.bridge3d.fps30 = True                          # 30 FPS cap: remembered
        self.assertIs(prefs.load()["view3d_fps30"], True)
        w.bridge3d.fps30 = False
        self.assertIs(prefs.load()["view3d_fps30"], False)
        w.page3d.disable_3d(12.0)                        # off for low FPS: 2D brings it back
        self.assertTrue(w.page3d.btn_2d.isVisibleTo(w.page3d))
        w.page3d.use_2d()
        self.assertTrue(w.bridge3d.mode2d)
        self.assertIs(prefs.load()["view3d_2d"], True)
        self.assertIsNone(prefs.load()["view3d_off"])
        w.bridge3d.reportLowFps(5.0)                     # 2D is never turned off
        self.assertEqual(low, [12.0])
        w.bridge3d.mode2d = False

    def test_j_diagnostic_pattern_print_scan_and_analyse(self):
        from unittest import mock

        import scanner
        from test_diagnostic import page, scan
        w = self.win
        self.settle()
        tmp = Path(self.tmp.name)
        # print: same gate as the MAG page, to the connected queue, stamped with the printer
        sent = []
        with mock.patch.object(app.diagnostic, "print_pattern",
                               side_effect=lambda **k: sent.append(k)), \
                mock.patch.object(spooler, "job_ids", return_value=set()), \
                mock.patch.object(app.QTimer, "singleShot"):  # no real wait for the queue
            w.print_diagnostic()
        self.assertEqual(sent[0]["queue"], "EPSON L3150 Series (Copiar 3)")
        self.assertIn(SERIAL, sent[0]["stamp"])
        self.assertTrue(w.busy)
        self.assertFalse(w.btn_diag_scan.isEnabled(), "nothing is scanned while printing")
        self.assertEqual(history.load()[0]["kind"], "prueba")
        w._maintenance_finished()
        self.settle()
        self.assertTrue(w.btn_diag_scan.isEnabled())

        # scan: the fake scanner returns a sheet with three clogged cyan nozzles
        def fake_scan(device_id, path, dpi=300):
            self.assertEqual((device_id, dpi), ("wia-1", 300))
            path.parent.mkdir(parents=True, exist_ok=True)
            scan(page(["cyan_clogged"])).save(str(path))
            return path

        shown = []
        saved_scans = app.SCANS_DIR
        app.SCANS_DIR = tmp / "escaneos"
        try:
            with mock.patch.object(scanner, "list_scanners", return_value=[
                    scanner.Scanner("wia-0", "HP LJ M176 Scan Driver"),
                    scanner.Scanner("wia-1", "EPSON L3150 Series")]), \
                    mock.patch.object(scanner, "scan", side_effect=fake_scan), \
                    mock.patch.object(app.DiagnosticDialog, "exec",
                                      lambda dialog: shown.append(dialog)):
                w.scan_diagnostic()
                self.assertTrue(pump(self.qapp, lambda: shown, 120), "no result was shown")
        finally:
            app.SCANS_DIR = saved_scans
        self.settle()
        event = history.load()[0]
        self.assertEqual(event["kind"], "diagnóstico")
        self.assertEqual(event["detail"], "Cian: inyectores tapados")
        self.assertTrue(w._history_file(event).is_file(), "the marked image is kept")
        self.assertIn("Cian: inyectores tapados", w.diag_note.text())
        self.assertTrue(Path(event["scan"]).is_file(), "the raw scan is kept for later")
        result = shown[0].result
        self.assertEqual(result.level, "bad")
        html = app.DiagnosticDialog.html(result)
        self.assertIn("Qué hacer", html)
        self.assertIn("Negro", html)  # the parts that are fine are listed too

        # analyse a saved file that is not the pattern: said plainly, nothing recorded
        blank = tmp / "foto.png"
        page().copy(0, 0, 900, 900).save(str(blank))
        count = len(history.load())
        with mock.patch.object(app.QFileDialog, "getOpenFileName",
                               return_value=(str(blank), "")):
            w.open_diagnostic()
            self.settle()
        self.assertIn("cuatro marcas", self.warnings[-1])
        self.assertEqual(len(history.load()), count)


if __name__ == "__main__":
    unittest.main()
