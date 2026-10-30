"""Start/stop an elevated USBPcap capture of the printer only (device 4 on USBPcap1).

    python session.py start <name>   -> asks Windows for administrator rights once
    python session.py stop           -> ends the capture and prints a summary
"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG, STOP, STATE = HERE / "capture.log", HERE / "capture.stop", HERE / "capture.current"
TSHARK = Path(r"C:\Program Files\Wireshark\tshark.exe")


def start(name, devices="4"):
    out = HERE / f"{name}.pcap"
    out.unlink(missing_ok=True)
    LOG.unlink(missing_ok=True)
    STOP.unlink(missing_ok=True)
    args = (f'-NoProfile -ExecutionPolicy Bypass -File "{HERE / "capture.ps1"}" '
            f'-Out "{out}" -Stop "{STOP}" -Log "{LOG}" -Devices {devices}')
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Start-Process powershell -Verb RunAs -WindowStyle Hidden -ArgumentList '{args}'"],
                   check=True)
    for _ in range(120):  # up to 60 s for the user to accept the Windows prompt
        if LOG.exists() and LOG.read_text(errors="ignore").strip():
            break
        time.sleep(0.5)
    text = LOG.read_text(errors="ignore").strip() if LOG.exists() else ""
    print("log:", text or "(sin respuesta: no se aceptó el aviso de administrador)")
    if text.startswith("started"):
        STATE.write_text(str(out))
        time.sleep(1.5)
        print("capturando en:", out.name)
    return text.startswith("started")


def stop():
    out = Path(STATE.read_text())
    STOP.write_text("stop")
    for _ in range(40):
        if "stopped" in LOG.read_text(errors="ignore"):
            break
        time.sleep(0.5)
    print("log:", LOG.read_text(errors="ignore").strip().replace("\n", " | "))
    print("pcap:", out.name, out.stat().st_size if out.exists() else "no existe", "bytes")
    if out.exists() and out.stat().st_size and TSHARK.exists():
        done = subprocess.run([str(TSHARK), "-r", str(out), "-q", "-z", "io,stat,0"],
                              capture_output=True, text=True)
        print(done.stdout.strip()[-400:] or done.stderr.strip()[-300:])


if __name__ == "__main__":
    if sys.argv[1] == "start":
        sys.exit(0 if start(sys.argv[2], *sys.argv[3:4]) else 1)
    stop()
