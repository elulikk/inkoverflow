"""Reads an HP printer over its USB "REST" interface (the one HP Smart uses). Read only:
only HTTP GET is ever sent, and only over the vendor interface (MI_02, WinUSB, bulk OUT
0x0A / IN 0x8B), never the print interface, so nothing can come out printed.

HP Smart (or anything else holding the interface) must be closed, otherwise the open fails
and the caller falls back to what Windows says. Needs no IP and no network: this is how a
USB-only model such as the Smart Tank 210 gives its ink, status and counters.
"""
import ctypes
import ctypes.wintypes as wt
import gzip
import json
import uuid
import winreg

OUT_EP, IN_EP = 0x0A, 0x8B
USB_ENUM = r"SYSTEM\CurrentControlSet\Enum\USB"
TIMEOUT_MS = 4000
PATHS = {
    "identity": "/cdm/system/v1/identity",
    "status": "/cdm/system/v1/status",
    "supplies": "/cdm/supply/v1/suppliesPublic",
    "alerts": "/cdm/alert/v1/alerts",
    "counters": "/cdm/deviceUsage/v1/lifetimeCounters",
}


class UsbRestError(RuntimeError):
    pass


class NoInterface(UsbRestError):
    """The HP has no REST interface here (not USB, or the driver is not WinUSB)."""


class _Guid(ctypes.Structure):
    _fields_ = [("a", wt.DWORD), ("b", wt.WORD), ("c", wt.WORD), ("d", ctypes.c_ubyte * 8)]


class _InterfaceData(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("guid", _Guid), ("flags", wt.DWORD),
                ("reserved", ctypes.c_void_p)]


def _libs():
    return (ctypes.WinDLL("setupapi", use_last_error=True),
            ctypes.WinDLL("kernel32", use_last_error=True),
            ctypes.WinDLL("winusb", use_last_error=True))


def _guid(text):
    u = uuid.UUID(text.strip("{}"))
    g = _Guid()
    g.a, g.b, g.c = u.time_low, u.time_mid, u.time_hi_version
    for i, byte in enumerate(u.bytes[8:]):
        g.d[i] = byte
    return g


def _interface_guids():
    """(pid, DeviceInterfaceGUID) of each HP USB device that has a REST interface."""
    found = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, USB_ENUM) as usb:
            index = 0
            while True:
                try:
                    name = winreg.EnumKey(usb, index)
                except OSError:
                    break
                index += 1
                upper = name.upper()
                if not (upper.startswith("VID_03F0&") and upper.endswith("&MI_02")):
                    continue
                try:
                    with winreg.OpenKey(usb, name) as key:
                        instance = winreg.EnumKey(key, 0)
                    with winreg.OpenKey(usb, f"{name}\\{instance}\\Device Parameters") as key:
                        guid, _ = winreg.QueryValueEx(key, "DeviceInterfaceGUID")
                except OSError:
                    continue
                found.append((upper.split("PID_")[1][:4], guid))
    except OSError:
        pass
    return found


def device_path(pid=None):
    """Path of the plugged-in HP REST interface (of that USB pid if given), or None."""
    setupapi = _libs()[0]
    setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    for found_pid, guid_text in _interface_guids():
        if pid and found_pid.upper() != pid.upper():
            continue
        guid = _guid(guid_text)
        hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, 0x12)
        data = _InterfaceData()
        data.cbSize = ctypes.sizeof(data)
        path, i = None, 0
        while setupapi.SetupDiEnumDeviceInterfaces(ctypes.c_void_p(hdev), None,
                                                   ctypes.byref(guid), i, ctypes.byref(data)):
            need = wt.DWORD()
            setupapi.SetupDiGetDeviceInterfaceDetailW(
                ctypes.c_void_p(hdev), ctypes.byref(data), None, 0, ctypes.byref(need), None)
            buf = ctypes.create_string_buffer(need.value)
            ctypes.cast(buf, ctypes.POINTER(wt.DWORD))[0] = (
                8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)
            if setupapi.SetupDiGetDeviceInterfaceDetailW(
                    ctypes.c_void_p(hdev), ctypes.byref(data), buf, need, None, None):
                candidate = ctypes.wstring_at(ctypes.addressof(buf) + 4)
                if "mi_02" in candidate.lower():
                    path = candidate
                    break
            i += 1
        setupapi.SetupDiDestroyDeviceInfoList(ctypes.c_void_p(hdev))
        if path:
            return path
    return None


def _complete(data):
    head, _, body = data.partition(b"\r\n\r\n")
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            return len(body) >= int(line.split(b":")[1])
    return True


def decode(raw):
    """(status line, body text) of a raw HTTP reply (chunked and gzip handled)."""
    head, _, body = raw.partition(b"\r\n\r\n")
    if b"chunked" in head.lower():
        out, rest = b"", body
        while rest:
            size, _, rest = rest.partition(b"\r\n")
            try:
                n = int(size.split(b";")[0] or b"0", 16)
            except ValueError:
                break
            if n == 0:
                break
            out, rest = out + rest[:n], rest[n + 2:]
        body = out
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return head.decode("latin1").split("\r\n")[0], body.decode("utf8", "replace")


class Session:
    """One open WinUSB handle on the REST interface; GET only."""

    def __init__(self, path):
        self.path = path
        _, self._kernel32, self._winusb = _libs()
        self._kernel32.CreateFileW.restype = ctypes.c_void_p
        handle = self._kernel32.CreateFileW(path, 0xC0000000, 3, None, 3, 0x40000000 | 0x80,
                                            None)
        if handle in (None, ctypes.c_void_p(-1).value):
            raise UsbRestError(f"no se pudo abrir la HP por USB (error "
                               f"{ctypes.get_last_error()}): ¿HP Smart sigue abierto?")
        self._handle = handle
        self._wh = ctypes.c_void_p()
        if not self._winusb.WinUsb_Initialize(ctypes.c_void_p(handle), ctypes.byref(self._wh)):
            code = ctypes.get_last_error()
            self._kernel32.CloseHandle(ctypes.c_void_p(handle))
            raise UsbRestError(f"WinUsb_Initialize falló ({code})")
        timeout = wt.ULONG(TIMEOUT_MS)
        for endpoint in (IN_EP, OUT_EP):
            self._winusb.WinUsb_SetPipePolicy(self._wh, endpoint, 3, 4, ctypes.byref(timeout))

    def close(self):
        self._winusb.WinUsb_Free(self._wh)
        self._kernel32.CloseHandle(ctypes.c_void_p(self._handle))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def get(self, target):
        """Parsed JSON of GET `target`; UsbRestError on a transfer failure or non-200."""
        message = (f"GET {target} HTTP/1.1\r\nHost: {self.path}\r\nAccept: application/json\r\n"
                   "Accept-Encoding: identity\r\nConnection: keep-alive\r\n\r\n").encode()
        sent = wt.ULONG()
        if not self._winusb.WinUsb_WritePipe(self._wh, OUT_EP, message, len(message),
                                             ctypes.byref(sent), None):
            raise UsbRestError(f"WritePipe falló ({ctypes.get_last_error()})")
        data = b""
        while True:
            buf = ctypes.create_string_buffer(4096)
            got = wt.ULONG()
            if not self._winusb.WinUsb_ReadPipe(self._wh, IN_EP, buf, 4096, ctypes.byref(got),
                                                None):
                break
            data += buf.raw[:got.value]
            if data.endswith(b"0\r\n\r\n") or (b"\r\n\r\n" in data and
                                                b"Content-Length" in data and _complete(data)):
                break
        if not data:
            raise UsbRestError(f"la HP no contestó a {target}")
        status, body = decode(data)
        if " 200" not in status:
            raise UsbRestError(f"{target}: {status}")
        try:
            return json.loads(body)
        except ValueError as exc:
            raise UsbRestError(f"{target}: respuesta ilegible ({exc})")


def read_all(pid=None):
    """{'identity', 'status', 'supplies', 'alerts', 'counters'} as parsed JSON; a section the
    printer refuses is left out. UsbRestError when the interface is absent or busy."""
    path = device_path(pid)
    if not path:
        raise NoInterface("la HP no expone su interfaz de lectura por USB")
    out = {}
    with Session(path) as session:
        for key, target in PATHS.items():
            try:
                out[key] = session.get(target)
            except UsbRestError:
                if not out:
                    raise       # the first question already fails: nothing will answer
    return out
