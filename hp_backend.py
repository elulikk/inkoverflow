"""Reads an HP printer (built around the HP Smart Tank 580). Read only: nothing here can
change a setting, print a page or touch a counter.

Where each figure comes from, most reliable first:

* USB, from Windows only (pnp.py): model, serial number (the last part of the USB device
  id, USB\\VID_03F0&PID_xxxx\\CN...), USB product id, the print queue. The printer is
  never opened by this app over USB. HP answers status queries over its vendor "REST"
  USB interface, not over the print interface: HTTP or PJL text sent to the print
  interface is printed as a page of garbage ("GET /cdm/system/v1/status HTTP/1.1"), so
  this module never writes to it. Over USB the state comes from the Windows queue.
* Network (the printer's IP, typed by the user or taken from its Windows TCP/IP port):
  - IPP Get-Printer-Attributes (RFC 8011; every AirPrint/Mopria printer, the Smart Tank
    580 included, answers it on port 631, path /ipp/print): make and model, state and
    state reasons (paper out, jam, door open, ink low...), marker levels and colours,
    firmware, the IEEE 1284 device id (with the serial number).
  - LEDM, HP's embedded web server XML (port 80, /DevMgmt/*.xml, the same files the
    printer's web page and HPLIP read): serial and product number, firmware, status
    category and alerts, each ink and printhead with its state and level, and the usage
    counters (pages, colour and mono pages, scans, copies, jams).

Waste ink: HP does not publish a waste-ink (absorber) counter for its tank printers, no
protocol above reports one, and HP documents no reset. The only waste signal that can be
read is the IPP state reason "marker-waste-...", shown as an alert when it comes. This
module has no reset and must never get one that has not been verified on a printer.
"""
import http.client
import ipaddress
import re
import struct
import xml.etree.ElementTree as ET

import hp_models
import hp_usb

TIMEOUT = 4.0
IPP_PATHS = ("/ipp/print", "/ipp/printer", "/ipp")
LEDM_FILES = {
    "config": "/DevMgmt/ProductConfigDyn.xml",
    "status": "/DevMgmt/ProductStatusDyn.xml",
    "consumables": "/DevMgmt/ConsumableConfigDyn.xml",
    "usage": "/DevMgmt/ProductUsageDyn.xml",
}
IPP_ATTRIBUTES = (
    "printer-make-and-model", "printer-device-id", "printer-state", "printer-state-reasons",
    "printer-state-message", "printer-info", "printer-name", "printer-location",
    "printer-uuid", "printer-firmware-string-version", "printer-firmware-version",
    "marker-names", "marker-colors", "marker-levels", "marker-low-levels",
    "marker-high-levels", "marker-types", "printer-supply-description",
    "printer-up-time", "printer-more-info",
)

NO_RESET = ("HP no publica un contador de almohadillas (absorbente de tinta) para sus "
            "impresoras de tanque, ni un reseteo documentado. InkFlow no escribe nada en "
            "una HP: el reseteo y la copia de contadores quedan deshabilitados.")


class HpError(RuntimeError):
    pass


# ---- address ---------------------------------------------------------------------------
def parse_host(text):
    """(host, port or None) from what the user typed: an IP or a host name, optionally
    with :port. Raises HpError for anything else (no scheme, no path, no spaces)."""
    text = (text or "").strip()
    port = None
    match = re.fullmatch(r"(.+?):(\d{1,5})", text)
    if match and not text.count(":") > 1:
        text, port = match.group(1), int(match.group(2))
    try:
        ipaddress.ip_address(text)
        return text, port
    except ValueError:
        pass
    if re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", text):
        return text, port
    raise HpError(f"Dirección no válida: «{text}». Escribí la IP de la impresora, "
                  "por ejemplo 192.168.0.25.")


# ---- HTTP --------------------------------------------------------------------------------
def _request(host, port, method, path, body=None, headers=None, timeout=TIMEOUT):
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        reply = conn.getresponse()
        data = reply.read(2_000_000)
        return reply.status, data
    except (OSError, http.client.HTTPException) as exc:
        raise HpError(f"{host}:{port}{path}: {exc}") from exc
    finally:
        conn.close()


def http_get(host, port, path, timeout=TIMEOUT):
    status, data = _request(host, port, "GET", path, timeout=timeout)
    if status != 200:
        raise HpError(f"{path}: HTTP {status}")
    return data


# ---- IPP ---------------------------------------------------------------------------------
_TAG_INT, _TAG_BOOL, _TAG_ENUM = 0x21, 0x22, 0x23
_TAG_TEXT_LANG, _TAG_NAME_LANG = 0x35, 0x36
_STRING_TAGS = {0x41, 0x42, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49}
GET_PRINTER_ATTRIBUTES = 0x000B


def _attr(tag, name, value):
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return (bytes([tag]) + struct.pack(">H", len(name)) + name.encode("ascii")
            + struct.pack(">H", len(raw)) + raw)


def ipp_request(uri, attributes=IPP_ATTRIBUTES, request_id=1):
    """An IPP/1.1 Get-Printer-Attributes request (read only)."""
    out = struct.pack(">BBHI", 1, 1, GET_PRINTER_ATTRIBUTES, request_id) + b"\x01"
    out += _attr(0x47, "attributes-charset", "utf-8")
    out += _attr(0x48, "attributes-natural-language", "en")
    out += _attr(0x45, "printer-uri", uri)
    for i, name in enumerate(attributes):
        out += _attr(0x44, "requested-attributes" if i == 0 else "", name)
    return out + b"\x03"


def ipp_parse(data):
    """(status code, {name: [values]}) of an IPP response, every group merged. Integers
    and enums are ints, booleans bools, strings str; other values stay bytes."""
    if len(data) < 9:
        raise HpError("Respuesta IPP demasiado corta.")
    _major, _minor, status, _rid = struct.unpack(">BBHI", data[:8])
    attrs, pos, last = {}, 8, None
    try:
        while pos < len(data):
            tag = data[pos]
            pos += 1
            if tag == 0x03:
                break
            if tag < 0x10:          # a new attribute group
                continue
            (nlen,) = struct.unpack(">H", data[pos:pos + 2])
            name = data[pos + 2:pos + 2 + nlen].decode("ascii", "replace")
            pos += 2 + nlen
            (vlen,) = struct.unpack(">H", data[pos:pos + 2])
            raw = data[pos + 2:pos + 2 + vlen]
            if len(raw) != vlen:
                raise HpError("Respuesta IPP cortada.")
            pos += 2 + vlen
            if tag in (_TAG_INT, _TAG_ENUM) and vlen == 4:
                value = struct.unpack(">i", raw)[0]
            elif tag == _TAG_BOOL and vlen == 1:
                value = bool(raw[0])
            elif tag in _STRING_TAGS:
                value = raw.decode("utf-8", "replace")
            elif tag in (_TAG_TEXT_LANG, _TAG_NAME_LANG) and vlen >= 4:
                (llen,) = struct.unpack(">H", raw[:2])
                value = raw[4 + llen:].decode("utf-8", "replace")
            else:
                value = raw
            if nlen:
                last = name
                attrs.setdefault(name, []).append(value)
            elif last:
                attrs[last].append(value)
    except struct.error as exc:
        raise HpError("Respuesta IPP mal formada.") from exc
    return status, attrs


def read_ipp(host, port=631, timeout=TIMEOUT):
    """{name: [values]} of the printer, from the first IPP path that answers."""
    errors = []
    for path in IPP_PATHS:
        body = ipp_request(f"ipp://{host}:{port}{path}")
        try:
            status, data = _request(host, port, "POST", path, body,
                                    {"Content-Type": "application/ipp"}, timeout)
        except HpError as exc:
            errors.append(str(exc))
            break               # nothing listens: the other paths will not answer either
        if status != 200:
            errors.append(f"{path}: HTTP {status}")
            continue
        code, attrs = ipp_parse(data)
        if code >= 0x0400:
            errors.append(f"{path}: IPP 0x{code:04X}")
            continue
        return attrs
    raise HpError("IPP: " + "; ".join(errors))


def parse_device_id(text):
    """IEEE 1284 device id 'MFG:HP;MDL:Smart Tank 580-590 series;SN:CN..;' ->
    {'MFG': 'HP', 'MDL': ..., 'SN': ...}."""
    fields = {}
    for part in (text or "").split(";"):
        if ":" in part:
            key, value = part.split(":", 1)
            fields[key.strip().upper()] = value.strip()
    aliases = {"MANUFACTURER": "MFG", "MODEL": "MDL", "COMMAND SET": "CMD",
               "SERIALNUMBER": "SN", "SERN": "SN"}
    for long, short in aliases.items():
        if long in fields and short not in fields:
            fields[short] = fields[long]
    return fields


_IPP_STATES = {3: "idle", 4: "processing", 5: "stopped"}


def ipp_to_info(attrs):
    """The part of the info dict that IPP gives."""
    first = lambda name, default="": (attrs.get(name) or [default])[0]
    device_id = parse_device_id(first("printer-device-id"))
    names, colours = attrs.get("marker-names") or [], attrs.get("marker-colors") or []
    levels, types = attrs.get("marker-levels") or [], attrs.get("marker-types") or []
    lows = attrs.get("marker-low-levels") or []
    inks = []
    for i, name in enumerate(names):
        level = levels[i] if i < len(levels) and isinstance(levels[i], int) else -2
        low = lows[i] if i < len(lows) and isinstance(lows[i], int) else None
        if 0 <= level <= 100:
            state = "low" if (low is not None and level <= low) else "ok"
            value = level
        else:
            # Printer MIB: -3 = some ink left, unknown amount; -1/-2 = not known
            state, value = ("ok" if level == -3 else ""), None
        inks.append({"key": str(name), "colour": colours[i] if i < len(colours) else "",
                     "kind": types[i] if i < len(types) else "", "level": value,
                     "state": state})
    reasons = [str(r) for r in attrs.get("printer-state-reasons") or () if str(r) != "none"]
    firmware = first("printer-firmware-string-version") or first("printer-firmware-version")
    if isinstance(firmware, bytes):
        firmware = firmware.hex()
    return {
        "model": first("printer-make-and-model") or device_id.get("MDL", ""),
        "serial_number": device_id.get("SN", ""),
        "firmware_version": str(firmware or ""),
        "device_id": device_id,
        "ipp_state": _IPP_STATES.get(first("printer-state", 0), ""),
        "ipp_reasons": reasons,
        "ipp_message": str(first("printer-state-message") or ""),
        "inks": inks,
    }


# ---- LEDM --------------------------------------------------------------------------------
def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _find(node, *names):
    """First descendant whose local name is the last of `names`, below a chain of
    ancestors with the other names (any depth between them)."""
    if node is None:
        return None
    if not names:
        return node
    for child in node.iter():
        if child is not node and _local(child.tag) == names[0]:
            found = _find(child, *names[1:])
            if found is not None:
                return found
    return None


def _text(node, *names):
    found = _find(node, *names)
    return (found.text or "").strip() if found is not None and found.text else ""


def _xml(data):
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise HpError(f"XML no válido: {exc}") from exc


def _int(text):
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def ledm_config(root):
    info = _find(root, "ProductInformation")
    firmware = ""
    if info is not None:
        for child in info:
            if _local(child.tag) == "Version":
                firmware = _text(child, "Revision")
    return {"model": _text(info, "MakeAndModel"), "serial_number": _text(info, "SerialNumber"),
            "product_number": _text(info, "ProductNumber"), "firmware_version": firmware,
            "firmware_date": _text(_find(info, "Version"), "Date") if info is not None else ""}


def ledm_status(root):
    alerts = []
    for node in root.iter():
        if _local(node.tag) != "Alert":
            continue
        alerts.append({"id": _text(node, "ProductStatusAlertID"),
                       "severity": _text(node, "Severity"),
                       "colour": _text(node, "AlertDetailsMarkerColor")
                       or _text(node, "MarkerColor")})
    return {"category": _text(root, "StatusCategory"), "alerts": alerts}


def ledm_consumables(root):
    inks, heads = [], []
    for node in root.iter():
        if _local(node.tag) != "ConsumableInfo":
            continue
        kind = _text(node, "ConsumableTypeEnum").lower()
        entry = {"key": _text(node, "MarkerColor") or _text(node, "ConsumableLabelCode"),
                 "label": _text(node, "ConsumableLabelCode"),
                 "level": _int(_text(node, "ConsumablePercentageLevelRemaining")),
                 "state": _text(node, "ConsumableState") or _text(node, "ConsumableLifeState"),
                 "model": _text(node, "ConsumableSelectibilityNumber"), "kind": kind}
        if entry["level"] is not None and not 0 <= entry["level"] <= 100:
            entry["level"] = None
        (heads if "head" in kind else inks).append(entry)
    return {"inks": inks, "printheads": heads}


def ledm_usage(root):
    printer = _find(root, "PrinterSubunit")
    printer = root if printer is None else printer
    scanner = _find(root, "ScannerEngineSubunit")
    copier = _find(root, "CopyApplicationSubunit")
    value = lambda node, name: _int(_text(node, name)) if node is not None else None
    return {"total": value(printer, "TotalImpressions"),
            "mono": value(printer, "MonochromeImpressions"),
            "color": value(printer, "ColorImpressions"),
            "jams": value(printer, "JamEvents"),
            "mispicks": value(printer, "MispickEvents"),
            "scans": value(scanner, "ScanImages"),
            "copies": value(copier, "TotalImpressions")}


def read_ledm(host, port=80, timeout=TIMEOUT):
    """What the LEDM files give; a file that is missing is left out. HpError when the
    printer serves none of them."""
    parsers = {"config": ledm_config, "status": ledm_status,
               "consumables": ledm_consumables, "usage": ledm_usage}
    out, errors = {}, []
    for key, path in LEDM_FILES.items():
        try:
            out[key] = parsers[key](_xml(http_get(host, port, path, timeout)))
        except HpError as exc:
            errors.append(str(exc))
            if not out and "HTTP" not in str(exc):
                break           # the web server does not answer at all
    if not out:
        raise HpError("LEDM: " + "; ".join(errors))
    return out


# ---- the whole reading -------------------------------------------------------------------
def usb_identity(printer):
    """Info from what Windows says about a USB unit (pnp.UsbPrinter); no I/O."""
    return {"model": hp_models.model_from_names(printer.names),
            "serial_number": printer.serial or "", "usb_pid": printer.pid,
            "usb_names": list(printer.names), "usb_ports": list(printer.ports)}


_REST_LEVEL_STATES = {"ok": "ok", "low": "low", "verylow": "verylow", "veryLow": "verylow",
                      "empty": "empty", "out": "out", "missing": "missing"}


def rest_to_network(data):
    """The USB REST answers (hp_usb.read_all) in the shape of a LEDM reading, so that
    build_info treats both the same. Ink tanks have a percentage; the cartridges of a
    tank printer are its printheads."""
    identity = data.get("identity") or {}
    names = identity.get("makeAndModel") or {}
    config = {"model": names.get("name") or names.get("base") or "",
              "serial_number": identity.get("serialNumber", ""),
              "product_number": identity.get("productNumber", ""),
              "firmware_version": identity.get("firmwareVersion", ""),
              "firmware_date": identity.get("firmwareDateCode", "")}
    alerts = []
    for alert in (data.get("alerts") or {}).get("alerts") or ():
        alerts.append({"id": str(alert.get("stringId") or alert.get("category") or ""),
                       "severity": str(alert.get("severity", "")),
                       "colour": str(alert.get("colorCode") or alert.get("color") or "")})
    status = {"category": str((data.get("status") or {}).get("status", "")), "alerts": alerts}
    inks, heads = [], []
    for supply in (data.get("supplies") or {}).get("suppliesList") or ():
        key = supply.get("supplyColorCode") or "".join(supply.get("colors") or ())
        state = supply.get("levelState") or supply.get("supplyState") or ""
        entry = {"key": key, "label": key, "model": supply.get("selectabilityNumber", ""),
                 "state": _REST_LEVEL_STATES.get(state, state)}
        if supply.get("supplyType") == "inkTank":
            level = supply.get("percentLifeDisplay")
            entry.update(level=level if isinstance(level, int) and 0 <= level <= 100 else None,
                         kind="ink")
            inks.append(entry)
        else:
            entry.update(level=None, kind="printhead")
            heads.append(entry)
    printed = ((data.get("counters") or {}).get("printUsage") or {}).get("impressions") or {}
    usage = {"total": printed.get("total"), "mono": printed.get("monochrome"),
             "color": printed.get("color")}
    return {"ledm": {"config": config, "status": status,
                     "consumables": {"inks": inks, "printheads": heads}, "usage": usage},
            "rest": True}


def _merge_inks(ledm_inks, ipp_inks):
    """LEDM first (it has the HP state words); IPP fills in a missing level."""
    if not ledm_inks:
        return ipp_inks
    by_colour = {}
    for ink in ipp_inks:
        by_colour.setdefault(colour_word(ink["key"]) or colour_word(ink["colour"]), ink)
    for ink in ledm_inks:
        other = by_colour.get(colour_word(ink["key"]) or colour_word(ink["label"]))
        if other and ink["level"] is None and other["level"] is not None:
            ink["level"] = other["level"]
    return ledm_inks


_COLOUR_WORDS = (("tri", "tricolor"), ("cmy", "tricolor"), ("black", "black"),
                 ("#000000", "black"), ("cyan", "cyan"), ("#00ffff", "cyan"),
                 ("magenta", "magenta"), ("#ff00ff", "magenta"), ("yellow", "yellow"),
                 ("#ffff00", "yellow"))
_LETTERS = {"K": "black", "C": "cyan", "M": "magenta", "Y": "yellow", "CMY": "tricolor"}


def colour_word(text):
    """'Black ink' / '#000000' / 'K' -> 'black' ('' when unknown)."""
    raw = (text or "").strip()
    if raw.upper() in _LETTERS:
        return _LETTERS[raw.upper()]
    low = raw.lower()
    if low.count("#") > 1:
        return "tricolor"
    for needle, word in _COLOUR_WORDS:
        if needle in low:
            return word
    return ""


def read_network(host_text, timeout=TIMEOUT):
    """Everything the printer serves over the network. HpError if neither IPP nor LEDM
    answers."""
    host, port = parse_host(host_text)
    raw, errors = {}, []
    try:
        raw["ipp"] = ipp_to_info(read_ipp(host, port or 631, timeout))
    except HpError as exc:
        errors.append(str(exc))
    try:
        raw["ledm"] = read_ledm(host, port or 80, timeout)
    except HpError as exc:
        errors.append(str(exc))
    if not raw:
        raise HpError(f"La HP no responde en {host_text}: " + " · ".join(errors))
    return raw, errors


def build_info(identity=None, network=None, host="", network_errors=(), spooler=None):
    """The info dict the window shows, from the USB identity, the network reading and
    the Windows queue state (spooler: {'queue', 'jobs', 'problem'} or None)."""
    identity, network = identity or {}, network or {}
    ipp, ledm = network.get("ipp") or {}, network.get("ledm") or {}
    config, status = ledm.get("config") or {}, ledm.get("status") or {}
    consumables = ledm.get("consumables") or {}

    def pick(key):
        for source in (config, ipp, identity):
            if source.get(key):
                return source[key]
        return ""

    model = hp_models.clean_model(pick("model")) or identity.get("model") or "HP"
    state = {"category": status.get("category", ""), "ipp": ipp.get("ipp_state", ""),
             "reasons": list(ipp.get("ipp_reasons") or ()),
             "message": ipp.get("ipp_message", ""),
             "ledm_alerts": list(status.get("alerts") or ()),
             "spooler": dict(spooler) if spooler else None}
    ready = None
    if state["category"]:
        ready = state["category"] in ("ready", "inPowerSave", "processing")
    elif state["ipp"]:
        ready = state["ipp"] in ("idle", "processing") and not any(
            r.endswith("-error") for r in state["reasons"])
    elif spooler is not None:
        ready = not spooler.get("problem")
    rest = bool(network.get("rest"))
    via = [name for name, ok in (("USB (Windows)", bool(identity)), ("USB (REST)", rest),
                                 ("IPP", bool(ipp)), ("LEDM", bool(ledm) and not rest))
           if ok]
    return {
        "brand": "hp", "model": model, "serial_number": pick("serial_number"),
        "firmware_version": pick("firmware_version"),
        "product_number": config.get("product_number", ""),
        "host": host, "via": via, "network_errors": list(network_errors),
        "usb": {k: identity[k] for k in ("usb_pid", "usb_names", "usb_ports") if k in identity},
        "device_id": ipp.get("device_id") or {},
        "state": state, "ready": ready,
        "inks": _merge_inks(consumables.get("inks") or [], ipp.get("inks") or []),
        "printheads": consumables.get("printheads") or [],
        "usage": ledm.get("usage") or {},
        "is_tank": hp_models.is_tank(model),
        # same keys as the Epson reading, for the code shared by both (test page)
        "printer_status": {"ready": bool(ready)},
    }


def read(printer=None, host="", spooler=None, timeout=TIMEOUT, usb_rest=True):
    """Read an HP: `printer` is the pnp.UsbPrinter Windows sees (or None), `host` its
    network address ('' when unknown). Only reads. HpError when there is nothing at all.
    usb_rest=False skips the USB REST interface (tests, or a machine without WinUSB)."""
    identity = usb_identity(printer) if printer is not None else None
    network, errors = None, []
    if host:
        try:
            network, errors = read_network(host, timeout)
        except HpError as exc:
            if identity is None:
                raise
            errors = [str(exc)]
    if network is None and identity is not None and usb_rest:
        # No network (a USB-only model, or no IP): ask the printer through its USB REST
        # interface. If that is busy (HP Smart open) the Windows identity still shows.
        try:
            network = rest_to_network(hp_usb.read_all())
        except hp_usb.NoInterface:
            pass
        except (hp_usb.UsbRestError, OSError) as exc:
            errors = [f"USB: {exc}"]
    if identity is None and network is None:
        raise HpError("No hay ninguna HP por USB ni una dirección de red para leerla.")
    return build_info(identity, network, host if network and not network.get("rest") else "",
                      errors, spooler)

