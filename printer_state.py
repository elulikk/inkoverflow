"""Ink levels and printer warnings, in words for the user.

Everything here comes from `info["printer_status"]`, the status block the backend already
decodes on every Actualizar (epson_print_conf.status_parser, "st" command). Nothing in this
module talks to the printer: it only translates what was already read.

What the printer really reports:

* Cartridge printers (e.g. XP-230/231): one level per cartridge, 0-100, estimated by the
  cartridge chip.
* EcoTank printers (e.g. L3150): no tank has a sensor. The L3150 of the USB capture
  reported 105 for every colour in all 838 status replies, before and after the cleanings,
  so a value above 100 means "not measured". The only real ink data there is how many
  times each colour was refilled (EEPROM "Ink replacement counter").

The printer's lights are driven by the same error and warning codes, so the app explains
the cause instead of guessing the light pattern; the light given for each code is the usual
one on Epson panels and only a hint (the exact pattern depends on the panel of each model).
"""
import re
from dataclasses import dataclass
from typing import List, Optional

ERROR, WARNING, INFO = "error", "aviso", "info"
_RANK = {ERROR: 0, WARNING: 1, INFO: 2}

# backend ink name -> (Spanish name, swatch colour)
INK_NAMES = {
    "Black": ("Negro", "#1d1d1f"), "Matte Black": ("Negro mate", "#2b2b2b"),
    "Photo Black": ("Negro foto", "#1d1d1f"), "Light Black": ("Gris", "#6b6b6b"),
    "Light Light Black": ("Gris claro", "#a8a8a8"), "Grey": ("Gris", "#6b6b6b"),
    "Light Grey": ("Gris claro", "#a8a8a8"),
    "Cyan": ("Cian", "#00a3e0"), "Light Cyan": ("Cian claro", "#6fd0f5"),
    "Magenta": ("Magenta", "#d6007e"), "Light Magenta": ("Magenta claro", "#f07ac0"),
    "Yellow": ("Amarillo", "#f5d000"), "Dark Yellow": ("Amarillo oscuro", "#c9a800"),
    "Red": ("Rojo", "#d7261e"), "Blue": ("Azul", "#2350c8"), "Orange": ("Naranja", "#f07c00"),
    "Green": ("Verde", "#1f9d55"), "Gloss Optimizer": ("Optimizador de brillo", "#c8c8c8"),
}
INK_ORDER = ["Negro", "Negro mate", "Negro foto", "Cian", "Magenta", "Amarillo"]

PAPER_LIGHT = "Luz de papel encendida"
PAPER_BLINK = "Luz de papel parpadeando"
INK_LIGHT = "Luz de tinta encendida"
INK_BLINK = "Luz de tinta parpadeando"
PADS_LIGHTS = "Luces de papel y tinta parpadeando a la vez o alternadas"
ALL_LIGHTS = "Todas las luces parpadeando"

# backend error text (status element 0x02) -> (severity, title, what to do, usual light)
ERRORS = {
    "Fatal error": (ERROR, "Error fatal",
                    "Apagá la impresora, revisá que nada trabe el carro (papel, tapas, "
                    "restos) y volvé a encenderla. Si sigue, es una falla de hardware.",
                    ALL_LIGHTS),
    "Other I/F is selected": (WARNING, "Otra conexión en uso",
                              "La impresora atiende otra interfaz (Wi-Fi u otro equipo). "
                              "Esperá a que termine.", ""),
    "Cover Open": (ERROR, "Tapa abierta", "Cerrá la tapa o el escáner.", PAPER_BLINK),
    "Paper jam": (ERROR, "Atasco de papel",
                  "Retirá con cuidado el papel trabado y pulsá el botón de papel.", PAPER_BLINK),
    "Ink out": (ERROR, "Sin tinta",
                "Cambiá el cartucho agotado (en tanques: rellená y confirmá la carga en la "
                "impresora).", INK_LIGHT),
    "Paper out": (ERROR, "Sin papel",
                  "Cargá papel y pulsá el botón de papel para seguir.", PAPER_LIGHT),
    "Paper size or paper type or paper path error": (
        ERROR, "Error de tamaño, tipo o ruta del papel",
        "Revisá que el papel cargado coincida con el elegido en la impresión.", PAPER_BLINK),
    "Ink overflow error (Waste ink pad counter overflow)": (
        ERROR, "Almohadillas de tinta residual llenas",
        "La impresora se bloqueó porque el contador llegó al límite. Cambiá o lavá las "
        "almohadillas y reseteá el contador (Inicio › Contadores).", PADS_LIGHTS),
    "Wait return from the tear-off position": (WARNING, "Esperando que el papel vuelva",
                                               "Esperá a que termine el movimiento.", ""),
    "Double Feed": (ERROR, "Doble alimentación",
                    "Entraron dos hojas juntas: retiralas, airea el papel y volvé a cargarlo.",
                    PAPER_BLINK),
    "Cartridge cover is opened error": (ERROR, "Tapa de cartuchos abierta",
                                        "Cerrá la tapa de los cartuchos.", INK_BLINK),
    "Cutter error (Fatal Error)": (ERROR, "Error de la cuchilla", "Apagá y encendé la "
                                   "impresora.", ALL_LIGHTS),
    "Cutter jam error (recoverable)": (ERROR, "Cuchilla trabada", "Retirá el papel "
                                       "trabado.", PAPER_BLINK),
    "Maintenance cartridge is missing error": (ERROR, "Falta la caja de mantenimiento",
                                               "Colocá la caja de mantenimiento.", ""),
    "Rear cover is opened error": (ERROR, "Tapa trasera abierta", "Cerrá la tapa trasera.",
                                   PAPER_BLINK),
    "CD-R tray is out error": (ERROR, "Bandeja de CD fuera de lugar",
                               "Retirá o colocá bien la bandeja de CD.", PAPER_BLINK),
    "Memory Card loading Error": (WARNING, "Error al leer la tarjeta de memoria",
                                  "Retirá la tarjeta y volvé a colocarla.", ""),
    "Tray cover is opened": (ERROR, "Tapa de la bandeja abierta", "Cerrá la tapa.",
                             PAPER_BLINK),
    "Ink cartridge overflow error": (ERROR, "Error de cartucho de tinta",
                                     "Revisá los cartuchos y volvé a colocarlos.", INK_BLINK),
    "Battery abnormal voltage error": (ERROR, "Batería con tensión anormal", "", ""),
    "Battery abnormal temperature error": (ERROR, "Batería con temperatura anormal", "", ""),
    "Battery is empty error": (ERROR, "Batería agotada", "Conectá el cargador.", ""),
    "Initial filling is impossible error": (
        ERROR, "No se pudo hacer la carga inicial de tinta",
        "Revisá que los tanques o cartuchos tengan tinta y repetí la carga inicial.",
        INK_BLINK),
    "Maintenance cartridge cover is opened error": (ERROR, "Tapa de la caja de "
                                                    "mantenimiento abierta", "Cerrala.", ""),
    "Scanner or front cover is opened error": (ERROR, "Escáner o tapa frontal abierta",
                                               "Cerrá el escáner o la tapa frontal.",
                                               PAPER_BLINK),
    "Maintenance request": (ERROR, "La impresora pide servicio",
                            "Suele indicar almohadillas en el límite: revisá los contadores.",
                            PADS_LIGHTS),
    "Printing disable error": (ERROR, "Impresión deshabilitada",
                               "La impresora no acepta trabajos. Apagala y encendela.", ""),
    "Maintenance Box near End error": (WARNING, "Caja de mantenimiento casi llena",
                                       "Prepará el cambio de la caja o de las almohadillas.",
                                       ""),
    "Driver mismatch error": (ERROR, "Driver incorrecto",
                              "La impresora recibió datos de un driver que no es el suyo.", ""),
}

_INK_LOW = re.compile(r"Ink low \((.+)\)")
_CLEANING_OFF = re.compile(r"Cleaning Disabled \((.+)\)")
_COLOURS_ES = {"Black": "negro", "Yellow": "amarillo", "Magenta": "magenta", "Cyan": "cian",
               "Matte Black": "negro mate", "Photo Black": "negro foto", "Red": "rojo",
               "Blue": "azul", "Gloss optimizer": "optimizador de brillo"}

# printer status codes (status element 0x01) that are not "ready" nor "busy"
STATUS_TEXT = {
    0x00: "Error", 0x01: "Imprimiendo sola", 0x02: "Ocupada", 0x03: "Esperando",
    0x04: "En reposo", 0x05: "En pausa", 0x07: "Limpiando",
    0x08: "Sin inicializar (de fábrica)", 0x0A: "Apagándose", 0x0F: "Test de inyectores",
    0x11: "Cargando tinta",
}


@dataclass
class Ink:
    name: str              # Spanish colour name
    swatch: str            # colour to paint it with
    level: Optional[int]   # 0-100, or None when the printer does not measure it
    state: str = ""        # HP: what its sensor says ("bajo", "vacío"...), "" if nothing


@dataclass
class Alert:
    severity: str          # ERROR, WARNING or INFO
    title: str
    action: str = ""
    light: str = ""        # usual light on the printer's panel ("" when none)
    code: str = ""         # what the printer said, untranslated


def _colours(text):
    """'Black or Yellow' -> 'negro o amarillo'."""
    return " o ".join(_COLOURS_ES.get(part.strip(), part.strip().lower())
                      for part in text.split(" or "))


def status_text(status):
    """The printer state in Spanish ('--' when unknown)."""
    code = (status.get("status") or (None, ""))[0]
    if code in STATUS_TEXT:
        return STATUS_TEXT[code]
    return (status.get("status") or ("", "--"))[1] or "--"


def box_text(status, i=1):
    """Waste box i as the printer reports it, in Spanish ('--' when not reported)."""
    raw = str(status.get(f"maintenance_box_{i}", ""))
    for prefix, words in (("not full", "con espacio"), ("near full", "casi lleno"),
                          ("full", "lleno")):
        if raw.startswith(prefix):
            return words
    return raw or "--"


def inks(status) -> List[Ink]:
    """Ink of each colour, black first. level is None for a colour the printer does not
    measure (a tank: the printer reports a value above 100)."""
    result = []
    for entry in status.get("ink_level") or ():
        try:
            _id, _colour, name, ink_name, level = entry
        except (TypeError, ValueError):
            continue
        spanish, swatch = INK_NAMES.get(ink_name, INK_NAMES.get(name, (str(ink_name), "#888888")))
        measured = isinstance(level, int) and 0 <= level <= 100
        result.append(Ink(spanish, swatch, level if measured else None))
    order = {name: i for i, name in enumerate(INK_ORDER)}
    return sorted(result, key=lambda ink: order.get(ink.name, len(order)))


def ink_measured(status) -> Optional[bool]:
    """True if the printer reports real ink levels, False if it reports colours without
    a level (tanks), None if it reports no ink at all."""
    found = inks(status)
    if not found:
        return None
    return any(ink.level is not None for ink in found)


def alerts(status, pads_pct: Optional[float] = None) -> List[Alert]:
    """Everything the printer is warning about, worst first. pads_pct is the fullest
    waste pad in % (from the counters), to warn before the printer locks itself."""
    found: List[Alert] = []
    tanks = ink_measured(status) is False

    code = (status.get("status") or (None, ""))[0]
    errcode = status.get("errcode")
    if errcode:
        text = str(errcode).strip()
        if text in ERRORS:
            severity, title, action, light = ERRORS[text]
            if text == "Ink out" and tanks:
                action = ("En los tanques la impresora no mide la tinta: estima el consumo. "
                          "Rellená el color que falta y confirmá la carga en la impresora.")
            found.append(Alert(severity, title, action, light, text))
        else:
            number = re.search(r"\d+", text)
            found.append(Alert(ERROR, "Error de la impresora sin descripción",
                               "Anotá el código y revisá el panel de la impresora.", "",
                               f"código {number.group()}" if number else text))
    elif code == 0x00:
        found.append(Alert(ERROR, "La impresora está en error",
                           "No informó la causa: mirá sus luces o su pantalla.", "", "Error"))

    jam = status.get("paper_jam")
    if isinstance(jam, str) and jam != "No jams" and not any(a.title == "Atasco de papel"
                                                             for a in found):
        title = {"Paper jammed at ejecting": "Papel trabado al expulsar",
                 "Paper jam in rear ASF or no feed": "Atasco en la entrada trasera o el "
                                                      "papel no entra",
                 "No papers at rear ASF": "Sin papel en la bandeja trasera"}.get(jam, jam)
        found.append(Alert(WARNING, title, "Revisá el recorrido del papel.", PAPER_BLINK, jam))

    for warning in status.get("warning_code") or ():
        text = str(warning)
        low = _INK_LOW.match(text)
        off = _CLEANING_OFF.match(text)
        if low:
            action = ("Prepará el cartucho de repuesto." if not tanks else
                      "En los tanques es una estimación del consumo: mirá el visor y "
                      "rellená si hace falta.")
            found.append(Alert(WARNING, f"Tinta baja ({_colours(low.group(1))})", action,
                               INK_BLINK, text))
        elif off:
            found.append(Alert(WARNING, f"Limpieza deshabilitada ({_colours(off.group(1))})",
                               "Queda poca tinta de ese color para limpiar el cabezal.",
                               INK_BLINK, text))
        elif text == "Black print mode":
            found.append(Alert(INFO, "Imprimiendo solo en negro",
                               "La impresora usa solo el negro hasta que cambies el color "
                               "agotado.", INK_BLINK, text))
        else:
            found.append(Alert(INFO, "Aviso de la impresora sin descripción", "", "", text))

    for i in (1, 2):
        box = str(status.get(f"maintenance_box_{i}", ""))
        where = "principal" if i == 1 else "del platen"
        if box.startswith("full") and not any(a.code.startswith("Ink overflow")
                                              for a in found):
            found.append(Alert(ERROR, f"Depósito de tinta residual {where} lleno",
                               "La impresora va a bloquearse (o ya lo hizo): cambiá o lavá las "
                               "almohadillas y reseteá el contador.", PADS_LIGHTS, box))
        elif box.startswith("near full"):
            found.append(Alert(WARNING, f"Depósito de tinta residual {where} casi lleno",
                               "Planificá el cambio de almohadillas.", "", box))

    if pads_pct is not None and pads_pct >= 90 and not any(
            "residual" in a.title or "Almohadillas" in a.title for a in found):
        found.append(Alert(WARNING, f"Almohadillas al {pads_pct:.0f} %",
                           "Cerca del límite: la impresora se bloqueará al llegar al 100 %.",
                           "", ""))

    return sorted(found, key=lambda a: _RANK[a.severity])


def chip(status, found: List[Alert]):
    """(text, kind) for the status-bar chip; kind is 'ok', 'warn' or 'bad'."""
    errors = [a for a in found if a.severity == ERROR]
    if errors:
        return f"Error: {errors[0].title}", "bad"
    warnings = [a for a in found if a.severity == WARNING]
    if status.get("ready"):
        if warnings:
            return ("Lista · 1 aviso" if len(warnings) == 1
                    else f"Lista · {len(warnings)} avisos"), "warn"
        return "Lista", "ok"
    return status_text(status) if status.get("status") else "Conectada", "warn"


def alert_line(alert: Alert) -> str:
    """One alert as one line of plain text."""
    line = alert.title
    if alert.action:
        line += f": {alert.action}"
    return line


# ---- HP -------------------------------------------------------------------------------
# What an HP reports (hp_backend.py) is not the Epson status block: its words are
# translated here, into the same Alert and Ink shapes, so the window shows both alike.
HP_INKS = {"black": ("Negro", "#1d1d1f"), "cyan": ("Cian", "#00a3e0"),
           "magenta": ("Magenta", "#d6007e"), "yellow": ("Amarillo", "#f5d000"),
           "tricolor": ("Tricolor", "#8a5cc2")}
HP_INK_STATES = {"ok": "con tinta", "low": "bajo", "verylow": "muy bajo",
                 "out": "vacío", "empty": "vacío", "depleted": "vacío",
                 "missing": "falta", "unknown": ""}

HP_CATEGORIES = {
    "ready": "Lista", "processing": "Imprimiendo", "inPowerSave": "En ahorro de energía",
    "scanProcessing": "Escaneando", "busy": "Ocupada", "cancelJob": "Cancelando un trabajo",
    "closeDoorOrCover": "Tapa o puerta abierta", "paperJam": "Atasco de papel",
    "jamInPrinter": "Atasco de papel", "trayEmptyOrOpen": "Sin papel o bandeja abierta",
    "cartridgeMissing": "Falta un cabezal",
    "inkSystemInitializing": "Preparando el sistema de tinta",
    "shuttingDown": "Apagándose", "initializing": "Iniciando", "calibrating": "Calibrando",
}
HP_IPP_STATES = {"idle": "En reposo", "processing": "Imprimiendo", "stopped": "Detenida"}
_WASTE_ACTION = ("La impresora avisa por su cuenta que el absorbente de tinta residual "
                 "(las almohadillas) se llena. HP no documenta un contador ni un reseteo: "
                 "se cambia en el servicio técnico.")
# IPP printer-state-reasons (RFC 8011 / PWG 5100), without the -report/-warning/-error
# suffix -> (title, what to do)
HP_REASONS = {
    "media-empty": ("Sin papel", "Cargá papel en la bandeja de entrada."),
    "media-needed": ("Sin papel", "Cargá papel en la bandeja de entrada."),
    "media-jam": ("Atasco de papel", "Abrí la puerta de acceso y retirá el papel trabado "
                                     "con cuidado."),
    "door-open": ("Tapa o puerta abierta", "Cerrá la puerta de acceso o la tapa."),
    "cover-open": ("Tapa o puerta abierta", "Cerrá la puerta de acceso o la tapa."),
    "interlock-open": ("Tapa o puerta abierta", "Cerrá la puerta de acceso o la tapa."),
    "marker-supply-low": ("Tinta baja", "Mirá el visor de los tanques y rellená el color "
                                        "que falta."),
    "marker-supply-empty": ("Sin tinta", "Rellená el tanque vacío antes de imprimir: sin "
                                         "tinta el cabezal se daña."),
    "marker-waste-almost-full": ("Absorbente de tinta residual casi lleno", _WASTE_ACTION),
    "marker-waste-full": ("Absorbente de tinta residual lleno", _WASTE_ACTION),
    "toner-low": ("Tóner bajo", "Prepará el cartucho de repuesto."),
    "toner-empty": ("Sin tóner", "Cambiá el cartucho de tóner."),
    "input-tray-missing": ("Falta la bandeja de entrada", "Colocá la bandeja."),
    "output-area-full": ("Bandeja de salida llena", "Retirá las hojas impresas."),
    "output-tray-missing": ("Falta la bandeja de salida", "Colocá la bandeja."),
    "offline": ("Fuera de línea", "Revisá la conexión de la impresora."),
    "paused": ("En pausa", "Reanudá la impresora desde su panel o desde Windows."),
    "moving-to-paused": ("Pasando a pausa", ""),
    "shutdown": ("Apagándose", ""),
    "spool-area-full": ("Memoria de trabajos llena", "Esperá a que termine lo que imprime."),
    "connecting-to-device": ("Conectando", ""),
    "other": ("La impresora informa un problema", "Mirá su panel o su página web."),
}
# LEDM ProductStatusAlertID (HP) -> (title, what to do)
HP_LEDM_ALERTS = {
    "closeDoorOrCover": HP_REASONS["door-open"], "paperJam": HP_REASONS["media-jam"],
    "jamInPrinter": HP_REASONS["media-jam"], "trayEmptyOrOpen": HP_REASONS["media-empty"],
    "outOfPaper": HP_REASONS["media-empty"],
    "cartridgeLow": HP_REASONS["marker-supply-low"], "inkLow": HP_REASONS["marker-supply-low"],
    "cartridgeVeryLow": HP_REASONS["marker-supply-low"],
    "cartridgeOut": HP_REASONS["marker-supply-empty"],
    "inkOut": HP_REASONS["marker-supply-empty"],
    "cartridgeMissing": ("Falta un cabezal", "Colocá el cabezal que falta y cerrá el seguro."),
    "printheadMissing": ("Falta un cabezal", "Colocá el cabezal que falta y cerrá el seguro."),
    "printheadProblem": ("Problema con un cabezal", "Sacá el cabezal, revisá que no tenga la "
                                                    "cinta protectora y volvé a colocarlo."),
    "inkSystemFailure": ("Falla del sistema de tinta", "Apagá la impresora, revisá los tubos y "
                                                       "los cabezales y volvé a encenderla."),
    "carriageJam": ("Carro trabado", "Retirá lo que traba el carro y reiniciá la impresora."),
}
_REASON_SUFFIX = re.compile(r"-(report|warning|error)$")
_SEVERITY_OF_SUFFIX = {"error": ERROR, "warning": WARNING, "report": INFO}


def _hp_colour(text):
    import hp_backend
    return hp_backend.colour_word(text)


def hp_inks(info) -> List[Ink]:
    """Ink of an HP, black first. level is None when it gives no percentage (the Smart
    Tank 580 has low-ink sensors, not a level gauge); state says what the sensor says."""
    found = []
    for entry in info.get("inks") or ():
        word = (_hp_colour(entry.get("key")) or _hp_colour(entry.get("label"))
                or _hp_colour(entry.get("colour")))
        name, swatch = HP_INKS.get(word, (str(entry.get("key") or "Tinta"), "#888888"))
        level = entry.get("level")
        level = level if isinstance(level, int) and 0 <= level <= 100 else None
        state = HP_INK_STATES.get(str(entry.get("state", "")).lower(), "")
        found.append(Ink(name, swatch, level, state))
    order = {name: i for i, name in enumerate(INK_ORDER)}
    return sorted(found, key=lambda ink: order.get(ink.name, len(order)))


def hp_status_text(info) -> str:
    state = info.get("state") or {}
    if state.get("category"):
        return HP_CATEGORIES.get(state["category"], state["category"])
    if state.get("ipp"):
        return HP_IPP_STATES.get(state["ipp"], state["ipp"])
    spooler = state.get("spooler")
    if spooler is not None:
        if spooler.get("problem"):
            return f"Windows indica: {spooler['problem']}"
        return "Conectada por USB (estado no informado)"
    return "--"


def hp_status(info) -> dict:
    """A status dict with the keys chip() reads."""
    return {"ready": bool(info.get("ready")), "status": (None, hp_status_text(info))}


def hp_alerts(info) -> List[Alert]:
    """What an HP is warning about, worst first."""
    state = info.get("state") or {}
    found: List[Alert] = []

    def add(severity, title, action, code):
        if not any(a.title == title for a in found):
            found.append(Alert(severity, title, action, "", code))

    for reason in state.get("reasons") or ():
        suffix = _REASON_SUFFIX.search(reason)
        base = _REASON_SUFFIX.sub("", reason)
        severity = _SEVERITY_OF_SUFFIX[suffix.group(1)] if suffix else WARNING
        if base in HP_REASONS:
            title, action = HP_REASONS[base]
            if base == "marker-waste-full":
                severity = ERROR
            add(severity, title, action, reason)
        else:
            add(INFO, "Aviso de la impresora sin descripción", "", reason)
    for alert in state.get("ledm_alerts") or ():
        code, level = alert.get("id", ""), alert.get("severity", "").lower()
        severity = (ERROR if level == "error" else
                    INFO if level in ("info", "informational") else WARNING)
        title, action = HP_LEDM_ALERTS.get(code, ("Aviso de la impresora sin descripción", ""))
        colour = alert.get("colour")
        if colour and title in ("Tinta baja", "Sin tinta"):
            word = HP_INKS.get(_hp_colour(colour), (colour,))[0].lower()
            title = f"{title} ({word})"
        add(severity, title, action, code)
    category = state.get("category", "")
    if category in ("closeDoorOrCover", "paperJam", "jamInPrinter", "trayEmptyOrOpen",
                    "cartridgeMissing") and not any(a.severity == ERROR for a in found):
        title, action = HP_LEDM_ALERTS.get(category, (HP_CATEGORIES[category], ""))
        add(ERROR, title, action, category)
    if not any(a.code.startswith(("marker-supply", "cartridge", "ink")) for a in found):
        for ink in hp_inks(info):
            if ink.state in ("bajo", "muy bajo"):
                add(WARNING, f"Tinta baja ({ink.name.lower()})",
                    "Mirá el visor del tanque y rellená.", "low")
            elif ink.state == "vacío":
                add(ERROR, f"Sin tinta ({ink.name.lower()})", "Rellená el tanque.", "out")
    spooler = state.get("spooler")
    if spooler and spooler.get("problem"):
        add(WARNING, f"Windows indica: {spooler['problem']}",
            "Mirá el panel de la impresora y la cola de Windows.", spooler.get("queue", ""))
    return sorted(found, key=lambda a: _RANK[a.severity])
