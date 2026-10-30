"""Hardware-free tests. Run:  .venv\\Scripts\\python.exe -m unittest discover -s tests -v"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from epson_usb.d4 import Timeouts, build_packet  # noqa: E402

import backend_cli as be  # noqa: E402
import cleaning as cl  # noqa: E402
import history  # noqa: E402
from fake_printer import READ_KEY, FakeL3150, make_transport  # noqa: E402

FX = json.loads((HERE / "captured_frames.json").read_text())
FAST = Timeouts.scaled(0.02)


def counter(printer):
    e = printer.config.eeprom
    return e[48] + (e[49] << 8) + (e[47] << 16)


class Clock:
    """Fake time: sleeping advances it, so a 10-minute timeout runs instantly."""

    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class PacketsMatchTheCapture(unittest.TestCase):
    def test_data_socket_opening(self):
        self.assertEqual(build_packet(0, 0, cl.open_channel_payload(0x40), credit=1).hex(),
                         FX["open_channel_40"])
        self.assertEqual(build_packet(0, 0, cl.credit_request_payload(0x40), credit=1).hex(),
                         FX["credit_request_40"])
        self.assertEqual(build_packet(0, 0, cl.credit_payload(0x40), credit=1).hex(),
                         FX["credit_40"])

    def test_every_cleaning_command(self):
        for key, _label, byte, _t, _p in cl.MODES:
            packet = build_packet(0x40, 0x40, cl.cleaning_command(READ_KEY, byte))
            expected = FX["cleaning_" + key]
            self.assertEqual(packet.hex(), expected, key)

    def test_status_poll_frame(self):
        from epson_usb.epson_ctrl import packet_command
        self.assertEqual(packet_command(b"st", b"\x01").hex(), FX["st_poll"][12:])


class StatusReplies(unittest.TestCase):
    def payload(self, name):
        return bytes.fromhex(FX[name])[6:]  # drop the 6-byte D4 header

    def test_idle(self):
        self.assertEqual(cl.status_of(self.payload("status_idle")), {"code": 4, "error": None})

    def test_cleaning(self):
        self.assertEqual(cl.status_of(self.payload("status_cleaning"))["code"], 7)

    def test_error(self):
        self.assertEqual(cl.status_of(self.payload("status_error")), {"code": 0, "error": 0x10})

    def test_garbage_is_not_a_status(self):
        self.assertIsNone(cl.status_of(b"nonsense")["code"])
        self.assertIsNone(cl.status_of(None)["code"])


class DatabaseFacts(unittest.TestCase):
    def test_keys_and_pad_formula(self):
        self.assertEqual(be.keys("L3150"), ((151, 7), b"Maribaya"))
        points = be.pad_points("L3150", {48: 0x3B, 49: 0x16, 47: 0, 50: 0, 51: 0})
        self.assertEqual(points["main_waste"], (5691, 6346))   # what the original shows
        self.assertEqual(points["borderless_waste"], (0, 3416))

    def test_backup_cells_cover_the_counter(self):
        self.assertTrue({47, 48, 49, 50, 51} <= set(be.cells_for("L3150")))


class CleaningSessionOnAFakePrinter(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self._factory = cl.TRANSPORT_FACTORY

    def tearDown(self):
        cl.TRANSPORT_FACTORY = self._factory

    def run_cleaning(self, mode="cl1", restore=False, **printer_kwargs):
        transport, printer = make_transport(**printer_kwargs)
        cl.TRANSPORT_FACTORY = lambda: transport
        try:
            result = cl.run("L3150", mode, restore_counter=restore, timeouts=FAST,
                            sleep=self.clock.sleep, now=self.clock.now)
        except cl.CleaningError:
            self.printer_after_error = printer
            raise
        return result, printer

    def test_cl1_without_restore_lets_the_counter_rise(self):
        result, printer = self.run_cleaning("cl1")
        self.assertEqual(counter(printer), 5690 + 28)
        self.assertEqual(result.delta_main, 28)
        self.assertFalse(result.restored)
        self.assertEqual(result.hidden_points, 0)
        self.assertEqual(printer.eeprom_writes, [])

    def test_exactly_the_captured_command_is_sent(self):
        _result, printer = self.run_cleaning("cl3")
        self.assertEqual(len(printer.data_packets), 1)
        psid, ssid, payload = printer.data_packets[0]
        self.assertEqual((psid, ssid), (0x40, 0x40))
        self.assertEqual(payload, cl.cleaning_command(READ_KEY, 0x03))

    def test_restore_rewinds_only_the_main_counter_and_reports_hidden_ink(self):
        result, printer = self.run_cleaning("cl2", restore=True)
        self.assertEqual(counter(printer), 5690)
        self.assertTrue(result.restored)
        self.assertEqual(result.hidden_points, 60)
        # 5690 = 0x163A, 5750 = 0x1676: only the low byte (cell 48) differs
        self.assertEqual(printer.eeprom_writes, [(48, 0x3A)])

    def test_power_flushing_costs_more(self):
        result, printer = self.run_cleaning("power")
        self.assertEqual(result.delta_main, 400)

    def test_printer_error_aborts_without_restoring(self):
        with self.assertRaises(cl.CleaningError) as ctx:
            self.run_cleaning("cl1", restore=True, error_on_cleaning=True)
        self.assertIn("error", str(ctx.exception).lower())
        self.assertEqual(self.printer_after_error.eeprom_writes, [])

    def test_busy_printer_gets_nothing(self):
        transport, printer = make_transport()
        printer.status_code = 0x07
        cl.TRANSPORT_FACTORY = lambda: transport
        with self.assertRaises(cl.CleaningError):
            cl.run("L3150", "cl1", timeouts=FAST, sleep=self.clock.sleep, now=self.clock.now)
        self.assertEqual(printer.data_packets, [])

    def test_a_cleaning_that_never_ends_times_out_and_restores_nothing(self):
        transport, printer = make_transport()
        printer.cleaning_polls_left = 10 ** 9
        cl.TRANSPORT_FACTORY = lambda: transport
        original = printer._handle_packet

        def never_finish(packet):  # keep the printer "cleaning" forever
            original(packet)
            if packet.psid == 0x40:
                printer.cleaning_polls_left = 10 ** 9

        printer._handle_packet = never_finish
        with self.assertRaises(cl.CleaningError) as ctx:
            cl.run("L3150", "cl1", restore_counter=True, timeouts=FAST,
                   sleep=self.clock.sleep, now=self.clock.now)
        self.assertIn("no terminó", str(ctx.exception))
        self.assertEqual(printer.eeprom_writes, [])

    def test_unverified_model_is_refused_before_touching_usb(self):
        def boom():
            raise AssertionError("USB must not be opened")

        cl.TRANSPORT_FACTORY = boom
        with self.assertRaises(cl.CleaningError):
            cl.run("L4150", "cl1")

    def test_progress_is_reported(self):
        transport, _printer = make_transport()
        cl.TRANSPORT_FACTORY = lambda: transport
        seen = []
        cl.run("L3150", "cl1", timeouts=FAST, sleep=self.clock.sleep, now=self.clock.now,
               on_progress=lambda text, elapsed: seen.append((text, elapsed)))
        self.assertTrue(seen)
        self.assertTrue(all("CL1" in text for text, _ in seen))


class HistoryAndHiddenInk(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self._old = history.DATA
        history.DATA = Path(self._dir.name)

    def tearDown(self):
        history.DATA = self._old
        self._dir.cleanup()

    def test_record_and_load_newest_first(self):
        history.record("limpieza", "L3150", "A", detail="uno")
        history.record("reseteo", "L3150", "B", detail="dos")
        events = history.load()
        self.assertEqual([e["detail"] for e in events], ["dos", "uno"])
        self.assertEqual([e["detail"] for e in history.load(serial="A")], ["uno"])

    def test_corrupt_lines_are_skipped(self):
        history.record("x", "L3150", "A")
        with (history.DATA / "history.jsonl").open("a") as fh:
            fh.write("{not json\n")
        self.assertEqual(len(history.load()), 1)

    def test_hidden_points_accumulate_and_clear(self):
        self.assertEqual(history.hidden_points("A"), 0)
        self.assertEqual(history.add_hidden("A", 28), 28)
        self.assertEqual(history.add_hidden("A", 60), 88)
        self.assertEqual(history.add_hidden("B", 5), 5)
        history.clear_hidden("A")
        self.assertEqual(history.hidden_points("A"), 0)
        self.assertEqual(history.hidden_points("B"), 5)

    def test_negative_points_are_ignored(self):
        self.assertEqual(history.add_hidden("A", -10), 0)


if __name__ == "__main__":
    unittest.main()
