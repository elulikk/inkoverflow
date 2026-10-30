"""Nozzle check and head cleaning exactly as Epson's own Windows driver sends them, decoded
from a USB capture of the driver's Maintenance tab on an XP-2101
(captures/xp2100_driver_mant.pcap, driver 3.02.02.00).

Windows and the backend call the XP-2101 "XP-2100", so that is the model name used here.

The driver writes both jobs, as ESC/P2 remote-mode commands, to the printer interface
(the one Windows' usbprint driver owns), not through D4 like Epson's AdjProg:

    nozzle check  REMOTE1 TI <clock> JS 00 00 00 00 PP 00 01 FE NC 00 00 ... JE 00
    cleaning      REMOTE1 TI <clock> CH 00 00

The driver offers one cleaning only (no CL1/CL2/CL3, no power flushing), and in the capture
it did not talk to the printer over D4 while the head was cleaning (state 7 for ~115 s).
So run_cleaning() leaves the printer alone for QUIET_S before asking its state again.
One cleaning used 6-7 % of each 206 cartridge in the capture.
"""
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

#: Models whose jobs were captured from the Epson driver (the XP-2101 declares XP-2100).
DRIVER_MODELS = {"XP-2100"}

EXIT_PACKET_MODE = b"\x00\x00\x00\x1b\x01@EJL 1284.4\n@EJL     \n"
INIT = b"\x1b@\x1b@"
ENTER_REMOTE = b"\x1b(R\x08\x00\x00REMOTE1"
EXIT_REMOTE = b"\x1b\x00\x00\x00"

ST_ERROR, ST_IDLE, ST_CLEANING = 0x00, 0x04, 0x07

# what the capture showed: busy ~115 s after the job; we wait longer before any USB talk
TYPICAL_S = 115
QUIET_S = 130
PATIENCE_S = 420
POLL_S = 5


def remote(cmd: bytes, params: bytes) -> bytes:
    """One remote-mode command: two letters, 16-bit little-endian length, parameters."""
    return cmd + len(params).to_bytes(2, "little") + params


def timer(when: datetime) -> bytes:
    """TI: the driver sets the printer clock before every job."""
    return remote(b"TI", b"\x00" + when.year.to_bytes(2, "big")
                  + bytes([when.month, when.day, when.hour, when.minute, when.second]))


def nozzle_check_job(when: Optional[datetime] = None) -> bytes:
    """The driver's 'Comp. inyec. cab. impr.': one page with the nozzle pattern."""
    when = when or datetime.now()
    return b"".join([
        EXIT_PACKET_MODE, INIT, ENTER_REMOTE,
        timer(when),
        remote(b"JS", b"\x00\x00\x00\x00"),   # job start
        remote(b"PP", b"\x00\x01\xfe"),        # paper path: the rear feeder
        remote(b"NC", b"\x00\x00"),            # print the nozzle check
        EXIT_REMOTE,
        b"\r\n\r\n",
        ENTER_REMOTE,
        remote(b"VI", b"\x00\x00"),
        remote(b"LD", b""),                    # load the default settings
        EXIT_REMOTE,
        b"\x0c", INIT, ENTER_REMOTE,
        remote(b"JE", b"\x00"),                # job end
        EXIT_REMOTE,
    ])


def cleaning_job(when: Optional[datetime] = None) -> bytes:
    """The driver's 'Limpieza de cabezal de impresión' (all colours)."""
    when = when or datetime.now()
    return b"".join([EXIT_PACKET_MODE, INIT, ENTER_REMOTE, timer(when),
                     remote(b"CH", b"\x00\x00"), EXIT_REMOTE])


class DriverCleaningError(RuntimeError):
    """A cleaning that did not complete; the message is meant for the user."""


@dataclass
class DriverCleaningResult:
    mode: str
    seconds: float
    before: Dict[str, tuple]
    after: Dict[str, tuple]
    restored: bool = False
    hidden_points: int = 0
    log: List[str] = field(default_factory=list)

    @property
    def delta_main(self) -> int:
        return self.after["main_waste"][0] - self.before["main_waste"][0]


def _state(info) -> Optional[int]:
    status = (info or {}).get("printer_status", {}).get("status")
    return status[0] if status else None


def run_cleaning(model: str, label: str,
                 on_progress: Optional[Callable[[str, float], None]] = None,
                 send: Optional[Callable[[bytes], int]] = None,
                 read_info: Optional[Callable[[str], dict]] = None,
                 read_cells: Optional[Callable[[str, list], dict]] = None,
                 sleep: Callable[[float], None] = time.sleep,
                 now: Callable[[], float] = time.monotonic) -> DriverCleaningResult:
    """Run the driver's cleaning. send/read_info/read_cells are replaced in the tests."""
    import backend_cli as be
    if model not in DRIVER_MODELS:
        raise DriverCleaningError(f"La limpieza del driver solo está capturada en "
                                  f"{', '.join(sorted(DRIVER_MODELS))}; {model} no se envía.")
    if send is None:
        import spooler
        send = spooler.send_direct
    read_info = read_info or be.read_info
    read_cells = read_cells or be.read_cells
    progress = on_progress or (lambda text, elapsed: None)
    cells = sorted({oid for pad in be.models()[model]["pads"].values() for oid in pad["oids"]})
    log: List[str] = []

    def state():
        try:
            return _state(read_info(model))
        except Exception:  # busy printers sometimes do not answer: just ask again later
            return None

    first = state()
    if first != ST_IDLE:
        raise DriverCleaningError(f"La impresora no está en reposo (estado {first}). "
                                  "No se envió nada.")
    try:
        before = be.pad_points(model, read_cells(model, cells))
    except Exception as exc:
        raise DriverCleaningError(f"No se pudo leer el contador: {exc}. No se envió nada.") from exc
    log.append(f"Contador antes: {before['main_waste'][0]} puntos")

    started = now()
    send(cleaning_job())
    log.append(f"Orden «{label}» enviada (secuencia del driver Epson)")

    # The driver does not talk to the printer while it cleans; neither do we.
    while now() - started < QUIET_S:
        sleep(1)
        progress(f"{label}: limpiando (sin consultar la impresora)", now() - started)
    trace: List[str] = []
    while True:
        elapsed = now() - started
        code = state()
        progress(f"{label}: estado {code}", elapsed)
        if not trace or not trace[-1].endswith(f" {code}"):
            trace.append(f"{elapsed:.0f}s {code}")
        if code == ST_IDLE:
            break
        if code == ST_ERROR:
            raise DriverCleaningError(f"La impresora informó de un error durante la limpieza. "
                                      f"Estados: {', '.join(trace)}")
        if elapsed > PATIENCE_S:
            raise DriverCleaningError(f"La limpieza no terminó en {PATIENCE_S} s. "
                                      f"Estados: {', '.join(trace[-12:])}")
        sleep(POLL_S)
    seconds = now() - started
    log.append(f"Terminó (en reposo a los {seconds:.0f} s)")
    try:
        after = be.pad_points(model, read_cells(model, cells))
    except Exception as exc:
        raise DriverCleaningError(f"La limpieza terminó pero no se pudo releer el contador: "
                                  f"{exc}") from exc
    delta = after["main_waste"][0] - before["main_waste"][0]
    log.append(f"Contador después: {after['main_waste'][0]} puntos ({delta:+d})")
    return DriverCleaningResult(mode=label, seconds=seconds, before=before, after=after, log=log)
