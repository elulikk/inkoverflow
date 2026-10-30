"""Read-only probe of the HP REST interface (MI_02, WinUSB) of a USB HP printer.

    python hp_rest_probe.py GET /cdm/servicesDiscovery

Sends one HTTP GET over the bulk pipes the HP Smart capture showed (OUT 0x0a, IN 0x8b)
and prints the reply. Only GET is accepted: this tool must never change the printer.
HP Smart (or anything else holding the interface) must be closed first.
"""
import ctypes
import ctypes.wintypes as wt
import gzip
import sys
import winreg

OUT_EP, IN_EP = 0x0A, 0x8B
INSTANCE_PREFIX = r"SYSTEM\CurrentControlSet\Enum\USB\VID_03F0&PID_4654&MI_02"

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
winusb = ctypes.WinDLL("winusb", use_last_error=True)


class GUID(ctypes.Structure):
    _fields_ = [("a", wt.DWORD), ("b", wt.WORD), ("c", wt.WORD), ("d", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("guid", GUID), ("flags", wt.DWORD),
                ("reserved", ctypes.c_void_p)]


def _guid(text):
    import uuid
    u = uuid.UUID(text.strip("{}"))
    g = GUID()
    g.a, g.b, g.c = u.time_low, u.time_mid, u.time_hi_version
    for i, byte in enumerate(u.bytes[8:]):
        g.d[i] = byte
    return g


def interface_guid_and_instance():
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, INSTANCE_PREFIX) as key:
        inst = winreg.EnumKey(key, 0)
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                        f"{INSTANCE_PREFIX}\\{inst}\\Device Parameters") as key:
        guid, _ = winreg.QueryValueEx(key, "DeviceInterfaceGUID")
    return guid, inst


def device_path():
    guid_text, _ = interface_guid_and_instance()
    guid = _guid(guid_text)
    setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, 0x12)  # present|interface
    data = SP_DEVICE_INTERFACE_DATA()
    data.cbSize = ctypes.sizeof(data)
    path = None
    i = 0
    while setupapi.SetupDiEnumDeviceInterfaces(ctypes.c_void_p(hdev), None, ctypes.byref(guid),
                                               i, ctypes.byref(data)):
        need = wt.DWORD()
        setupapi.SetupDiGetDeviceInterfaceDetailW(ctypes.c_void_p(hdev), ctypes.byref(data),
                                                  None, 0, ctypes.byref(need), None)
        buf = ctypes.create_string_buffer(need.value)
        ctypes.cast(buf, ctypes.POINTER(wt.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
        if setupapi.SetupDiGetDeviceInterfaceDetailW(ctypes.c_void_p(hdev), ctypes.byref(data),
                                                     buf, need, None, None):
            cand = ctypes.wstring_at(ctypes.addressof(buf) + 4)
            if "mi_02" in cand.lower() and "pid_4654" in cand.lower():
                path = cand
                break
        i += 1
    setupapi.SetupDiDestroyDeviceInfoList(ctypes.c_void_p(hdev))
    return path


def open_pipe_handle(path):
    kernel32.CreateFileW.restype = ctypes.c_void_p
    h = kernel32.CreateFileW(path, 0xC0000000, 3, None, 3, 0x40000000 | 0x80, None)
    if h in (None, ctypes.c_void_p(-1).value):
        raise OSError(f"CreateFile falló ({ctypes.get_last_error()}): ¿HP Smart sigue abierto?")
    wh = ctypes.c_void_p()
    if not winusb.WinUsb_Initialize(ctypes.c_void_p(h), ctypes.byref(wh)):
        raise OSError(f"WinUsb_Initialize falló ({ctypes.get_last_error()})")
    return h, wh


def request(method, target, timeout_ms=5000):
    if method != "GET":
        raise SystemExit("Solo GET: esta sonda no escribe nada en la impresora.")
    h, wh = open_pipe_handle(device_path())
    try:
        t = wt.ULONG(timeout_ms)
        for ep in (IN_EP, OUT_EP):
            winusb.WinUsb_SetPipePolicy(wh, ep, 3, 4, ctypes.byref(t))     # PIPE_TRANSFER_TIMEOUT
        # HP Smart sends the device path as Host (seen in the USB capture); "localhost" gets 404.
        msg = (f"GET {target} HTTP/1.1\r\nHost: {device_path()}\r\nAccept: application/json\r\n"
               "Accept-Encoding: identity\r\nConnection: keep-alive\r\n\r\n").encode()
        sent = wt.ULONG()
        if not winusb.WinUsb_WritePipe(wh, OUT_EP, msg, len(msg), ctypes.byref(sent), None):
            raise OSError(f"WritePipe falló ({ctypes.get_last_error()})")
        data = b""
        while True:
            buf = ctypes.create_string_buffer(4096)
            got = wt.ULONG()
            if not winusb.WinUsb_ReadPipe(wh, IN_EP, buf, 4096, ctypes.byref(got), None):
                break
            data += buf.raw[:got.value]
            if data.endswith(b"0\r\n\r\n") or (b"\r\n\r\n" in data and b"Content-Length" in data
                                                 and _complete(data)):
                break
        return data
    finally:
        winusb.WinUsb_Free(wh)
        kernel32.CloseHandle(ctypes.c_void_p(h))


def _complete(data):
    head, _, body = data.partition(b"\r\n\r\n")
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            return len(body) >= int(line.split(b":")[1])
    return True


def decode(raw):
    head, _, body = raw.partition(b"\r\n\r\n")
    if b"chunked" in head.lower():
        out, rest = b"", body
        while rest:
            size, _, rest = rest.partition(b"\r\n")
            n = int(size.split(b";")[0] or b"0", 16)
            if n == 0:
                break
            out, rest = out + rest[:n], rest[n + 2:]
        body = out
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return head.decode("latin1"), body.decode("utf8", "replace")


if __name__ == "__main__":
    method, target = sys.argv[1], sys.argv[2]
    head, body = decode(request(method, target))
    print(head.split("\r\n")[0])
    print(body)
