"""Decides which printer model is really plugged in, from what Windows reports about the
Epson and HP USB printers that are present (pnp.py) and the backend's model database.
An Epson must be in the backend's database; an HP is named from its Windows names
(hp_models.py) and read by hp_backend.py.

The Windows print queues play no part: the PC accumulates one per printer that was ever
attached. Nothing here touches a printer, so it can run at any time.
"""
import re
from dataclasses import dataclass

import hp_models

NONE, SINGLE, SEVERAL, UNKNOWN = "none", "single", "several", "unknown"


@dataclass(frozen=True)
class Detection:
    status: str
    model: str = ""         # backend model; only set when status == SINGLE
    printers: tuple = ()    # the pnp.UsbPrinter units that are attached
    summary: str = ""       # a few words for the selector
    message: str = ""       # a full sentence for the banner and the log
    brand: str = "epson"    # "epson" or "hp": who makes the printer that was found


def _key(text):
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def candidates(name):
    """Model spellings that one Windows name can stand for, most likely first.

    "EPSON L3150 Series" -> L3150; "EPSON XP-231 235 Series" -> XP-231, XP-235 (Epson
    writes a family as the first model followed by the last digits of the others)."""
    base = re.sub(r"^\s*EPSON\s+", "", name.strip(), flags=re.I)
    base = re.sub(r"\s+Series\s*$", "", base, flags=re.I).strip()
    if not base:
        return []
    tokens = base.split()
    found = [base, tokens[0]]
    prefix = re.match(r"\D+", tokens[0])
    if prefix and len(tokens) > 1:
        found += [prefix.group(0) + token for token in tokens[1:] if re.fullmatch(r"\d+\w*", token)]
    return list(dict.fromkeys(found))


def resolve(names, db):
    """The backend model a printer is, from the names Windows gives it, or ''. A model is
    only accepted when its whole name matches: L315 is not L3150."""
    by_key = {}
    for model in sorted(db):
        by_key.setdefault(_key(model), model)
    for name in names:
        for candidate in candidates(name):
            if _key(candidate) in by_key:
                return by_key[_key(candidate)]
    return ""


def detect(db, printers):
    """What is plugged in, as a Detection. `printers` are the present Epson USB units."""
    printers = tuple(printers)
    if not printers:
        return Detection(
            NONE, summary="sin impresora",
            message="Windows no ve ninguna impresora Epson conectada por USB (ni una HP). "
                    "Comprueba el cable, que esté encendida, y pulsa Actualizar (F5).")
    if len(printers) > 1:
        names = ", ".join(p.name for p in printers)
        brands = {getattr(p, "brand", "epson") for p in printers}
        what = "impresoras Epson" if brands == {"epson"} else (
            "impresoras HP" if brands == {"hp"} else "impresoras (Epson y HP)")
        return Detection(
            SEVERAL, printers=printers, summary="varias impresoras",
            message=f"Hay {len(printers)} {what} conectadas por USB ({names}). "
                    "No se adivina cuál es: deja conectada solo la que quieres usar y pulsa "
                    "Actualizar (F5).")
    printer = printers[0]
    if getattr(printer, "brand", "epson") == "hp":
        model = hp_models.model_from_names(printer.names) or "HP"
        serial = f", serie {printer.serial}" if printer.serial else ""
        return Detection(SINGLE, model, printers, summary=model, brand="hp",
                         message=f"Impresora HP conectada: {printer.name}{serial}. "
                                 f"Modelo: {model}.")
    model = resolve(printer.names, db)
    if model:
        return Detection(SINGLE, model, printers, summary=model,
                         message=f"Impresora conectada: {printer.name}. Modelo: {model}.")
    return Detection(
        UNKNOWN, printers=printers, summary="modelo no soportado",
        message=f"Hay una impresora Epson conectada ({printer.name}), pero su modelo no está "
                "en la base del backend: no se puede leer ni resetear desde aquí.")
