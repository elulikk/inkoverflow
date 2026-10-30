"""A fake L3150 for hardware-free tests: the library's MockPrinter plus the D4 data
socket 0x40 and a cleaning state, behaving like the printer in the USB capture."""
from epson_usb.backends.mock import MockConfig, MockPrinter, MockTransport
from epson_usb.d4 import build_packet
from epson_usb.status import ELEMENT_STATUS, build_st2

READ_KEY = (151, 7)
WRITE_KEY = b"Maribaya"
MAIN_PAD = (48, 49, 47)  # low, high, top byte (the backend's order)

CLEANING_BYTES = {0x01: 28, 0x02: 60, 0x03: 90, 0x04: 400}  # points added per mode


class FakeL3150(MockPrinter):
    def __init__(self, counter=5690, status_script=None, error_on_cleaning=False):
        cells = {48: counter & 0xFF, 49: (counter >> 8) & 0xFF, 47: (counter >> 16) & 0xFF,
                 50: 0, 51: 0}
        super().__init__(MockConfig(model_name="L3150", read_key=READ_KEY,
                                    write_key=WRITE_KEY, serial="X5E9205615",
                                    eeprom=cells))
        self.sockets_open = set()
        self.data_packets = []       # (psid, ssid, payload) received on the data socket
        self.cleaning_polls_left = 0
        self.pending_points = 0
        self.error_on_cleaning = error_on_cleaning
        self.status_code = 0x04
        self.polls_idle_before = 0

    # status reflects the current state
    def _status_elements(self):
        elements = [(ELEMENT_STATUS, bytes([self.status_code]))]
        if self.status_code == 0x00:
            elements.append((0x02, b"\x10"))
        return elements + [(0x06, b"\x01\x00")]

    def _frame_reply(self, payload):
        if payload[:2] == b"st":
            reply = super()._frame_reply(payload)
            if self.cleaning_polls_left > 0:
                self.cleaning_polls_left -= 1
                if self.cleaning_polls_left == 0:
                    self._finish_cleaning()
            return reply
        return super()._frame_reply(payload)

    def _finish_cleaning(self):
        value = self.config.eeprom
        counter = value[48] + (value[49] << 8) + (value[47] << 16) + self.pending_points
        value[48], value[49], value[47] = counter & 0xFF, (counter >> 8) & 0xFF, counter >> 16
        self.pending_points = 0
        self.status_code = 0x04

    def _handle_packet(self, packet):
        if packet.psid == 0x40:
            self.data_packets.append((packet.psid, packet.ssid, packet.payload))
            if packet.payload[:2] == b"\x1b\x7c" and packet.payload[7:10] == b"\x84\x7b\x42":
                mode = packet.payload[10]
                self.pending_points = CLEANING_BYTES.get(mode, 0)
                if self.error_on_cleaning:
                    self.status_code = 0x00
                else:
                    self.status_code = 0x07
                    self.cleaning_polls_left = 4
            return
        if packet.psid == 0 and packet.payload and packet.payload[0] in (0x01, 0x03, 0x04) \
                and len(packet.payload) >= 3 and packet.payload[1] == 0x40:
            sock = packet.payload[1]
            opcode = packet.payload[0]
            if opcode == 0x01:
                self.sockets_open.add(sock)
                self._control_reply(bytes([0x81, 0x00, sock, sock, 0x04, 0x00, 0x04, 0x00,
                                           0x00, 0x00]))
            elif opcode == 0x04:
                self._control_reply(bytes([0x84, 0x00, sock, sock, 0x00, 0x64]))
            else:
                self._control_reply(bytes([0x83, 0x00, sock, sock]))
            return
        super()._handle_packet(packet)


def make_transport(printer=None, **kwargs):
    printer = printer or FakeL3150(**kwargs)
    transport = MockTransport(printer=printer)
    transport.open()
    return transport, printer
