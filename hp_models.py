"""HP printers: names, families and the 3D style, from the names Windows gives them.

Pure text handling, no I/O: detect.py uses it, and detection must never touch a printer.

What Windows reports for an HP ink-tank printer (seen on this PC for the Smart Tank 530
and 750, the Ink Tank 310 and 410 and the DeskJet 2700):

* USB vendor id 03F0. The printer is a composite device whose id ends in the serial
  number: USB\\VID_03F0&PID_2A54\\CN09C3S2XG.
* Interface MI_01 is the USB printer class (7/1/2, driver usbprint): the print channel.
  "HP Smart Tank 530 series" / bus name "Smart Tank 530 series".
* MI_02 is HP's vendor "REST" interface (ff/04/01, named "... series(REST)"), with an
  IPP-over-USB alternate setting (7/1/4). MI_03 is another vendor channel (WinUSB).
* The Windows print queue is "HP Smart Tank 530 series" on a USBnnn port.
"""
import re

HP_VENDOR = "VID_03F0"
EPSON_VENDOR = "VID_04B8"

STYLE_EPSON = "epson_l3150"           # 3D model of the Epson tank family
STYLE_EPSON_XP2100 = "epson_xp2100"   # Epson XP-2100 / 2101 / 2105: cartridges 206
STYLE_HP_SMART_TANK_580 = "hp_smart_tank_580"

# Epson models drawn as the XP-2100 (same body, four 206 cartridges). Windows names the
# XP-2101 "EPSON XP-2100 Series", so the backend sees it as XP-2100.
_EPSON_XP2100 = re.compile(r"\bXP-?21(0[0-5]|5[0-5])\b", re.I)

# HP ink-tank families (the ones whose ink is in refillable tanks).
_TANK = re.compile(r"\b(Smart\s*Tank|Ink\s*Tank|DeskJet\s+GT)\b", re.I)


def is_hp_name(name):
    text = (name or "").strip().upper()
    return text.startswith("HP ") or text.startswith("HEWLETT") or text.startswith("HP_")


def clean_model(name):
    """'HP Smart Tank 580-590 series' -> 'HP Smart Tank 580-590';
    'Hewlett-Packard HP LaserJet 1022' -> 'HP LaserJet 1022'; 'Smart Tank 530 series'
    -> 'HP Smart Tank 530'. '' for an empty name."""
    text = re.sub(r"\(.*?\)", "", name or "")          # "(REST)", "(USB)", "(Copiar 2)"
    text = re.sub(r"^\s*Hewlett[-\s]?Packard\s+", "", text, flags=re.I)
    text = re.sub(r"\s+series\s*$", "", text.strip(), flags=re.I).strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return ""
    if not re.match(r"HP\b", text, re.I):
        text = "HP " + text
    return "HP" + text[2:]


def model_from_names(names):
    """The HP model from the names Windows gives one unit, most specific first; ''."""
    for name in names or ():
        if not name or name.upper().startswith("USB") or "PRINTER" == name.upper().strip():
            continue
        cleaned = clean_model(name)
        if cleaned and cleaned.upper() != "HP":
            return cleaned
    return ""


def same_model(a, b):
    """True when two names are the same HP model: a queue 'HP Smart Tank 580-590 series
    (Copiar 1)' and the model 'HP Smart Tank 580-590'."""
    return bool(a and b) and clean_model(a).upper() == clean_model(b).upper()


def is_tank(model):
    return bool(_TANK.search(model or ""))


def is_smart_tank_580_family(model):
    """Smart Tank 580-590 series: 580, 581, 583, 585, 588, 589, 590 (one platform)."""
    return bool(re.search(r"Smart\s*Tank\s*(5[89]\d)\b", model or "", re.I))


def style_for(brand, model=""):
    """3D model to draw. Every HP gets the Smart Tank 580, the only HP model there is;
    an Epson XP-2100 family printer gets its own (cartridges), any other Epson the L3150."""
    if brand == "hp":
        return STYLE_HP_SMART_TANK_580
    if _EPSON_XP2100.search(model or ""):
        return STYLE_EPSON_XP2100
    return STYLE_EPSON


def serial_from_device_id(device_id):
    """Serial number in a USB device id (USB\\VID_03F0&PID_2A54\\CN09C3S2XG), or '' when
    the last part is a Windows-made id (it has '&' in it: 6&191aa7b4&0&0001)."""
    last = (device_id or "").replace("/", "\\").split("\\")[-1]
    return last if last and "&" not in last and len(last) >= 6 else ""
