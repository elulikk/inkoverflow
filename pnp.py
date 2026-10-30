"""Which Epson and HP printers Windows has plugged in right now, and what it calls them.

This only reads the PnP device registry that Windows keeps (SetupAPI and cfgmgr32
properties). It never opens the printer, never opens a D4 session and never sends a
byte, so it is safe to call at any moment, even while the printer prints, ejects or
cleans. A printer that is unplugged or switched off is not "present": the stale entries of
printers that used to be attached are skipped by the DIGCF_PRESENT flag.

The model comes from the names Windows stores for the USB printer interface (for example
"EPSON L3150 Series") and for its parent USB device (the product string of the printer,
"L3150 Series"), not from the Windows print queues, which pile up for printers that are
gone.
"""
import ctypes
import ctypes.wintypes as wt
import re
import struct
import sys
import uuid
from dataclasses import dataclass

EPSON_VENDOR = "VID_04B8"
HP_VENDOR = "VID_03F0"
#: Device interface class of USB printers (the class the maintenance transport opens).
USBPRINT_GUID_TEXT = "28d78fad-5a12-11d1-ae5b-0000f803a8c2"

DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10
CR_SUCCESS = 0
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class _Guid(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, text):
        raw = uuid.UUID(text).bytes
        return cls(int.from_bytes(raw[0:4], "big"), int.from_bytes(raw[4:6], "big"),
                   int.from_bytes(raw[6:8], "big"), (ctypes.c_ubyte * 8)(*raw[8:16]))


class _PropertyKey(ctypes.Structure):
    _fields_ = [("fmtid", _Guid), ("pid", wt.ULONG)]


class _InterfaceData(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("InterfaceClassGuid", _Guid), ("Flags", wt.DWORD),
                ("Reserved", ctypes.POINTER(ctypes.c_ulong))]


class _DevInfoData(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("ClassGuid", _Guid), ("DevInst", wt.DWORD),
                ("Reserved", ctypes.POINTER(ctypes.c_ulong))]


_FRIENDLY_NAME = _PropertyKey(_Guid.parse("a45c254e-df1c-4efd-8020-67d146a850e0"), 14)
_BUS_REPORTED_DESC = _PropertyKey(_Guid.parse("540b947e-8b40-45bc-a8a2-6a0b894cbda2"), 4)

_dlls = None


def _api():
    global _dlls
    if _dlls is None:
        setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
        cfgmgr = ctypes.WinDLL("cfgmgr32", use_last_error=True)
        setupapi.SetupDiGetClassDevsW.restype = wt.HANDLE
        setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.c_void_p, wt.LPCWSTR, wt.HWND, wt.DWORD]
        setupapi.SetupDiEnumDeviceInterfaces.restype = wt.BOOL
        setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
            wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p]
        setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wt.BOOL
        setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
            wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD,
            ctypes.POINTER(wt.DWORD), ctypes.POINTER(_DevInfoData)]
        setupapi.SetupDiDestroyDeviceInfoList.restype = wt.BOOL
        setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wt.HANDLE]
        cfgmgr.CM_Get_Parent.restype = ctypes.c_ulong
        cfgmgr.CM_Get_Parent.argtypes = [ctypes.POINTER(wt.DWORD), wt.DWORD, ctypes.c_ulong]
        cfgmgr.CM_Get_DevNode_PropertyW.restype = ctypes.c_ulong
        cfgmgr.CM_Get_DevNode_PropertyW.argtypes = [
            wt.DWORD, ctypes.POINTER(_PropertyKey), ctypes.POINTER(wt.ULONG),
            ctypes.c_void_p, ctypes.POINTER(wt.ULONG), ctypes.c_ulong]
        for walk in (cfgmgr.CM_Get_Child, cfgmgr.CM_Get_Sibling):
            walk.restype = ctypes.c_ulong
            walk.argtypes = [ctypes.POINTER(wt.DWORD), wt.DWORD, ctypes.c_ulong]
        cfgmgr.CM_Get_Device_IDW.restype = ctypes.c_ulong
        cfgmgr.CM_Get_Device_IDW.argtypes = [wt.DWORD, wt.LPWSTR, ctypes.c_ulong, ctypes.c_ulong]
        _dlls = setupapi, cfgmgr
    return _dlls


@dataclass(frozen=True)
class UsbPrinter:
    instance: str       # unique per attached unit (the same id usb_instances() counts)
    names: tuple = ()   # what Windows calls it, most specific first
    pid: str = ""       # USB product id in hex, for messages only
    ports: tuple = ()   # Windows printer ports of this unit ("USB017"): its live queue's port
    vendor: str = EPSON_VENDOR
    serial: str = ""    # from the USB device id when the printer reports one (HP does)

    @property
    def brand(self):
        return "hp" if self.vendor == HP_VENDOR else "epson"

    @property
    def name(self):
        """The name to show the user."""
        word, shown = ("HP", "HP") if self.brand == "hp" else ("EPSON", "Epson")
        for candidate in self.names:
            if word in candidate.upper().split() or candidate.upper().startswith(word):
                return candidate
        if self.names:
            return self.names[-1]
        return f"{shown} USB (PID {self.pid})" if self.pid else f"{shown} USB"


def _property(devinst, key):
    """A string property of a device node, '' if it has none."""
    _, cfgmgr = _api()
    buffer = ctypes.create_unicode_buffer(256)
    kind, size = wt.ULONG(0), wt.ULONG(ctypes.sizeof(buffer))
    status = cfgmgr.CM_Get_DevNode_PropertyW(devinst, ctypes.byref(key), ctypes.byref(kind),
                                             buffer, ctypes.byref(size), 0)
    return buffer.value.strip() if status == CR_SUCCESS else ""


def _printer_ports(node):
    """Printer ports of the Windows printer devices below a USB printer node. The device
    id of each one ends in its port: USBPRINT\\EPSONXP-230_SERIES\\7&5CA91A&0&USB017."""
    _, cfgmgr = _api()
    ports = []
    child = wt.DWORD(0)
    status = cfgmgr.CM_Get_Child(ctypes.byref(child), node, 0)
    while status == CR_SUCCESS:
        buffer = ctypes.create_unicode_buffer(512)
        if cfgmgr.CM_Get_Device_IDW(child.value, buffer, 512, 0) == CR_SUCCESS:
            port = re.search(r"&(USB\d+)$", buffer.value, re.I)
            if port:
                ports.append(port.group(1).upper())
        sibling = wt.DWORD(0)
        status = cfgmgr.CM_Get_Sibling(ctypes.byref(sibling), child.value, 0)
        child = sibling
    return ports


def _device_id(devinst):
    """Device instance id of a node, such as USB/VID_03F0&PID_2A54/CN09C3S2XG with
    backslashes; '' if unknown."""
    _, cfgmgr = _api()
    buffer = ctypes.create_unicode_buffer(512)
    if cfgmgr.CM_Get_Device_IDW(devinst, buffer, 512, 0) == CR_SUCCESS:
        return buffer.value
    return ""


def _interface(hdev, data):
    """(device path, device node) of one enumerated interface, or (None, None)."""
    setupapi, _ = _api()
    required = wt.DWORD(0)
    setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(data), None, 0,
                                              ctypes.byref(required), None)
    if not required.value:
        return None, None
    buffer = ctypes.create_string_buffer(required.value)
    # SP_DEVICE_INTERFACE_DETAIL_DATA_W.cbSize: 8 on 64-bit, 6 on 32-bit.
    ctypes.memmove(buffer, struct.pack("I", 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6), 4)
    node = _DevInfoData()
    node.cbSize = ctypes.sizeof(_DevInfoData)
    if not setupapi.SetupDiGetDeviceInterfaceDetailW(
            hdev, ctypes.byref(data), buffer, required.value, None, ctypes.byref(node)):
        return None, None
    return ctypes.wstring_at(ctypes.addressof(buffer) + 4), node.DevInst


def _present_interfaces(interface_guid, vendor):
    """[(path, instance, names, ports, unit id)] of the present device interfaces of one
    class made by `vendor`, one entry per interface. The unit id is the device id of the
    physical USB device: the parent of an interface of a composite device (MI_01, PI_02)
    or the node itself."""
    setupapi, cfgmgr = _api()
    guid = _Guid.parse(interface_guid)
    hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None,
                                         DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if not hdev or hdev == INVALID_HANDLE_VALUE:
        return []
    found = []
    try:
        index = 0
        while True:
            data = _InterfaceData()
            data.cbSize = ctypes.sizeof(_InterfaceData)
            if not setupapi.SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(guid),
                                                        index, ctypes.byref(data)):
                break
            index += 1
            path, node = _interface(hdev, data)
            if not path or vendor not in path.upper() or path.count("#") < 3:
                continue
            names = [_property(node, _FRIENDLY_NAME), _property(node, _BUS_REPORTED_DESC)]
            unit = _device_id(node)
            parent = wt.DWORD(0)
            if cfgmgr.CM_Get_Parent(ctypes.byref(parent), node, 0) == CR_SUCCESS:
                names.append(_property(parent.value, _BUS_REPORTED_DESC))
                if re.search(r"&(MI|PI)_\d", unit, re.I):
                    unit = _device_id(parent.value) or unit
            found.append((path, path.split("#")[2], [n for n in names if n],
                          _printer_ports(node), unit))
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return found


def epson_usb_printers(interface_guid=USBPRINT_GUID_TEXT, vendor=EPSON_VENDOR):
    """The Epson USB printers attached now, one per physical unit. [] when there are none,
    and also when this is not Windows."""
    if sys.platform != "win32":
        return []
    try:
        interfaces = _present_interfaces(interface_guid, vendor)
    except (OSError, AttributeError):  # SetupAPI unavailable: nothing can be told
        return []
    units = {}
    for path, instance, names, ports, _unit in interfaces:
        pid = re.search(r"pid_([0-9a-f]{4})", path, re.I)
        unit = units.setdefault(instance, {"names": [], "ports": [],
                                           "pid": pid.group(1).upper() if pid else ""})
        unit["names"] += [n for n in names if n not in unit["names"]]
        unit["ports"] += [p for p in ports if p not in unit["ports"]]
    return [UsbPrinter(instance, tuple(unit["names"]), unit["pid"], tuple(unit["ports"]))
            for instance, unit in sorted(units.items())]


def hp_usb_printers(interface_guid=USBPRINT_GUID_TEXT):
    """The HP USB printers attached now, one per physical unit, with the serial number
    Windows has in the USB device id. An HP tank printer shows several printer-class
    interfaces (MI_01 to print, PI_02 for IPP over USB...), so the interfaces are grouped
    by their USB device, not by interface. Registry only, like the Epson list."""
    if sys.platform != "win32":
        return []
    try:
        interfaces = _present_interfaces(interface_guid, HP_VENDOR)
    except (OSError, AttributeError):
        return []
    units = {}
    for path, instance, names, ports, unit_id in interfaces:
        key = unit_id or instance
        pid = re.search(r"pid_([0-9a-f]{4})", path, re.I)
        unit = units.setdefault(key, {"names": [], "ports": [], "instance": instance,
                                      "pid": pid.group(1).upper() if pid else ""})
        if re.search(r"&MI_01|#0001#?", path, re.I):      # the print interface names it
            unit["instance"] = instance
        unit["names"] += [n for n in names if n not in unit["names"]]
        unit["ports"] += [p for p in ports if p not in unit["ports"]]
    return [UsbPrinter(unit["instance"], tuple(unit["names"]), unit["pid"],
                       tuple(unit["ports"]), HP_VENDOR, _serial_of(key))
            for key, unit in sorted(units.items())]


def _serial_of(device_id):
    """Serial number at the end of a USB device id, '' for a Windows-made id."""
    last = device_id.split("\\")[-1]
    return last if last and "&" not in last and len(last) >= 6 else ""


def usb_printers():
    """Every Epson and HP USB printer attached now."""
    return epson_usb_printers() + hp_usb_printers()
