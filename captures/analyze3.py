"""Chronology of the original's EEPROM reads/writes and cleaning commands, with replies."""
import subprocess
import sys
from pathlib import Path

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
pcap = Path(sys.argv[1])
out = subprocess.run(
    [TSHARK, "-r", str(pcap), "-Y", "usb.transfer_type == 0x03 && usb.capdata",
     "-T", "fields", "-e", "frame.number", "-e", "frame.time_relative",
     "-e", "usb.endpoint_address", "-e", "usb.capdata"],
    capture_output=True, text=True).stdout
frames = []
for line in out.splitlines():
    p = line.split("\t")
    if len(p) == 4:
        frames.append((int(p[0]), float(p[1]), p[2], bytes.fromhex(p[3].replace(":", ""))))


def printable(b):
    return "".join(chr(x) if 32 <= x < 127 else "." for x in b)


def reply_after(index):
    """First IN data frame on the same socket after frames[index]."""
    sock = frames[index][3][:2]
    for no, t, ep, data in frames[index + 1:index + 12]:
        if ep == "0x85" and data[:2] == sock and len(data) > 6:
            return data[6:]
    return None


for i, (no, t, ep, data) in enumerate(frames):
    if ep != "0x04" or len(data) < 7:
        continue
    body = data[6:]
    if data[:2] == b"\x02\x02" and body[:2] == b"||":
        op = body[6:8].hex()
        rep = reply_after(i)
        kind = {"41be": "READ ", "42bd": "WRITE"}.get(op, "??" + op)
        arg = body[8:]
        if kind == "READ ":
            addr = arg[1] + (arg[2] << 8)
            print(f"{t:7.1f}s  #{no:<6} READ  addr {addr:3d}        -> reply {rep.hex(' ') if rep else None} {printable(rep) if rep else ''}")
        elif kind == "WRITE":
            addr = arg[1] + (arg[2] << 8)
            print(f"{t:7.1f}s  #{no:<6} WRITE addr {addr:3d} := 0x{arg[3]:02x} ({arg[3]})  -> reply {printable(rep) if rep else None}")
        else:
            print(f"{t:7.1f}s  #{no:<6} {kind} {body.hex(' ')}")
    elif data[:2] == b"\x40\x40":
        print(f"{t:7.1f}s  #{no:<6} DATA-CHANNEL {body.hex(' ')}   <-- cleaning command")
