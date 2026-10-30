"""Scanning through WIA (Windows Image Acquisition), the same path the Windows
"Fax and Scan" app uses. Only the scanner part of a multifunction printer is touched:
no D4 session is opened on the printer.

Run from a worker thread: each call initialises COM for that thread.
"""
from dataclasses import dataclass
from pathlib import Path

WIA_SCANNER = 1
FORMAT_PNG = "{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}"
FORMAT_BMP = "{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}"
# WIA item properties
DATA_TYPE, INTENT = 4103, 6146
X_RES, Y_RES, X_START, Y_START, X_EXTENT, Y_EXTENT = 6147, 6148, 6149, 6150, 6151, 6152
COLOR = 3  # WIA_DATA_COLOR
INTENT_COLOR = 1


@dataclass
class Scanner:
    id: str
    name: str


def _in_com(fn, *args):
    """Run fn inside COM for this thread; every COM object fn made is released before
    COM is closed (otherwise pywin32 complains when they are freed later)."""
    import gc
    import pythoncom
    pythoncom.CoInitialize()
    try:
        return fn(*args)
    finally:
        gc.collect()
        pythoncom.CoUninitialize()


def _prop(props, pid):
    for index in range(1, props.Count + 1):
        prop = props.Item(index)
        if prop.PropertyID == pid:
            return prop
    return None


def _set(props, pid, value):
    """Set a property if the driver has it; some drivers refuse some values."""
    prop = _prop(props, pid)
    if prop is None:
        return False
    try:
        prop.Value = value
        return True
    except Exception:
        return False


def list_scanners():
    """Scanners Windows offers through WIA (connected or on the network)."""
    return _in_com(_list)


def _list():
    import win32com.client
    manager = win32com.client.Dispatch("WIA.DeviceManager")
    found = []
    for index in range(1, manager.DeviceInfos.Count + 1):
        info = manager.DeviceInfos.Item(index)
        if info.Type != WIA_SCANNER:
            continue
        name = _prop(info.Properties, 7)  # WIA_DIP_DEV_NAME
        found.append(Scanner(str(info.DeviceID), str(name.Value) if name else str(info.DeviceID)))
    return found


def pick(scanners, model=""):
    """The scanner that most likely belongs to the printer in use."""
    if not scanners:
        return None
    words = [w for w in model.upper().replace("-", " ").split() if len(w) > 2]
    for scanner in scanners:
        name = scanner.name.upper().replace("-", " ")
        if words and all(w in name for w in words):
            return scanner
    return scanners[0] if len(scanners) == 1 else None


def scan(device_id, path, dpi=300):
    """Scan the whole glass in colour and save it to `path` (PNG or BMP, whatever the
    driver gives; the extension is fixed accordingly). Returns the saved path."""
    return _in_com(_scan, device_id, Path(path), dpi)


def _scan(device_id, path, dpi):
    import win32com.client
    manager = win32com.client.Dispatch("WIA.DeviceManager")
    device = None
    for index in range(1, manager.DeviceInfos.Count + 1):
        info = manager.DeviceInfos.Item(index)
        if info.DeviceID == device_id:
            device = info.Connect()
            break
    if device is None:
        raise RuntimeError("El escáner ya no está disponible: ¿se desconectó o apagó?")
    item = device.Items.Item(1)
    props = item.Properties
    _set(props, INTENT, INTENT_COLOR)
    _set(props, DATA_TYPE, COLOR)
    _set(props, X_RES, dpi)
    _set(props, Y_RES, dpi)
    _set(props, X_START, 0)
    _set(props, Y_START, 0)
    for pid in (X_EXTENT, Y_EXTENT):  # the whole glass, at this resolution
        prop = _prop(props, pid)
        if prop is not None:
            try:
                prop.Value = prop.SubTypeMax
            except Exception:
                pass
    try:
        image = item.Transfer(FORMAT_PNG)
    except Exception:
        image = item.Transfer(FORMAT_BMP)
    ext = {FORMAT_PNG: ".png", FORMAT_BMP: ".bmp"}.get(str(image.FormatID).upper(),
                                                      "." + str(image.FileExtension))
    path = path.with_suffix(ext.lower())
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()  # WIA refuses to overwrite
    image.SaveFile(str(path))
    return path
