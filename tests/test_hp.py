"""HP support, with the HP Smart Tank 580 as the model, and no hardware.

The printer is tests/fake_hp.py: a local web server that answers IPP and LEDM like the
printer's network side, plus the USB unit as Windows lists it. The window tests reuse the
fakes of test_detect.py, so no Epson backend process and no USB session is ever started.
"""
import os
import re
import struct
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import app  # noqa: E402
import backend_cli as be  # noqa: E402
import detect  # noqa: E402
import fake_hp  # noqa: E402
import history  # noqa: E402
import hp_backend  # noqa: E402
import hp_models  # noqa: E402
import hp_usb  # noqa: E402
import pnp  # noqa: E402
import prefs  # noqa: E402
import printer_state as ps  # noqa: E402
import report  # noqa: E402
import spooler  # noqa: E402
from test_detect import WindowCase, unit  # noqa: E402

HP_MODEL = "HP Smart Tank 580-590"


def setUpModule():
    """The tests must not talk to a real HP that happens to be plugged into this PC."""
    patcher = mock.patch.object(hp_usb, "read_all", side_effect=hp_usb.NoInterface("test"))
    patcher.start()
    unittest.addModuleCleanup(patcher.stop)


class Names(unittest.TestCase):
    def test_windows_names_of_hp_printers_seen_on_this_pc(self):
        for names, model in (
                (("HP Smart Tank 580-590 series", "Smart Tank 580-590 series"), HP_MODEL),
                (("HP Smart Tank 530 series", "Smart Tank 530 series"), "HP Smart Tank 530"),
                (("Smart Tank 750 series",), "HP Smart Tank 750"),
                (("HP Ink Tank Wireless 410 series",), "HP Ink Tank Wireless 410"),
                (("Hewlett-Packard HP LaserJet 1022",), "HP LaserJet 1022"),
                (("USB2.0 Printer", "HP DeskJet 2700 series"), "HP DeskJet 2700"),
                ((), "")):
            self.assertEqual(hp_models.model_from_names(names), model, names)

    def test_queue_copies_are_the_same_model(self):
        self.assertTrue(hp_models.same_model("HP Smart Tank 580-590 series (Copiar 1)", HP_MODEL))
        self.assertFalse(hp_models.same_model("HP Smart Tank 530 series", HP_MODEL))
        self.assertFalse(hp_models.same_model("", HP_MODEL))

    def test_tank_family_and_3d_style(self):
        self.assertTrue(hp_models.is_tank(HP_MODEL))
        self.assertTrue(hp_models.is_tank("HP Ink Tank 310"))
        self.assertFalse(hp_models.is_tank("HP LaserJet 1022"))
        self.assertTrue(hp_models.is_smart_tank_580_family("HP Smart Tank 585"))
        self.assertFalse(hp_models.is_smart_tank_580_family("HP Smart Tank 530"))
        self.assertEqual(hp_models.style_for("hp", HP_MODEL), "hp_smart_tank_580")
        self.assertEqual(hp_models.style_for("epson", "L3150"), "epson_l3150")

    def test_smart_tank_210_gets_the_model_without_scanner(self):
        for model in ("HP Smart Tank 210-220", "HP Smart Tank 210", "HP Smart Tank 215"):
            self.assertTrue(hp_models.is_smart_tank_210_family(model), model)
            self.assertEqual(hp_models.style_for("hp", model), "hp_smart_tank_210", model)
        for model in (HP_MODEL, "HP Smart Tank 530", "HP Smart Tank 750", ""):
            self.assertFalse(hp_models.is_smart_tank_210_family(model), model)
        self.assertEqual(hp_models.style_for("hp", "HP Smart Tank 530"), "hp_smart_tank_580")

    def test_ink_tank_and_deskjet_2700_get_their_own_models(self):
        for model in ("HP Ink Tank 310", "HP Ink Tank 315", "HP Ink Tank Wireless 410",
                      "HP Ink Tank Wireless 415", "HP Ink Tank 419"):
            self.assertEqual(hp_models.style_for("hp", model), "hp_ink_tank_415", model)
        for model in ("HP DeskJet 2700", "HP DeskJet 2720", "HP DeskJet Ink Advantage 2775",
                      "HP DeskJet Ink Advantage 2776"):
            self.assertEqual(hp_models.style_for("hp", model), "hp_deskjet_2775", model)
        for model in ("HP Ink Tank 3100", "HP DeskJet 3700", "HP DeskJet 27000",
                      "HP Smart Tank 530"):
            self.assertEqual(hp_models.style_for("hp", model), "hp_smart_tank_580", model)

    def test_canon_and_brother_get_their_models(self):
        self.assertEqual(hp_models.style_for("canon", "G3110"), "canon_g3110")
        self.assertEqual(hp_models.style_for("brother", "DCP-T420W"), "brother_t420w")

    def test_lasers_get_the_printer_or_the_multifunction(self):
        cases = [("hp", "HP LaserJet M111w", "hp_laserjet_m111"),
                 ("hp", "HP LaserJet M110we", "hp_laserjet_m111"),
                 ("hp", "HP LaserJet MFP M141w", "hp_laserjet_m141"),
                 ("hp", "HP LaserJet Pro M15w", "hp_laserjet_m111"),
                 ("hp", "HP LaserJet M1132 MFP", "hp_laserjet_m141"),
                 ("brother", "HL-1212W", "brother_hl1212w"),
                 ("brother", "DCP-1612W", "brother_dcp1612w"),
                 ("pantum", "P2500W", "pantum_p2500w"),
                 ("pantum", "M6550NW", "pantum_m6550nw"),
                 ("samsung", "Xpress M2020W", "samsung_m2020w"),
                 ("samsung", "Xpress M2070W", "samsung_m2070w")]
        for brand, model, style in cases:
            self.assertEqual(hp_models.style_for(brand, model), style, model)
        self.assertEqual(hp_models.style_for("hp", "HP Smart Tank 530"), "hp_smart_tank_580")

    def test_every_style_has_its_files(self):
        import printer3d
        styles = {getattr(hp_models, name) for name in dir(hp_models)
                  if name.startswith("STYLE_")}
        self.assertTrue(styles <= set(printer3d.MODELS), styles - set(printer3d.MODELS))
        for style, (qml, *_rest) in printer3d.MODELS.items():
            self.assertTrue((printer3d.HERE / "view3d" / qml).is_file(), qml)
            self.assertTrue((printer3d.HERE / "view3d" / "meshes" / style).is_dir(), style)

    def test_xp2100_family_gets_the_cartridge_model(self):
        for model in ("XP-2100", "XP-2101", "XP-2105", "XP-2150", "XP-2155"):
            self.assertEqual(hp_models.style_for("epson", model), "epson_xp2100", model)
        for model in ("XP-2200", "XP-231", "L3150", "XP-21000", ""):
            self.assertEqual(hp_models.style_for("epson", model), "epson_l3150", model)
        self.assertEqual(hp_models.style_for("hp", "XP-2100"), "hp_smart_tank_580")

    def test_serial_from_the_usb_device_id(self):
        self.assertEqual(hp_models.serial_from_device_id(r"USB\VID_03F0&PID_2A54\CN09C3S2XG"),
                         "CN09C3S2XG")
        self.assertEqual(hp_models.serial_from_device_id(r"USB\VID_03F0&PID_2A54\6&1a&0&1"), "")
        self.assertEqual(pnp._serial_of(r"USB\VID_03F0&PID_3954\TH47J6D0NN"), "TH47J6D0NN")

    def test_usb_unit_of_an_hp(self):
        hp = fake_hp.usb_unit()
        self.assertEqual(hp.brand, "hp")
        self.assertEqual(hp.name, "HP Smart Tank 580-590 series")
        self.assertEqual(pnp.UsbPrinter("x", (), "4454", (), pnp.HP_VENDOR).name,
                         "HP USB (PID 4454)")
        self.assertEqual(unit("L3150").brand, "epson")


class Detection(unittest.TestCase):
    def test_one_hp_is_detected_with_its_serial(self):
        found = detect.detect({}, [fake_hp.usb_unit()])
        self.assertEqual((found.status, found.brand, found.model),
                         (detect.SINGLE, "hp", HP_MODEL))
        self.assertIn(fake_hp.SERIAL, found.message)
        self.assertEqual(found.summary, HP_MODEL)

    def test_an_epson_stays_an_epson(self):
        db = be.models()
        found = detect.detect(db, [unit("L3150")])
        self.assertEqual((found.status, found.brand, found.model), (detect.SINGLE, "epson", "L3150"))

    def test_an_epson_and_an_hp_are_not_guessed(self):
        found = detect.detect({}, [unit("L3150"), fake_hp.usb_unit()])
        self.assertEqual(found.status, detect.SEVERAL)
        self.assertIn("Epson y HP", found.message)
        self.assertIn("HP Smart Tank 580-590 series", found.message)

    def test_nothing_attached_names_both_brands(self):
        self.assertIn("ni una HP", detect.detect({}, []).message)

    def test_the_hp_list_is_a_registry_read_that_never_raises(self):
        found = pnp.hp_usb_printers()
        self.assertIsInstance(found, list)
        self.assertTrue(all(p.brand == "hp" for p in found))
        self.assertEqual(pnp.hp_usb_printers("00000000-0000-0000-0000-000000000000"), [])

    def test_the_hp_naming_code_cannot_talk_to_a_device(self):
        source = (ROOT / "hp_models.py").read_text(encoding="utf-8")
        for forbidden in ("import", "open(", "socket", "http", "CreateFile", "subprocess"):
            if forbidden == "import":
                self.assertEqual(re.findall(r"^import (\w+)", source, re.M), ["re"])
                continue
            self.assertNotIn(forbidden, source)


class Ipp(unittest.TestCase):
    def test_request_is_get_printer_attributes(self):
        body = hp_backend.ipp_request("ipp://10.0.0.5:631/ipp/print")
        self.assertEqual(body[:4], b"\x01\x01\x00\x0b")
        self.assertIn(b"printer-uri", body)
        self.assertIn(b"marker-levels", body)
        self.assertEqual(body[-1:], b"\x03")

    def test_response_round_trip(self):
        data = fake_hp.ipp_response(fake_hp.ipp_attrs(levels=(40, 3, -3, -2)))
        status, attrs = hp_backend.ipp_parse(data)
        self.assertEqual(status, 0)
        self.assertEqual(attrs["marker-levels"], [40, 3, -3, -2])
        self.assertEqual(attrs["printer-state"], [3])
        info = hp_backend.ipp_to_info(attrs)
        self.assertEqual(info["serial_number"], fake_hp.SERIAL)
        self.assertEqual(info["firmware_version"], fake_hp.FIRMWARE)
        self.assertEqual([(i["level"], i["state"]) for i in info["inks"]],
                         [(40, "ok"), (3, "low"), (None, "ok"), (None, "")])

    def test_broken_responses_are_errors_not_crashes(self):
        with self.assertRaises(hp_backend.HpError):
            hp_backend.ipp_parse(b"\x01\x01")
        with self.assertRaises(hp_backend.HpError):
            hp_backend.ipp_parse(fake_hp.ipp_response(fake_hp.ipp_attrs())[:60])

    def test_device_id(self):
        fields = hp_backend.parse_device_id("MFG:HP;MDL:Smart Tank 580-590 series;SN:CN1;")
        self.assertEqual((fields["MFG"], fields["MDL"], fields["SN"]),
                         ("HP", "Smart Tank 580-590 series", "CN1"))

    def test_addresses(self):
        self.assertEqual(hp_backend.parse_host(" 192.168.0.25 "), ("192.168.0.25", None))
        self.assertEqual(hp_backend.parse_host("127.0.0.1:8631"), ("127.0.0.1", 8631))
        self.assertEqual(hp_backend.parse_host("HP-580.local"), ("HP-580.local", None))
        for bad in ("http://10.0.0.1/", "10.0.0.1/DevMgmt", "a b", ""):
            with self.assertRaises(hp_backend.HpError, msg=bad):
                hp_backend.parse_host(bad)


class NetworkReading(unittest.TestCase):
    def setUp(self):
        self.hp = fake_hp.FakeHp().start()
        self.addCleanup(self.hp.stop)

    def read(self, printer="usb"):
        unit_ = fake_hp.usb_unit() if printer == "usb" else printer
        return hp_backend.read(unit_, self.hp.address, timeout=3)

    def test_everything_the_580_serves(self):
        info = self.read()
        self.assertEqual(info["brand"], "hp")
        self.assertEqual(info["model"], HP_MODEL)
        self.assertEqual(info["serial_number"], fake_hp.SERIAL)
        self.assertEqual(info["firmware_version"], fake_hp.FIRMWARE)
        self.assertEqual(info["product_number"], fake_hp.PRODUCT)
        self.assertEqual(info["via"], ["USB (Windows)", "IPP", "LEDM"])
        self.assertTrue(info["ready"])
        self.assertEqual(info["usage"]["total"], 1834)
        self.assertEqual(info["usage"]["scans"], 412)
        self.assertEqual(info["usage"]["copies"], 97)
        self.assertEqual([h["label"] for h in info["printheads"]], ["K", "CMY"])
        inks = ps.hp_inks(info)
        self.assertEqual([i.name for i in inks], ["Negro", "Cian", "Magenta", "Amarillo"])
        self.assertEqual([i.state for i in inks], ["con tinta", "con tinta", "con tinta", "bajo"])
        self.assertTrue(all(i.level is None for i in inks), "the 580 gives no percentage")

    def test_only_reads_reach_the_printer(self):
        self.read()
        self.assertTrue(self.hp.requests)
        for method, path, body in self.hp.requests:
            if method == "POST":
                self.assertEqual(path, "/ipp/print")
                self.assertEqual(struct.unpack(">H", body[2:4])[0], 0x000B,
                                 "only Get-Printer-Attributes")
            else:
                self.assertEqual(method, "GET")
                self.assertTrue(path.startswith("/DevMgmt/") and path.endswith("Dyn.xml"))

    def test_levels_from_ipp_fill_in_when_ledm_has_none(self):
        self.hp.ipp = fake_hp.ipp_attrs(levels=(70, 60, 10, 90))
        inks = {i.name: i.level for i in ps.hp_inks(self.read())}
        self.assertEqual(inks, {"Negro": 90, "Cian": 70, "Magenta": 60, "Amarillo": 10})

    def test_ledm_alone(self):
        self.hp.ipp_enabled = False
        info = self.read()
        self.assertEqual(info["via"], ["USB (Windows)", "LEDM"])
        self.assertEqual(info["serial_number"], fake_hp.SERIAL)

    def test_ipp_alone(self):
        self.hp.ledm_enabled = False
        info = self.read()
        self.assertEqual(info["via"], ["USB (Windows)", "IPP"])
        self.assertEqual(info["serial_number"], fake_hp.SERIAL)
        self.assertEqual(ps.hp_status_text(info), "En reposo")
        self.assertEqual(info["usage"], {})

    def test_network_only(self):
        info = hp_backend.read(None, self.hp.address, timeout=3)
        self.assertEqual(info["via"], ["IPP", "LEDM"])
        self.assertEqual(info["model"], HP_MODEL)

    def test_nothing_answers(self):
        self.hp.ipp_enabled = self.hp.ledm_enabled = False
        with self.assertRaises(hp_backend.HpError):
            hp_backend.read(None, self.hp.address, timeout=3)
        info = self.read()          # with the USB unit: identity, and the error kept
        self.assertEqual(info["via"], ["USB (Windows)"])
        self.assertEqual(info["serial_number"], fake_hp.SERIAL)
        self.assertTrue(info["network_errors"])
        self.assertEqual(info["host"], "")

    def test_usb_only(self):
        info = hp_backend.read(fake_hp.usb_unit(), "",
                               spooler={"queue": "HP Smart Tank 580-590 series", "jobs": 0,
                                        "problem": "impresora sin papel"})
        self.assertEqual(info["model"], HP_MODEL)
        self.assertEqual(info["serial_number"], fake_hp.SERIAL)
        self.assertFalse(info["ready"])
        self.assertEqual(ps.hp_status_text(info), "Windows indica: impresora sin papel")
        self.assertEqual(ps.hp_inks(info), [])
        with self.assertRaises(hp_backend.HpError):
            hp_backend.read(None, "")


REST = {
    "identity": {"makeAndModel": {"name": "Smart Tank 210-220 series"}, "serialNumber": "CN1",
                 "productNumber": "3D4L3A", "firmwareVersion": "FW1"},
    "status": {"status": "inPowerSave"},
    "supplies": {"suppliesList": [
        {"supplyType": "inkCartridge", "supplyColorCode": "CMY", "supplyState": "ok",
         "selectabilityNumber": "M0H50A"},
        {"supplyType": "inkTank", "supplyColorCode": "K", "supplyState": "ok",
         "percentLifeDisplay": 40, "levelState": "ok"},
        {"supplyType": "inkTank", "supplyColorCode": "C", "supplyState": "ok",
         "percentLifeDisplay": 5, "levelState": "low"}]},
    "alerts": {"version": "1.1.0"},
    "counters": {"printUsage": {"impressions": {"monochrome": 1, "color": 2, "total": 3}}},
}


class UsbRest(unittest.TestCase):
    def test_a_usb_only_hp_is_read_without_an_ip(self):
        with mock.patch.object(hp_usb, "read_all", return_value=REST):
            info = hp_backend.read(fake_hp.usb_unit(), "")
        self.assertEqual(info["via"], ["USB (Windows)", "USB (REST)"])
        self.assertEqual(info["host"], "")
        self.assertTrue(info["ready"])
        self.assertEqual([(i["key"], i["level"], i["state"]) for i in info["inks"]],
                         [("K", 40, "ok"), ("C", 5, "low")])
        self.assertEqual(info["printheads"][0]["key"], "CMY")
        self.assertEqual(info["usage"]["total"], 3)
        self.assertEqual(info["firmware_version"], "FW1")

    def test_a_busy_interface_keeps_the_windows_identity_and_says_why(self):
        busy = hp_usb.UsbRestError("¿HP Smart sigue abierto?")
        with mock.patch.object(hp_usb, "read_all", side_effect=busy):
            info = hp_backend.read(fake_hp.usb_unit(), "")
        self.assertEqual(info["via"], ["USB (Windows)"])
        self.assertTrue(info["network_errors"][0].startswith("USB:"))

    def test_only_get_is_ever_sent(self):
        sent = []

        class Fake(hp_usb.Session):
            def __init__(self):
                pass

            def get(self, target):
                sent.append(target)
                return {}

        Fake().get(hp_usb.PATHS["status"])
        self.assertEqual(sent, [hp_usb.PATHS["status"]])
        self.assertFalse(hasattr(hp_usb.Session, "post"))
        self.assertFalse(hasattr(hp_usb.Session, "patch"))


class HpWarnings(unittest.TestCase):
    def info(self, **state):
        base = {"category": "", "ipp": "", "reasons": [], "ledm_alerts": [], "spooler": None}
        base.update(state)
        return {"state": base, "inks": []}

    def test_ipp_reasons(self):
        found = ps.hp_alerts(self.info(ipp="stopped", reasons=[
            "marker-supply-low-warning", "media-empty-error", "com.hp-custom-report"]))
        self.assertEqual([(a.severity, a.title) for a in found], [
            (ps.ERROR, "Sin papel"), (ps.WARNING, "Tinta baja"),
            (ps.INFO, "Aviso de la impresora sin descripción")])

    def test_waste_ink_is_shown_when_the_printer_reports_it(self):
        almost = ps.hp_alerts(self.info(reasons=["marker-waste-almost-full-warning"]))
        full = ps.hp_alerts(self.info(reasons=["marker-waste-full-error"]))
        self.assertEqual(almost[0].severity, ps.WARNING)
        self.assertEqual(full[0].severity, ps.ERROR)
        self.assertIn("absorbente", full[0].action.lower())
        self.assertIn("no documenta", full[0].action)

    def test_ledm_alerts_and_category(self):
        found = ps.hp_alerts(self.info(category="closeDoorOrCover", ledm_alerts=[
            {"id": "cartridgeLow", "severity": "Warning", "colour": "Yellow"}]))
        self.assertEqual([a.title for a in found], ["Tapa o puerta abierta", "Tinta baja (amarillo)"])
        self.assertEqual(ps.hp_status_text(self.info(category="inPowerSave")),
                         "En ahorro de energía")

    def test_ink_sensor_without_alert_still_warns(self):
        info = self.info()
        info["inks"] = [{"key": "Black", "state": "out", "level": None}]
        self.assertEqual([(a.severity, a.title) for a in ps.hp_alerts(info)],
                         [(ps.ERROR, "Sin tinta (negro)")])

    def test_report_lists_the_sensor_words(self):
        data = report.sample()
        data.update(pads=[], pads_note="HP no publica un contador.", via="USB + IPP",
                    inks=[("Negro", None, "con tinta"), ("Amarillo", None, "bajo")])
        html = report.build_html(data)
        self.assertIn("Amarillo bajo", html)
        self.assertIn("sensor de tinta baja", html)
        self.assertIn("HP no publica un contador.", html)
        self.assertIn("Leída por", html)
        self.assertIn("Almohadillas: HP no publica", report.summary_text(data))


class HpInTheWindow(WindowCase):
    """A Smart Tank 580 on USB, with its network side answering at the typed address."""

    def setUp(self):
        super().setUp()
        self.hp = fake_hp.FakeHp().start()
        self.addCleanup(self.hp.stop)
        self.attached = [fake_hp.usb_unit()]
        self.hp_queues = [spooler.Queue("HP Smart Tank 580-590 series", "USB090", True),
                          spooler.Queue("HP Smart Tank 530 series", "USB056", False)]
        self.spool = (0, "")
        self.opened = []
        for target, name, replacement in (
                (spooler, "hp_queues", lambda: list(self.hp_queues)),
                (spooler, "queue_state", lambda queue, ignore=(): self.spool),
                (report, "REPORTS", Path(self.tmp.name) / "reports"),
                (os, "startfile", lambda path: self.opened.append(Path(path)))):
            patcher = mock.patch.object(target, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        prefs.save(hp_host=self.hp.address)

    def details(self, win):
        return "\n".join(f"{win.details.item(r, 0).text()}: {win.details.item(r, 1).text()}"
                         for r in range(win.details.rowCount()) if win.details.item(r, 1))

    def test_it_is_detected_and_read_without_the_epson_backend(self):
        win = self.open_window()
        self.assertEqual(win.brand, "hp")
        self.assertEqual(win.model_name, HP_MODEL)
        self.assertEqual(win.model.itemText(0), f"Automático · {HP_MODEL}")
        self.assertEqual(self.reads, [], "the Epson backend is never asked about an HP")
        self.spawn.assert_not_called()
        be.read_cells.assert_not_called()
        self.assertEqual(win.title.text(), HP_MODEL)
        self.assertIn(fake_hp.SERIAL, win.subtitle.text())
        self.assertIn("IPP", win.subtitle.text())
        self.assertIn(fake_hp.SERIAL, win.windowTitle())
        self.assertEqual(win.chip.text(), "Lista · 1 aviso")
        self.assertIn("Tinta baja (amarillo)", win.alerts_label.text())
        self.assertEqual(win.usage["Estado"].text(), "Lista")
        self.assertEqual(win.usage["Páginas impresas"].text(), "1834")
        self.assertEqual(win.usage["Escaneos"].text(), "412")
        self.assertEqual(win.ink_row.count() - 1, 4, "four tanks and a stretch")
        self.assertIn("sensores", win.ink_note.text())
        self.assertIn("Cabezales: negro bien · tricolor bien", win.ink_note.text())
        self.assertIn("HP no publica un contador", win.waste_note.text())
        self.assertIn("deshabilitados", win.reset_hint.text())
        self.assertEqual(win.gauges, {})
        self.assertTrue(win.banner.isHidden())
        self.assertEqual([q.name for q in win.queues], ["HP Smart Tank 580-590 series"])
        details = self.details(win)
        for text in (f"Número de serie: {fake_hp.SERIAL}", f"Firmware: {fake_hp.FIRMWARE}",
                     f"Número de producto: {fake_hp.PRODUCT}", "Páginas en color: 633",
                     "Tinta amarillo: bajo", "Leída por: USB (Windows) + IPP + LEDM",
                     "Reseteo de contadores: Deshabilitado para HP"):
            self.assertIn(text, details)

    def test_reset_and_epson_commands_are_off_and_say_why(self):
        win = self.open_window()
        for button in win.reset_buttons:
            self.assertFalse(button.isEnabled(), button.text())
            self.assertIn("HP no publica un contador", button.toolTip())
        for button in (win.btn_nozzle, win.btn_nozzle2, win.btn_color, win.btn_clean):
            self.assertFalse(button.isEnabled(), button.text())
            self.assertIn("comandos Epson", button.toolTip())
        self.assertFalse(win.btn_dump.isEnabled())
        self.assertIn("EEPROM", win.btn_dump.toolTip())
        for button in (win.btn_report, win.btn_summary, win.btn_testpage):
            self.assertTrue(button.isEnabled(), button.text())
        # even when called directly (3D view, shortcut), nothing is done
        for call in (lambda: win.reset("perm"), lambda: win.reset("dry"), win.backup,
                     win.clean_heads, win.read_dump,
                     lambda: win.maintenance("Test de inyectores", lambda: b"x", "check", False)):
            with mock.patch.object(spooler, "send_direct") as sent:
                call()
                sent.assert_not_called()
        self.assertTrue(pump_idle(self, win))
        be.reset.assert_not_called()
        be.read_cells.assert_not_called()
        self.assertIn("no disponible para HP", win.log.toPlainText())
        self.assertFalse(list((Path(self.tmp.name) / "backups").glob("*.json")))

    def test_3d_view_gets_brand_style_and_real_ink_states(self):
        win = self.open_window()
        data = win.bridge3d.data
        self.assertEqual((data["brand"], data["style"]), ("hp", "hp_smart_tank_580"))
        self.assertTrue(data["connected"])
        self.assertEqual(data["serial"], fake_hp.SERIAL)
        self.assertEqual(data["status"], "Lista")
        self.assertEqual([(i["name"], i["level"], i["state"]) for i in data["inks"]],
                         [("Negro", -1, "con tinta"), ("Cian", -1, "con tinta"),
                          ("Magenta", -1, "con tinta"), ("Amarillo", -1, "bajo")])
        self.assertEqual(data["pads"], [])
        self.assertFalse(data["canReset"])
        self.assertIn("HP no publica", data["why"])
        before = be.reset.call_count
        win.bridge3d.reset("perm")
        win.bridge3d.backup()
        self.assertEqual(be.reset.call_count, before)

    def test_ink_percentages_reach_the_3d_view_when_the_printer_gives_them(self):
        self.hp.ipp = fake_hp.ipp_attrs(levels=(70, 60, 10, 90))
        win = self.open_window()
        self.assertEqual([i["level"] for i in win.bridge3d.data["inks"]], [90, 70, 60, 10])
        self.assertTrue(win.bridge3d.data["inkMeasured"])
        self.assertIn("Nivel estimado", win.ink_note.text())

    def test_report_summary_and_history_carry_the_hp(self):
        win = self.open_window()
        win.make_report()
        self.assertTrue(self.opened)
        pdf = self.opened[-1]
        self.assertEqual(pdf.read_bytes()[:4], b"%PDF")
        self.assertIn(fake_hp.SERIAL, pdf.name)
        event = history.load()[0]
        self.assertEqual((event["kind"], event["model"], event["serial"]),
                         ("informe", HP_MODEL, fake_hp.SERIAL))
        win._render_history()
        self.assertIn(f"{HP_MODEL} · {fake_hp.SERIAL}  · conectada", [
            win.history_who.itemText(i) for i in range(win.history_who.count())])
        self.assertEqual(win._history_serial(), fake_hp.SERIAL)
        self.assertEqual(win.history_table.rowCount(), 1)
        win.copy_summary()
        text = app.QApplication.clipboard().text()
        self.assertIn(f"{HP_MODEL} · serie {fake_hp.SERIAL}", text)
        self.assertIn("Amarillo bajo", text)
        self.assertIn("Almohadillas: HP no publica", text)
        self.assertIn("Páginas impresas: 1834", text)

    def test_the_test_page_goes_to_the_hp_queue(self):
        win = self.open_window()
        self.assertEqual(win.print_queue.currentData().name, "HP Smart Tank 580-590 series")
        with mock.patch.object(app.testpage, "print_pdf",
                               side_effect=RuntimeError("stop: nothing is printed")) as printed:
            win.print_test_page()
        printed.assert_called_once_with(queue="HP Smart Tank 580-590 series",
                                        path=app.testpage.version_path(app.testpage.DEFAULT))

    def test_usb_only_says_how_to_read_the_rest(self):
        prefs.save(hp_host="")
        self.spool = (0, "impresora sin papel")
        win = self.open_window()
        self.assertEqual(win.brand, "hp")
        self.assertIn(fake_hp.SERIAL, win.subtitle.text())
        self.assertFalse(win.banner.isHidden())
        self.assertIn("HP por red", win.banner.text())
        self.assertIn("escribí su IP", win.ink_note.text())
        self.assertEqual(win.usage["Estado"].text(), "Windows indica: impresora sin papel")
        self.assertIn("Windows indica: impresora sin papel", win.alerts_label.text())
        self.assertEqual(self.hp.requests, [], "no address: the network is not touched")

    def test_the_address_of_its_windows_tcp_queue_is_used(self):
        prefs.save(hp_host="")
        self.hp_queues.append(spooler.Queue("HP Smart Tank 580-590 series (Copiar 1)",
                                            "IP_10.0.0.9", True, self.hp.address))
        win = self.open_window()
        self.assertEqual(win.info["host"], self.hp.address)
        self.assertTrue(win.info["host_from_queue"])
        self.assertIn("cola de Windows", self.details(win))

    def test_a_network_hp_without_usb(self):
        self.attached = []
        win = self.open_window()
        self.assertEqual(win.detection.status, detect.NONE)
        self.assertEqual(win.brand, "hp")
        self.assertEqual(win.model_name, HP_MODEL)
        self.assertEqual(win.info["via"], ["IPP", "LEDM"])
        self.assertEqual(self.reads, [])

    def test_an_address_that_does_not_answer_keeps_the_usb_identity(self):
        self.hp.ipp_enabled = self.hp.ledm_enabled = False
        win = self.open_window()
        self.assertEqual(win.brand, "hp")
        self.assertIn(fake_hp.SERIAL, win.subtitle.text())
        self.assertIn("no respondió por la red", win.banner.text())

    def test_unplugging_the_hp_clears_everything(self):
        prefs.save(hp_host="")
        win = self.open_window()
        self.assertEqual(win.brand, "hp")
        self.attached = []
        self.refresh(win)
        self.assertEqual(win.brand, "")
        self.assertFalse(win.info)
        self.assertEqual(win.usage["Páginas impresas"].text(), "--")
        self.assertEqual(win.bridge3d.data["brand"], "epson")
        self.assertFalse(win.bridge3d.data["connected"])

    def test_an_epson_after_the_hp_is_an_epson_again(self):
        prefs.save(hp_host="")
        win = self.open_window()
        self.attached = [unit("L3150")]
        self.refresh(win)
        self.assertEqual(win.brand, "epson")
        self.assertEqual(self.reads, ["L3150"])
        self.assertEqual((win.bridge3d.data["brand"], win.bridge3d.data["style"]),
                         ("epson", "epson_l3150"))
        self.assertTrue(all(b.isEnabled() for b in win.reset_buttons))


class EpsonIn3d(WindowCase):
    def test_the_epson_family_gets_its_brand_and_style(self):
        self.attached = [unit("L3150")]
        win = self.open_window()
        data = win.bridge3d.data
        self.assertEqual((data["brand"], data["style"]), ("epson", "epson_l3150"))
        self.assertEqual(data["model"], "L3150")
        self.assertTrue(data["connected"])


def pump_idle(case, win):
    from test_detect import pump
    return pump(case.qapp, lambda: not win.busy)


if __name__ == "__main__":
    unittest.main()
