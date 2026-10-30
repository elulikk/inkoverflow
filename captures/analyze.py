"""Summarize what a USBPcap capture sent to the printer's control channel (D4 socket 2)."""
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
    parts = line.split("\t")
    if len(parts) == 4:
        frames.append((int(parts[0]), float(parts[1]), parts[2], bytes.fromhex(parts[3].replace(":", ""))))

print("bulk frames with data:", len(frames), "| span: %.0f s" % (frames[-1][1] - frames[0][1]))

# bursts of activity: gaps > 20 s split the capture into phases
phases, current = [], [frames[0]]
for f in frames[1:]:
    if f[1] - current[-1][1] > 20:
        phases.append(current)
        current = []
    current.append(f)
phases.append(current)
print("phases (gaps > 20 s):", len(phases))
for i, ph in enumerate(phases, 1):
    print(f"  phase {i}: t={ph[0][1]:.0f}-{ph[-1][1]:.0f}s frames={len(ph)}")

# unique OUT payloads on the control socket (02 02 ...)
print("\nOUT payloads to socket 2 (header 02 02), unique, in order of first appearance:")
seen = OrderedDict()
for no, t, ep, data in frames:
    if ep != "0x04" or len(data) < 7 or data[0] != 2 or data[1] != 2:
        continue
    body = data[6:]
    key = body.hex()
    if key not in seen:
        seen[key] = [no, t, t, 1]
    else:
        seen[key][2] = t
        seen[key][3] += 1
for key, (no, t0, t1, n) in seen.items():
    body = bytes.fromhex(key)
    ascii_ = "".join(chr(b) if 32 <= b < 127 else "." for b in body)
    shown = body[:48].hex(" ")
    print(f"  #{no:<6} t={t0:7.1f}s x{n:<4} len={len(body):<4} {shown}{' ...' if len(body) > 48 else ''} | {ascii_[:60]}")
