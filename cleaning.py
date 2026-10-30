"""Head cleaning like Epson's AdjProg, decoded from a USB capture of the original
running on an L3150 (captures/limpiezas_original.pcap).

What the original does, and this module reproduces:

1. Opens a D4 session and reads the main waste-pad counter cells.
2. Opens D4 socket 0x40 and sends ONE command on it:
       1b 7c 00 06 00 <read_key0> <read_key1> 84 7b 42 <mode>
   with mode 01 CL1 (weak), 02 CL2 (middle), 03 CL3 (strong), 04 power ink flushing.
3. Polls the status ("st" on the control socket) until the printer is idle again.
4. Only when its "NOT increment waste ink pad counter" box is ticked: writes the
   counter cells back with the values read in step 1. That is not a printer
   command. The ink has still gone to the pad; only the counter is rewound.

Verified only on the L3150 family (modes may differ on other models), plus the models
in MATCHED_MODELS, whose command was matched against documentation rather than captured.
"""
import struct
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from epson_usb.backends import open_transport
from epson_usb.d4 import REVISION_0X10, EpsonCtrlSession, Timeouts
from epson_usb.errors import D4Error
from epson_usb.status import parse_st2

import backend_cli as be
import driver_jobs

DATA_SOCKET = 0x40

# key, label, mode byte, how long the original took (s), our patience (s)
MODES = [
    ("cl1", "CL1 (débil)", 0x01, 190, 480),
    ("cl2", "CL2 (medio)", 0x02, 190, 480),
    ("cl3", "CL3 (fuerte)", 0x03, 190, 480),
    ("power", "Power ink flushing", 0x04, 120, 720),
]
MODE_BY_KEY = {m[0]: m for m in MODES}

#: Models whose mode bytes were captured. Others are refused: unverified bytes
#: could do something else on a different firmware.
VERIFIED_MODELS = {"L3150", "L3151", "L3160", "L3166", "L3168"}

#: Models not captured, but whose cleaning is the same command with the same mode bytes:
#: - ez-reset's devices.xml gives the L3250 record (L3250 Series, L3258 Series) exactly
#:   the cleaning list of the L3150 family's record (L3FX): "service" cleanings 0x01,
#:   0x02, 0x03, 0x04 and charging 0xFF.
#: - Epson's AdjProg for L1210/L3210/L3250/L3251/L3260/L5290 (1.0.1.1) builds the same
#:   packet, 1b 7c 00 06 00 <read_key> 84 7b 42 <mode>, with the model's read key (the
#:   functions at 0x5063b2 and 0x506419 of AdjProg.exe, sha256 d84963ea...).
#: Not yet run on a real L3250.
MATCHED_MODELS = {"L3250", "L3258"}

#: Models cleaned with the Epson driver's own job instead (see driver_jobs.py): one mode only.
DRIVER_MODE = ("driver", "Limpieza (driver Epson)", None,
               driver_jobs.TYPICAL_S, driver_jobs.PATIENCE_S)
MODE_BY_KEY[DRIVER_MODE[0]] = DRIVER_MODE

#: Every model a cleaning is sent to.
SUPPORTED_MODELS = VERIFIED_MODELS | MATCHED_MODELS | driver_jobs.DRIVER_MODELS


def modes_for(model: str) -> list:
    """Cleaning modes offered for a model."""
    return [DRIVER_MODE] if model in driver_jobs.DRIVER_MODELS else MODES

ST_ERROR, ST_WAITING, ST_IDLE, ST_CLEANING = 0x00, 0x03, 0x04, 0x07
ELEMENT_ERROR = 0x02

#: Replaced by tests to run against a fake printer.
TRANSPORT_FACTORY: Callable = lambda: open_transport(backend="usbprint")


class CleaningError(RuntimeError):
    """A cleaning that did not complete; the message is meant for the user."""


# -- packets (each one checked byte for byte against the capture in the tests) ----
def cleaning_command(read_key, mode_byte: int) -> bytes:
    return bytes([0x1B, 0x7C, 0x00, 0x06, 0x00, read_key[0], read_key[1],
                  0x84, 0x7B, 0x42, mode_byte])


def open_channel_payload(sock: int) -> bytes:
    """D4 OpenChannel, revision 0x10 layout."""
    return struct.pack(">BBBHHHH", 0x01, sock, sock, 0x0400, 0x0400, 0x0000, 0x0000)


def credit_request_payload(sock: int) -> bytes:
    return struct.pack(">BBBHH", 0x04, sock, sock, 0xFFFF, 0x0064)


def credit_payload(sock: int) -> bytes:
    return struct.pack(">BBBH", 0x03, sock, sock, 0x0064)


def status_of(reply: Optional[bytes]) -> Dict[str, Optional[int]]:
    """{'code', 'error'} from an ST2 reply; code is None if it is not readable."""
    parsed = parse_st2(reply or b"")
    elements = parsed.get("elements", {})
    error = elements.get(ELEMENT_ERROR)
    return {"code": parsed.get("status"), "error": error[0] if error else None}


# -- session ----------------------------------------------------------------
class CleaningSession(EpsonCtrlSession):
    """EPSON-CTRL session that can also open the D4 data socket 0x40."""

    def open_data_channel(self) -> None:
        if self.rev != REVISION_0X10:
            raise D4Error("El canal de datos solo está verificado con la revisión "
                          "D4 0x10 (la impresora usa 0x%02x)." % self.rev)
        self.send(0, 0, open_channel_payload(DATA_SOCKET), credit=1)
        reply = self.recv(self.timeouts.open_ms)
        payload = reply.payload if reply else b""
        if not (len(payload) >= 2 and payload[0] == 0x81 and payload[1] == 0x00):
            raise D4Error("La impresora no abrió el canal de datos: %r" % payload)
        self.send(0, 0, credit_request_payload(DATA_SOCKET), credit=1)
        for _ in range(4):
            reply = self.recv(self.timeouts.credit_ms)
            if reply is None or (reply.payload and reply.payload[0] == 0x84):
                break
        self.send(0, 0, credit_payload(DATA_SOCKET), credit=1)
        self.recv(self.timeouts.credit_ack_ms)

    def send_data(self, payload: bytes) -> None:
        self.send(DATA_SOCKET, DATA_SOCKET, payload)

    def status(self) -> Dict[str, Optional[int]]:
        return status_of(self.command(b"st", b"\x01"))


@dataclass
class CleaningResult:
    mode: str
    seconds: float
    before: Dict[str, tuple]          # pad name -> (points, maximum)
    after: Dict[str, tuple]
    restored: bool
    hidden_points: int                # ink poured but not counted (main pad)
    log: List[str] = field(default_factory=list)

    @property
    def delta_main(self) -> int:
        return self.after["main_waste"][0] - self.before["main_waste"][0]


def run(model: str, mode_key: str, restore_counter: bool = False,
        on_progress: Optional[Callable[[str, float], None]] = None,
        poll_s: float = 1.0, timeouts: Optional[Timeouts] = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.monotonic) -> CleaningResult:
    """Run one cleaning. Raises CleaningError with a user-readable message."""
    if model not in SUPPORTED_MODELS:
        raise CleaningError(
            f"Los modos de limpieza solo están verificados en la familia L3150 y la L3250 "
            f"({', '.join(sorted(SUPPORTED_MODELS))}); {model} no se envía.")
    key, label, mode_byte, _typical, patience = MODE_BY_KEY[mode_key]
    if (model in driver_jobs.DRIVER_MODELS) != (key == DRIVER_MODE[0]):
        raise CleaningError(f"El modo «{label}» no es para {model}. No se envió nada.")
    if key == DRIVER_MODE[0]:
        if restore_counter:
            raise CleaningError("Con la limpieza del driver no se restaura el contador. "
                                "No se envió nada.")
        try:
            return driver_jobs.run_cleaning(model, label, on_progress=on_progress,
                                            sleep=sleep, now=now)
        except driver_jobs.DriverCleaningError as exc:
            raise CleaningError(str(exc)) from exc
    read_key, write_key = be.keys(model)
    pad_cells = sorted({oid for pad in be.models()[model]["pads"].values() for oid in pad["oids"]})
    main_cells = be.main_pad_cells(model)
    log: List[str] = []
    progress = on_progress or (lambda text, elapsed: None)

    def read_cells(session) -> Dict[int, int]:
        cells = {}
        for addr in pad_cells:
            value = session.read_eeprom(addr)
            if value is None:
                raise CleaningError("No se pudo leer el contador de la impresora "
                                    f"(celda {addr}). No se envió nada.")
            cells[addr] = value
        return cells

    try:
        transport = TRANSPORT_FACTORY()
    except Exception as exc:
        raise CleaningError(f"No se pudo abrir la impresora por USB: {exc}") from exc
    session = CleaningSession(transport, read_key=read_key, write_key=write_key,
                              timeouts=timeouts or Timeouts())
    try:
        try:
            session.connect()
        except D4Error as exc:
            raise CleaningError(f"La impresora no responde a D4: {exc}") from exc

        status = session.status()
        if status["code"] != ST_IDLE:
            raise CleaningError(f"La impresora no está en reposo (estado {status['code']}, "
                                f"error {status['error']}). No se envió nada.")
        before_cells = read_cells(session)
        before = be.pad_points(model, before_cells)
        log.append(f"Contador antes: {before['main_waste'][0]} puntos")

        session.open_data_channel()
        started = now()
        session.send_data(cleaning_command(read_key, mode_byte))
        log.append(f"Orden {label} enviada")

        seen_cleaning, idle_streak = False, 0
        trace: List[str] = []  # each change of state, to tell what the printer did
        while True:
            sleep(poll_s)
            elapsed = now() - started
            st = session.status()
            progress(f"{label}: estado {st['code']}", elapsed)
            step = f"{st['code']}" + (f"/err {st['error']:#x}" if st["error"] is not None else "")
            if not trace or not trace[-1].endswith(f" {step}"):
                trace.append(f"{elapsed:.0f}s {step}")
            if st["code"] == ST_CLEANING:
                seen_cleaning, idle_streak = True, 0
            elif st["code"] == ST_IDLE:
                idle_streak += 1
                if idle_streak >= 2 and (seen_cleaning or elapsed > 15):
                    break
            elif st["code"] == ST_ERROR:
                raise CleaningError(
                    f"La impresora informó de un error (código {st['error']}) durante "
                    f"la limpieza. No se restauró nada; revisa la impresora y el depósito "
                    f"de residuos. Estados: {', '.join(trace)}")
            if elapsed > patience:
                raise CleaningError(
                    f"La limpieza no terminó en {patience} s. No se restauró nada. "
                    f"Estados: {', '.join(trace[-12:])}")
        seconds = now() - started
        log.append(f"Terminó en {seconds:.0f} s")

        after_cells = read_cells(session)
        after = be.pad_points(model, after_cells)
        delta = after["main_waste"][0] - before["main_waste"][0]
        log.append(f"Contador después: {after['main_waste'][0]} puntos ({delta:+d})")

        restored, hidden = False, 0
        if restore_counter:
            for addr in main_cells:
                if after_cells[addr] != before_cells[addr]:
                    if not session.write_eeprom(addr, before_cells[addr]):
                        raise CleaningError(
                            f"No se pudo restaurar la celda {addr}; el contador queda "
                            f"en {after['main_waste'][0]} puntos.")
                    if session.read_eeprom(addr) != before_cells[addr]:
                        raise CleaningError(f"La celda {addr} no quedó restaurada.")
            restored, hidden = True, max(delta, 0)
            log.append(f"Contador restaurado a {before['main_waste'][0]} puntos "
                       f"({hidden} puntos de tinta NO contados)")
        return CleaningResult(mode=label, seconds=seconds, before=before, after=after,
                              restored=restored, hidden_points=hidden, log=log)
    finally:
        session.close()
