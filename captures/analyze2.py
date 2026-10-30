"""List what was sent on the other D4 sockets (not the control socket 2), by phase."""
import subprocess
import sys
from collections import OrderedDict
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

boundaries = [(33, 223), (409, 596), (690, 880), (926, 1117), (1327, 1431)]


def phase(t):
    for i, (a, b) in enumerate(boundaries, 1):
        if a - 5 <= t <= b + 5:
            return i
    return 0


seen = OrderedDict()
for no, t, ep, data in frames:
    if ep != "0x04" or len(data) < 6:
        continue
    sock = (data[0], data[1])
    if sock == (2, 2):
        continue
    body = data[6:] if sock != (0, 0) else data  # D4 commands keep their header
    key = (sock, body.hex())
    seen.setdefault(key, [no, t, phase(t), 0])
    seen[key][3] += 1

print(f"{'frame':>6} {'t(s)':>7} ph  n   socket  len  payload")
for (sock, hexbody), (no, t, ph, n) in seen.items():
    body = bytes.fromhex(hexbody)
    text = "".join(chr(b) if 32 <= b < 127 else "." for b in body)
    shown = body[:56].hex(" ") + (" ..." if len(body) > 56 else "")
    print(f"{no:>6} {t:7.1f} {ph:>2} {n:>3}  {sock[0]:02x}:{sock[1]:02x}  {len(body):>4}  {shown}")
    print(f"{'':>34}{text[:80]}")
