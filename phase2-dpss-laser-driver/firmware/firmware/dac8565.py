# DAC8565 (TI, 16-bit, 4 channels) driver.
# Frame (24 bits, MSB first), from the DAC8565 datasheet (SBAS411):
#   DB23..22 = 0 | DB21 LD1 | DB20 LD0 | DB19 = 0 | DB18..17 DAC select | DB16 PD0 | DB15..0 data
#   LD1:LD0 = 01 -> single-channel update (write buffer + update that DAC at once)
#   0x011000      -> internal 2.5 V reference always powered up
# DIN is latched on the falling edge of SCLK -> SPI mode 1 (CPOL = 0, CPHA = 1).
# On the board: LDAC = GND (update on the 24th clock), ENABLE = GND, RSTSEL = GND (binary coding,
# reset to zero scale), RST = 3.3 V.

CMD_SINGLE_UPDATE = 0x10           # LD1=0, LD0=1
REF_ALWAYS_ON = 0x011000


def frame(channel, code):
    """24-bit word that writes and updates one channel (0..3 = A..D)."""
    if not 0 <= channel <= 3:
        raise ValueError("channel")
    code = int(code)
    if not 0 <= code <= 0xFFFF:
        raise ValueError("code")
    return ((CMD_SINGLE_UPDATE | (channel << 1)) << 16) | code


def to_bytes(word24):
    return bytes(((word24 >> 16) & 0xFF, (word24 >> 8) & 0xFF, word24 & 0xFF))


class DAC8565:
    def __init__(self, spi, sync_pin):
        self.spi = spi                  # machine.SPI(0, baudrate=10_000_000, polarity=0, phase=1, ...)
        self.sync = sync_pin            # machine.Pin, output, idle high
        self.sync.value(1)
        self.codes = [0, 0, 0, 0]

    def _send(self, word24):
        self.sync.value(0)
        self.spi.write(to_bytes(word24))
        self.sync.value(1)

    def init(self):
        self._send(REF_ALWAYS_ON)
        for ch in range(4):
            self.write(ch, 0)

    def write(self, channel, code):
        self._send(frame(channel, code))
        self.codes[channel] = int(code)
