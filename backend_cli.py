"""Runs backend/epson_print_conf.py (Ircama/epson_print_conf, EUPL-1.2) as a
separate process and parses its text output."""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "backend" / "epson_print_conf.py"

PAD_LABELS = {
    "main_waste": "Almohadilla principal",
    "borderless_waste": "Almohadilla del platen",
    "first_waste": "Almohadilla 1",
    "second_waste": "Almohadilla 2",
    "third_waste": "Almohadilla 3",
}
_models = None


def models():
    """Model database of the backend: {model: {"pads": {...}, "reset_cells": [...]}}."""
    global _models
    if _models is None:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.run([sys.executable, str(ROOT / "modeldb.py")],
                              capture_output=True, text=True, timeout=120,
                              creationflags=flags)
        try:
            _models = json.loads(proc.stdout)
        except ValueError as exc:
            raise BackendError("No se pudo cargar la base de modelos.") from exc
    return _models


def backend_model(model):
    """Name the backend knows `model` by. A few models are not listed by name but share
    the record of one that is (see mapped_models.py); everything else is its own name."""
    return models().get(model, {}).get("backend_model", model)


def is_mapped(model):
    return "backend_model" in models().get(model, {})


def family(model):
    """Names a printer of this model may declare: the model itself and, for a mapped
    model, the other names that share its configuration."""
    return [model, *models().get(model, {}).get("identifies_as", [])]


def cells_for(model):
    """EEPROM cells to back up: every pad counter plus what the reset rewrites."""
    entry = models()[model]
    cells = set(entry["reset_cells"])
    for pad in entry["pads"].values():
        cells.update(pad["oids"])
    return sorted(cells)


def keys(model):
    """(read_key, write_key) of a model: the EEPROM access keys of the backend's
    database. write_key is bytes, or None when the model has none."""
    entry = models()[model]
    write_key = bytes.fromhex(entry["write_key"]) if entry.get("write_key") else None
    return tuple(entry["read_key"]), write_key


def main_pad_cells(model):
    """EEPROM cells of the main waste pad counter, in the backend's byte order."""
    return list(models()[model]["pads"]["main_waste"]["oids"])


def can_reset(model):
    entry = models().get(model)
    return bool(entry) and bool(entry["pads"]) and bool(entry["reset_cells"])


EEPROM_LINE = re.compile(
    r"EEPROM_ADDR 0x[0-9A-Fa-f]+\s*=\s*(\d+):\s*(--|0x[0-9A-Fa-f]{2})")


class BackendError(RuntimeError):
    pass


def run(model, args, timeout=180):
    cmd = [sys.executable, str(SCRIPT), "--usb", "-m", backend_model(model), *args]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        proc = subprocess.run(cmd, cwd=SCRIPT.parent, capture_output=True,
                              text=True, timeout=timeout, creationflags=flags)
    except subprocess.TimeoutExpired as exc:
        raise BackendError("Tiempo de espera agotado.") from exc
    return proc.stdout, proc.stderr


def read_info(model):
    out, err = run(model, ["-i"])
    try:
        info = ast.literal_eval(out.strip())
    except (ValueError, SyntaxError):
        info = None
    if not isinstance(info, dict):
        detail = (err or out).strip().splitlines()
        raise BackendError(detail[-1] if detail else "Sin respuesta de la impresora.")
    return info


def parse_cells(out):
    cells = {}
    for match in EEPROM_LINE.finditer(out):
        value = match.group(2)
        cells[int(match.group(1))] = None if value == "--" else int(value, 16)
    return cells


def read_cells(model, addresses):
    out, _ = run(model, ["-R", ",".join(map(str, addresses))])
    cells = parse_cells(out)
    if any(cells.get(a) is None for a in addresses):
        raise BackendError("No se pudo leer la EEPROM completa.")
    return cells


def dump(model, start, end):
    out, _ = run(model, ["-e", str(start), str(end)], timeout=900)
    return parse_cells(out)


def pad_points(model, cells):
    """Return {pad: (points, maximum)} like the vendor program shows them.

    The backend reads a pad's cells little-endian in the order of its oids and
    divides by "divider" to get the percentage, so the maximum is divider * 100.
    """
    result = {}
    for name, pad in models()[model]["pads"].items():
        points = sum(cells[oid] << (8 * i) for i, oid in enumerate(pad["oids"]))
        result[name] = (points, round(pad["divider"] * 100))
    return result


def reset(model, mode):
    """mode: 'dry', 'temp' or 'perm'. Returns (ok, last output line)."""
    flag = {"dry": ["--reset_waste_ink", "--dry-run"],
            "temp": ["--temp_reset_waste_ink"],
            "perm": ["--reset_waste_ink"]}[mode]
    out, err = run(model, flag)
    lines = (out or err).strip().splitlines()
    last = lines[-1] if lines else "Sin respuesta."
    return ("done" in last.lower() and "fail" not in last.lower()), last
