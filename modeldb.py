"""Prints the backend's model database as JSON (pads and reset cells per model), plus the
few models that mapped_models.py adds (XP-230, XP-231).

Run as a separate process so the EUPL-licensed backend stays out of the UI process.
"""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
logging.disable(logging.CRITICAL)
import mapped_models  # noqa: E402
from epson_print_conf import EpsonPrinter  # noqa: E402

PAD_KINDS = ("main_waste", "borderless_waste", "first_waste", "second_waste", "third_waste")

printer = EpsonPrinter(model="L3150")
db = {}
for name in sorted(printer.valid_printers):
    conf = printer.PRINTER_CONFIG[name]
    pads = {kind: {"oids": list(conf[kind]["oids"]), "divider": conf[kind]["divider"]}
            for kind in PAD_KINDS
            if isinstance(conf.get(kind), dict) and "oids" in conf[kind] and "divider" in conf[kind]}
    reset = conf.get("raw_waste_reset", {})
    write_key = conf.get("write_key")
    db[name] = {"pads": pads,
                "reset_cells": sorted(k for k in reset if isinstance(k, int)),
                "read_key": list(conf["read_key"]),
                "write_key": bytes(write_key).hex() if write_key else None}
mapped_models.apply(db)
print(json.dumps(db))
