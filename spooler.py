"""Maintenance jobs (nozzle check, head cleaning) written straight to the USB
printer interface, plus discovery of the Windows queues and USB devices. The
ESC/P2 remote-mode sequences come from the epson_escp2 library used by
epson_print_conf."""
import winreg
from dataclasses import dataclass

import win32print
from epson_escp2.epson_encode import EpsonEscp2
from epson_usb.backends import find_devices, open_transport

import pnp

GENERIC_PORT = "Puerto de impresora virtual para USB"


@dataclass
class Queue:
    name: str
    port: str
    active: bool  # the USB port currently has the printer attached
    host: str = ""  # network address of a TCP/IP port ('' for USB and the others)


def epson_queues(model_hint=""):
    """Epson queues of Windows. A queue is `active` when its port is the port of an Epson
    USB printer that is present now (see pnp.py). The description of the port is no use for
    that: it is often just "Puerto de impresora virtual para USB" even for the printer that
    is plugged in, and the stale queues of printers that are gone have the same text."""
    live_ports = {port for printer in usb_printers() for port in printer.ports}
    queues = []
    for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL, None, 2):
        name, port = p["pPrinterName"], p["pPortName"]
        if "EPSON" not in name.upper() or model_hint not in name:
            continue
        queues.append(Queue(name, port, port.upper() in live_ports))
    return sorted(queues, key=lambda q: (not q.active, q.name))


PORT_MONITORS = r"SYSTEM\CurrentControlSet\Control\Print\Monitors"


def port_host(port):
    """IP or host name of a Windows TCP/IP printer port (Standard TCP/IP Port, HP Standard
    TCP/IP Port...), '' for any other port. Reads the registry only."""
    if not port or port.upper().startswith(("USB", "LPT", "COM", "FILE", "WSD", "NUL")):
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, PORT_MONITORS) as monitors:
            for i in range(winreg.QueryInfoKey(monitors)[0]):
                name = winreg.EnumKey(monitors, i)
                try:
                    with winreg.OpenKey(monitors, f"{name}\\Ports\\{port}") as key:
                        for value in ("HostName", "IPAddress"):
                            try:
                                text = str(winreg.QueryValueEx(key, value)[0]).strip()
                            except OSError:
                                continue
                            if text:
                                return text
                except OSError:
                    continue
    except OSError:
        pass
    return ""


def hp_queues():
    """HP queues of Windows, connected ones first. A USB queue is `active` when its port
    belongs to an HP USB printer that is present now; a network queue carries the
    printer's address (host) and counts as active: whether it answers is only known by
    asking it."""
    live_ports = {port for printer in pnp.hp_usb_printers() for port in printer.ports}
    queues = []
    for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL, None, 2):
        name, port = p["pPrinterName"], p["pPortName"]
        if not name.upper().startswith(("HP ", "HEWLETT")):
            continue
        host = port_host(port)
        queues.append(Queue(name, port, port.upper() in live_ports or bool(host), host))
    return sorted(queues, key=lambda q: (not q.active, q.name))


# Windows spooler status bits, in words (winspool.h: PRINTER_STATUS_*, JOB_STATUS_*).
PRINTER_PROBLEMS = ((0x2, "en error"), (0x8, "con atasco de papel"), (0x10, "sin papel"),
                    (0x40, "con un problema de papel"), (0x80, "sin conexión"),
                    (0x1000, "no disponible"), (0x100000, "requiere intervención"),
                    (0x400000, "con la tapa abierta"))
JOB_PROBLEMS = ((0x2, "con error"), (0x1, "en pausa"), (0x20, "sin conexión"),
                (0x40, "sin papel"), (0x200, "bloqueado"), (0x400, "requiere intervención"))


#: Jobs Windows already finished but sometimes leaves in the queue (JOB_STATUS_DELETED,
#: JOB_STATUS_PRINTED, JOB_STATUS_COMPLETE). One such job, left there for days, kept
#: the app waiting for the full timeout after every test page.
JOB_DONE = 0x100 | 0x80 | 0x1000


def job_ids(queue):
    """Ids of every job in a Windows queue now, finished or not."""
    handle = win32print.OpenPrinter(queue)
    try:
        return {job.get("JobId") for job in win32print.EnumJobs(handle, 0, -1, 1)}
    finally:
        win32print.ClosePrinter(handle)


def queue_state(queue, ignore=()):
    """(jobs still to print in the Windows queue, what Windows says is wrong with the queue
    or its jobs, '' when nothing). Finished jobs and the ids in `ignore` (jobs that were
    already there before ours) do not count. Reads the spooler only, no USB traffic."""
    handle = win32print.OpenPrinter(queue)
    try:
        status = win32print.GetPrinter(handle, 2).get("Status", 0)
        jobs = [job for job in win32print.EnumJobs(handle, 0, -1, 1)
                if job.get("JobId") not in ignore and not job.get("Status", 0) & JOB_DONE]
    finally:
        win32print.ClosePrinter(handle)
    problems = [f"impresora {text}" for flag, text in PRINTER_PROBLEMS if status & flag]
    problems += [f"trabajo {text}" for flag, text in JOB_PROBLEMS
                 if any(job.get("Status", 0) & flag for job in jobs)]
    return len(jobs), " · ".join(problems)


def cancel_jobs(queue, ignore=()):
    """Delete the unfinished jobs of a Windows queue, except the ids in `ignore` (jobs
    that were there before ours). Returns how many were cancelled. Spooler only."""
    # the owner of a job may delete it with plain "use" access; no admin rights needed
    handle = win32print.OpenPrinter(queue, {"DesiredAccess": win32print.PRINTER_ACCESS_USE})
    try:
        cancelled = 0
        for job in win32print.EnumJobs(handle, 0, -1, 1):
            if job.get("JobId") in ignore or job.get("Status", 0) & JOB_DONE:
                continue
            win32print.SetJob(handle, job["JobId"], 0, None, win32print.JOB_CONTROL_DELETE)
            cancelled += 1
        return cancelled
    finally:
        win32print.ClosePrinter(handle)


def pending_jobs(queue):
    """Jobs still in a Windows queue. Reads the spooler only, no USB traffic."""
    return queue_state(queue)[0]


def usb_instances():
    """Physical Epson USB printers attached now (one per device instance, not per
    interface or per Windows queue)."""
    return sorted({d.path.split("#")[2]
                   for d in find_devices(backends=["usbprint"]) if d.path.count("#") >= 3})


def usb_printers():
    """The Epson and HP USB printers attached now, with the names Windows gives them.
    Reads the Windows device registry only: the printer is never opened, so this is safe
    while it prints (see pnp.py). It decides which model is connected; the Windows queues
    do not."""
    return pnp.usb_printers()


def send_direct(data):
    """Write raw bytes straight to the USB printer interface.

    The Windows queue cannot be used: Epson's V4 class driver routes every job
    through the XPS print processor, which rejects RAW data (event 824) before
    anything reaches the printer. Exactly one printer must be attached, so the
    bytes cannot go to another unit. The printer must then be left alone while
    it works: any other USB conversation (such as a status read) can abort it.
    """
    instances = usb_instances()
    if len(instances) != 1:
        raise RuntimeError(f"Hay {len(instances)} impresoras Epson USB conectadas; "
                           "deja conectada solo la que quieres usar.")
    transport = open_transport(backend="usbprint")
    try:
        sent = 0
        while sent < len(data):
            written = transport.write(data[sent:sent + 1024], timeout_ms=5000)
            if written <= 0:
                raise RuntimeError("La impresora no aceptó los datos.")
            sent += written
        return sent
    finally:
        transport.close()


def feed_sheet_job():
    """Turn the paper rollers once: an A4 page with nothing on it. It pushes out a sheet
    that stayed half way, or pulls one blank sheet from the rear feeder. No ink.

    The page set-up and the ending are byte for byte the ones of the colour pattern
    (epson_escp2 test_color_pattern), which these printers accept; only the raster data
    is left out. A first version sent a short ESC ( U with a long ESC ( v and no page
    size, and an L3250 stopped with its paper light on. With no paper in the rear
    feeder the printer also stops with the paper light on (paper out) until its button
    is pressed."""
    esc = EpsonEscp2()
    page = bytes.fromhex(
        "1b2847010001"                    # ESC ( G: graphics mode
        "1b28550500010101a005"            # ESC ( U: units, 1/1440"
        "1b28430400c6410000"              # ESC ( C: page length 29.7 cm
        "1b28630800ffffffffc6410000"      # ESC ( c: page format
        "1b28530800822e0000c6410000"      # ESC ( S: paper 21.0 x 29.7 cm
        "1b28760400" "00010000"           # ESC ( v: move the paper down 4.5 mm
    )
    return b"".join([
        esc.EXIT_PACKET_MODE, esc.INITIALIZE_PRINTER, esc.REMOTE_MODE, esc.JOB_START,
        esc.EXIT_REMOTE_MODE,
        page,
        esc.INITIALIZE_PRINTER, b"\r", esc.FF,   # end of page: the sheet goes out
        esc.INITIALIZE_PRINTER, esc.REMOTE_MODE, esc.LD, esc.EXIT_REMOTE_MODE,
        esc.INITIALIZE_PRINTER, esc.REMOTE_MODE, esc.LD, esc.JOB_END, esc.EXIT_REMOTE_MODE,
    ])


def nozzle_check(kind=0):
    return EpsonEscp2().check_nozzles(type=kind)


def color_pattern():
    return EpsonEscp2().test_color_pattern()


def clean_heads(group, power):
    return EpsonEscp2().clean_nozzles(group, power_clean=power)
