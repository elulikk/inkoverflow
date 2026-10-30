"""A fake HP Smart Tank 580 for hardware-free tests.

* FakeHp is an HTTP server on 127.0.0.1 that answers like the printer's network side:
  IPP Get-Printer-Attributes on /ipp/print and the LEDM files of /DevMgmt. One port
  serves both (the real printer uses 631 and 80; the test passes "127.0.0.1:port").
* usb_unit() is the printer as Windows lists it over USB (pnp.UsbPrinter).

Everything it receives is kept in `requests`, so a test can check that nothing but
reads ever reached the printer.
"""
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pnp

MODEL = "HP Smart Tank 580-590 series"
SERIAL = "CN2BK4M0QZ"
FIRMWARE = "TJP1FN2310AR"
PRODUCT = "1F3Y2A"

NS = ('xmlns:dd="http://www.hp.com/schemas/imaging/con/dictionaries/1.0/" '
      'xmlns:dd2="http://www.hp.com/schemas/imaging/con/dictionaries/2009/04/06" ')


def config_xml(serial=SERIAL):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<prdcfgdyn:ProductConfigDyn {NS}xmlns:prdcfgdyn="http://www.hp.com/schemas/imaging/con/ledm/productconfigdyn/2007/11/05">
 <dd:Version><dd:Revision>SVN-IPG-LEDM.216</dd:Revision><dd:Date>2011-02-08</dd:Date></dd:Version>
 <prdcfgdyn:ProductInformation>
  <dd:MakeAndModel>{MODEL}</dd:MakeAndModel>
  <dd:ProductNumber>{PRODUCT}</dd:ProductNumber>
  <dd:SerialNumber>{serial}</dd:SerialNumber>
  <dd:Version><dd:Revision>{FIRMWARE}</dd:Revision><dd:Date>2023-10-03</dd:Date></dd:Version>
 </prdcfgdyn:ProductInformation>
</prdcfgdyn:ProductConfigDyn>"""


def status_xml(category="ready", alerts=()):
    rows = "".join(
        f"<psdyn:Alert><ad:ProductStatusAlertID>{code}</ad:ProductStatusAlertID>"
        f"<ad:Severity>{severity}</ad:Severity><ad:AlertDetails>"
        f"<ad:AlertDetailsMarkerColor>{colour}</ad:AlertDetailsMarkerColor>"
        f"</ad:AlertDetails></psdyn:Alert>" for code, severity, colour in alerts)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<psdyn:ProductStatusDyn {NS}xmlns:psdyn="http://www.hp.com/schemas/imaging/con/ledm/productstatusdyn/2007/10/31" xmlns:pscat="http://www.hp.com/schemas/imaging/con/ledm/productstatuscategories/2007/10/31" xmlns:ad="http://www.hp.com/schemas/imaging/con/ledm/alertdetails/2007/10/31">
 <dd:Version><dd:Revision>SVN-IPG-LEDM.216</dd:Revision></dd:Version>
 <psdyn:Status><pscat:StatusCategory>{category}</pscat:StatusCategory></psdyn:Status>
 <psdyn:AlertTable>{rows}</psdyn:AlertTable>
</psdyn:ProductStatusDyn>"""


def consumables_xml(inks):
    """inks: [(colour, label, state, level or None)]. Two printheads are added."""
    rows = ""
    for colour, label, state, level in inks:
        pct = f"<dd:ConsumablePercentageLevelRemaining>{level}</dd:ConsumablePercentageLevelRemaining>" \
            if level is not None else ""
        rows += (f"<ccdyn:ConsumableInfo><dd:ConsumableTypeEnum>ink</dd:ConsumableTypeEnum>"
                 f"<dd:ConsumableLabelCode>{label}</dd:ConsumableLabelCode>"
                 f"<dd:MarkerColor>{colour}</dd:MarkerColor>{pct}"
                 f"<dd:ConsumableState>{state}</dd:ConsumableState>"
                 f"<dd:ConsumableSelectibilityNumber>{'GT53' if label == 'K' else 'GT52'}"
                 f"</dd:ConsumableSelectibilityNumber></ccdyn:ConsumableInfo>")
    for label in ("K", "CMY"):
        rows += (f"<ccdyn:ConsumableInfo><dd:ConsumableTypeEnum>printhead</dd:ConsumableTypeEnum>"
                 f"<dd:ConsumableLabelCode>{label}</dd:ConsumableLabelCode>"
                 f"<dd:ConsumableState>ok</dd:ConsumableState></ccdyn:ConsumableInfo>")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ccdyn:ConsumableConfigDyn {NS}xmlns:ccdyn="http://www.hp.com/schemas/imaging/con/ledm/consumableconfigdyn/2007/11/19">
 <dd:Version><dd:Revision>SVN-IPG-LEDM.216</dd:Revision></dd:Version>{rows}
</ccdyn:ConsumableConfigDyn>"""


def usage_xml(total=1834, mono=1201, color=633, scans=412, copies=97, jams=3):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<pudyn:ProductUsageDyn {NS}xmlns:pudyn="http://www.hp.com/schemas/imaging/con/ledm/productusagedyn/2007/12/11">
 <pudyn:PrinterSubunit>
  <dd:TotalImpressions PEID="5082">{total}</dd:TotalImpressions>
  <dd:MonochromeImpressions>{mono}</dd:MonochromeImpressions>
  <dd:ColorImpressions>{color}</dd:ColorImpressions>
  <dd:JamEvents>{jams}</dd:JamEvents><dd:MispickEvents>1</dd:MispickEvents>
 </pudyn:PrinterSubunit>
 <pudyn:ScannerEngineSubunit><dd:ScanImages>{scans}</dd:ScanImages></pudyn:ScannerEngineSubunit>
 <pudyn:CopyApplicationSubunit><dd:TotalImpressions>{copies}</dd:TotalImpressions></pudyn:CopyApplicationSubunit>
</pudyn:ProductUsageDyn>"""


# -- IPP response ------------------------------------------------------------------------
def _value(tag, name, raw):
    return (bytes([tag]) + struct.pack(">H", len(name)) + name.encode()
            + struct.pack(">H", len(raw)) + raw)


def ipp_response(attrs, request_id=1, status=0):
    """attrs: [(tag, name, [values])]; ints for tags 0x21/0x23, str for the others."""
    out = struct.pack(">BBHI", 1, 1, status, request_id)
    out += b"\x01" + _value(0x47, "attributes-charset", b"utf-8") \
        + _value(0x48, "attributes-natural-language", b"en")
    out += b"\x04"
    for tag, name, values in attrs:
        for i, value in enumerate(values):
            raw = struct.pack(">i", value) if tag in (0x21, 0x23) else value.encode()
            out += _value(tag, name if i == 0 else "", raw)
    return out + b"\x03"


def ipp_attrs(state=3, reasons=("none",), levels=(-3, -3, -3, -3), serial=SERIAL):
    return [
        (0x41, "printer-make-and-model", [MODEL]),
        (0x41, "printer-device-id", [
            f"MFG:HP;MDL:{MODEL};CMD:PCL3GUI,PJL,Automatic,JPEG,PCLM,AppleRaster,"
            f"PWGRaster,DW-PCL,802.11,DESKJET,DYN;CLS:PRINTER;DES:{PRODUCT};"
            f"CID:HPDeskjetSmartTank;LEDMDIS:USB#FF#CC#00,USB#07#01#02,USB#FF#04#01;"
            f"SN:{serial};"]),
        (0x23, "printer-state", [state]),
        (0x44, "printer-state-reasons", list(reasons)),
        (0x41, "printer-firmware-string-version", [FIRMWARE]),
        (0x42, "marker-names", ["Cyan ink", "Magenta ink", "Yellow ink", "Black ink"]),
        (0x42, "marker-colors", ["#00FFFF", "#FF00FF", "#FFFF00", "#000000"]),
        (0x21, "marker-levels", list(levels)),
        (0x21, "marker-low-levels", [5, 5, 5, 5]),
        (0x44, "marker-types", ["ink"] * 4),
    ]


class FakeHp:
    """The fake printer's network side. Change `ledm`, `ipp`, `ipp_enabled` or
    `ledm_enabled` between reads to give other answers."""

    INKS = [("Cyan", "C", "ok", None), ("Magenta", "M", "ok", None),
            ("Yellow", "Y", "low", None), ("Black", "K", "ok", None)]

    def __init__(self):
        self.requests = []          # (method, path, body)
        self.ipp_enabled = self.ledm_enabled = True
        self.ledm = {"/DevMgmt/ProductConfigDyn.xml": config_xml(),
                     "/DevMgmt/ProductStatusDyn.xml": status_xml(),
                     "/DevMgmt/ConsumableConfigDyn.xml": consumables_xml(self.INKS),
                     "/DevMgmt/ProductUsageDyn.xml": usage_xml()}
        self.ipp = ipp_attrs()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code, body, kind):
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                fake.requests.append(("GET", self.path, b""))
                if fake.ledm_enabled and self.path in fake.ledm:
                    self._send(200, fake.ledm[self.path].encode(), "text/xml")
                else:
                    self._send(404, b"not found", "text/plain")

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                fake.requests.append(("POST", self.path, body))
                if fake.ipp_enabled and self.path == "/ipp/print":
                    rid = struct.unpack(">I", body[4:8])[0] if len(body) >= 8 else 1
                    self._send(200, ipp_response(fake.ipp, rid), "application/ipp")
                else:
                    self._send(404, b"not found", "text/plain")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def address(self):
        return f"127.0.0.1:{self.server.server_address[1]}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    start, stop = __enter__, lambda self: self.__exit__()


def usb_unit(serial=SERIAL, instance="6&1a2b3c4d&0&0001", pid="4454", ports=("USB090",)):
    """The Smart Tank 580 as pnp.hp_usb_printers() reports it."""
    return pnp.UsbPrinter(instance, ("HP Smart Tank 580-590 series",
                                     "Smart Tank 580-590 series"), pid, ports,
                          pnp.HP_VENDOR, serial)
