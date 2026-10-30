"""Unique status replies (answers to 'st') over time: how the original sees a cleaning end."""
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

TSHARK = r"C:\Users\Usuario\Desktop\Reset Epson L3150 L1110 L3100 L3110 L3150 L3160 L5190\epson-reset-ui\captures"
TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
out = subprocess.run(
    [TSHARK, "-r", str(Path(sys.argv[1])), "-Y", "usb.transfer_type == 0x03 && usb.capdata && usb.endpoint_address == 0x85",
     "-T", "fields", "-e", "frame.time_relative", "-e", "usb.capdata"],
    capture_output=True, text=True).stdout

seen = OrderedDict()
for line in out.splitlines():
    t, h = line.split("\t")
    data = bytes.fromhex(h.replace(":", ""))
    if data[:2] != b"\x02\x02" or b"ST2" not in data:
        continue
    body = data[6:]
    key = body.hex()
    if key not in seen:
        seen[key] = [float(t), float(t), 1]
    else:
        seen[key][1] = float(t)
        seen[key][2] += 1

print("unique ST2 status replies, in order of first appearance:")
for key, (t0, t1, n) in seen.items():
    body = bytes.fromhex(key)
    # status block is a sequence of fields: id, len, value...
    text = "".join(chr(b) if 32 <= b < 127 else "." for b in body)
    print(f"  {t0:7.1f}-{t1:7.1f}s  x{n:<4} {len(body):3d}B  {body.hex(' ')[:150]}")
    print(f"{'':>34}{text[:70]}")
