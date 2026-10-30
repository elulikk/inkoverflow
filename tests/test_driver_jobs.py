"""XP-2100/2101 jobs from the Epson driver capture. Hardware-free."""
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import cleaning as cl  # noqa: E402
import driver_jobs as dj  # noqa: E402

FX = json.loads((HERE / "captured_frames_xp2100.json").read_text())


class JobsMatchTheCapture(unittest.TestCase):
    def test_nozzle_check(self):
        job = dj.nozzle_check_job(datetime(*FX["nozzle_check_time"]))
        self.assertEqual(job.hex(), FX["nozzle_check_job"])

    def test_cleaning(self):
        job = dj.cleaning_job(datetime(*FX["cleaning_time"]))
        self.assertEqual(job.hex(), FX["cleaning_job"])


class FeedSheet(unittest.TestCase):
    def test_an_empty_page_that_ends_in_a_form_feed(self):
        import spooler
        job = spooler.feed_sheet_job()
        self.assertTrue(job.startswith(b"\x00\x00\x00\x1b\x01@EJL 1284.4\n"))
        body = job[job.index(b"\x1b(G"):]
        self.assertIn(b"\x0c", body)                     # the form feed turns the rollers
        self.assertNotIn(b"\x1b.", body)                 # no raster data: no ink
        self.assertNotIn(b"NC\x02\x00", job)             # not a nozzle check
        self.assertNotIn(b"CH\x02\x00", job)             # not a cleaning
        self.assertTrue(job.endswith(b"JE\x01\x00\x00\x1b\x00\x00\x00"))
        # the long ESC ( U goes with the long ESC ( v, and the page size is given
        self.assertIn(b"\x1b(U\x05\x00", body)
        self.assertNotIn(b"\x1b(U\x01\x00", body)
        self.assertIn(b"\x1b(C\x04\x00", body)
        self.assertIn(b"\x1b(S\x08\x00", body)


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


class FakeXP2100:
    """Idle, cleans for 115 s after the job, then idle again with the counter raised."""

    def __init__(self, clock, fail=None):
        self.clock, self.fail = clock, fail
        self.sent, self.queries, self.sent_at = [], [], None
        self.main = [0x10, 0x00, 0x00]  # cells 337, 338, 336

    def send(self, data):
        self.sent.append(data)
        self.sent_at = self.clock.t
        return len(data)

    def read_info(self, model):
        self.queries.append(self.clock.t)
        if self.sent_at is None:
            code = 4
        elif self.clock.t - self.sent_at < 115:
            code = 7
        else:
            code = 0 if self.fail == "error" else 4
            self.main[0] = 0x30
        return {"printer_status": {"status": (code, "")}}

    def read_cells(self, model, cells):
        values = dict.fromkeys(cells, 0)
        values.update({337: self.main[0], 338: self.main[1], 336: self.main[2]})
        return values


class DriverCleaning(unittest.TestCase):
    def run_with(self, printer, clock, **kw):
        return dj.run_cleaning("XP-2100", "Limpieza (driver Epson)", send=printer.send,
                               read_info=printer.read_info, read_cells=printer.read_cells,
                               sleep=clock.sleep, now=clock.now, **kw)

    def test_sends_the_driver_job_and_waits_quietly(self):
        clock = Clock()
        printer = FakeXP2100(clock)
        result = self.run_with(printer, clock)
        self.assertEqual(len(printer.sent), 1)
        self.assertIn(b"CH\x02\x00\x00\x00", printer.sent[0])
        # no question to the printer during the quiet period after the job
        self.assertFalse([t for t in printer.queries if 0 < t - printer.sent_at < dj.QUIET_S])
        self.assertGreater(result.delta_main, 0)
        self.assertFalse(result.restored)

    def test_refuses_a_busy_printer(self):
        clock = Clock()
        printer = FakeXP2100(clock)
        printer.sent_at = 0.0  # already cleaning
        with self.assertRaises(dj.DriverCleaningError):
            self.run_with(printer, clock)
        self.assertEqual(printer.sent, [])

    def test_error_state_is_reported(self):
        clock = Clock()
        with self.assertRaises(dj.DriverCleaningError):
            self.run_with(FakeXP2100(clock, fail="error"), clock)


class Modes(unittest.TestCase):
    def test_xp2100_gets_only_the_driver_mode(self):
        self.assertEqual([m[0] for m in cl.modes_for("XP-2100")], ["driver"])
        self.assertIn("XP-2100", cl.SUPPORTED_MODELS)
        self.assertEqual(cl.modes_for("L3150"), cl.MODES)

    def test_wrong_mode_for_the_model_is_refused(self):
        with self.assertRaises(cl.CleaningError):
            cl.run("XP-2100", "cl1")
        with self.assertRaises(cl.CleaningError):
            cl.run("L3150", "driver")
        with self.assertRaises(cl.CleaningError):
            cl.run("XP-2100", "driver", restore_counter=True)


if __name__ == "__main__":
    unittest.main()
