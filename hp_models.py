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
STYLE_HP_SMART_TANK_210 = "hp_smart_tank_210"   # print-only: no scanner, no display
STYLE_HP_INK_TANK = "hp_ink_tank_415"   # Ink Tank 310 / 315 / Wireless 410 / 415...
STYLE_HP_DESKJET_2700 = "hp_deskjet_2775"   # DeskJet 2700 family: cartridges 667
STYLE_CANON_G = "canon_g3110"           # Canon PIXMA G series (MegaTank)
STYLE_BROTHER_TANK = "brother_t420w"    # Brother InkBenefit Tank (DCP-T220 / T420W...)
# mono lasers (view3d/printers/laser.py): each family as a printer and a multifunction
STYLE_HP_LASERJET = "hp_laserjet_m111"
STYLE_HP_LASERJET_MFP = "hp_laserjet_m141"
STYLE_BROTHER_HL1212W = "brother_hl1212w"
STYLE_BROTHER_DCP1612W = "brother_dcp1612w"
STYLE_PANTUM_P2500 = "pantum_p2500w"
STYLE_PANTUM_M6550 = "pantum_m6550nw"
STYLE_SAMSUNG_M2020 = "samsung_m2020w"
STYLE_SAMSUNG_M2070 = "samsung_m2070w"

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


def is_smart_tank_210_family(model):
    """Smart Tank 210-220 series (print only): 210, 211, 212, 213, 215, 216, 220, 221...
    (the Windows name is 'Smart Tank 210-220 series'; 'Smart Tank 2xx' is the same body)."""
    return bool(re.search(r"Smart\s*Tank\s*2\d\d\b", model or "", re.I))


def is_ink_tank_family(model):
    """Ink Tank 310 / 315 / 318 / 319 and Ink Tank Wireless 410 / 415 / 418 / 419 (one body,
    the tank unit on the right). Windows names them 'HP Ink Tank 310 series' and 'HP Ink
    Tank Wireless 410 series'."""
    return bool(re.search(r"Ink\s*Tank\s*(Wireless\s*)?(31\d|41\d)\b", model or "", re.I))


def is_deskjet_2700_family(model):
    """DeskJet 2700 series (2710, 2720, 2752, 2755...) and DeskJet Ink Advantage 2775 /
    2776 / 2778 / 2789: one body with two cartridges. Windows says 'HP DeskJet 2700 series'."""
    return bool(re.search(r"DeskJet\s*(Ink\s*Advantage\s*)?27\d\d\b", model or "", re.I))


def laserjet_m110_style(model):
    """LaserJet M110-M111 (printer) or LaserJet MFP M140-M141 (with scanner). Any other
    LaserJet is drawn as one of them too (with the scanner when it is an MFP); '' for a
    model that is not a LaserJet."""
    text = model or ""
    found = re.search(r"LaserJet\s*(MFP\s*)?M1([14])\d[a-z]*\b", text, re.I)
    if found:
        mfp = bool(found.group(1)) or found.group(2) == "4"
    elif re.search(r"LaserJet", text, re.I):
        mfp = bool(re.search(r"\bMFP\b", text, re.I))
    else:
        return ""
    return STYLE_HP_LASERJET_MFP if mfp else STYLE_HP_LASERJET


def _laser_style(brand, model):
    """The mono laser models of the other makers ('' when the model is not one of them):
    Brother HL-1200 / DCP-1600, Pantum P2500 / M6500 and Samsung Xpress M2020 / M2070
    families (the multifunction twin is the one with the scanner)."""
    text = model or ""
    if brand == "brother":
        if re.search(r"\bHL-?1[12]\d\d", text, re.I):
            return STYLE_BROTHER_HL1212W
        if re.search(r"\bDCP-?1[56]\d\d", text, re.I):
            return STYLE_BROTHER_DCP1612W
    if brand == "pantum":
        return STYLE_PANTUM_M6550 if re.search(r"\bM6\d\d\d", text, re.I) else STYLE_PANTUM_P2500
    if brand == "samsung":
        return STYLE_SAMSUNG_M2070 if re.search(r"\bM20[67]\d", text, re.I) else STYLE_SAMSUNG_M2020
    return ""


def style_for(brand, model=""):
    """3D model to draw. An HP gets the model of its family (Smart Tank 210, Ink Tank,
    DeskJet 2700, LaserJet M110 / M140), any other HP the Smart Tank 580; an Epson XP-2100
    family printer gets its own (cartridges), any other Epson the L3150. Canon has one
    model; Brother, Pantum and Samsung one per family (the Brother ink tank by default)."""
    if brand == "hp":
        if is_smart_tank_210_family(model):
            return STYLE_HP_SMART_TANK_210
        if is_ink_tank_family(model):
            return STYLE_HP_INK_TANK
        if is_deskjet_2700_family(model):
            return STYLE_HP_DESKJET_2700
        return laserjet_m110_style(model) or STYLE_HP_SMART_TANK_580
    if brand == "canon":
        return STYLE_CANON_G
    if brand in ("brother", "pantum", "samsung"):
        return _laser_style(brand, model) or STYLE_BROTHER_TANK
    if _EPSON_XP2100.search(model or ""):
        return STYLE_EPSON_XP2100
    return STYLE_EPSON


def serial_from_device_id(device_id):
    """Serial number in a USB device id (USB\\VID_03F0&PID_2A54\\CN09C3S2XG), or '' when
    the last part is a Windows-made id (it has '&' in it: 6&191aa7b4&0&0001)."""
    last = (device_id or "").replace("/", "\\").split("\\")[-1]
    return last if last and "&" not in last and len(last) >= 6 else ""
