# Hardware layer for the Raspberry Pi Pico 2 (RP2350, MicroPython >= 1.24).
import time, json
from machine import Pin, SPI, mem32
import rp2
import config as C
import dpss_pio as PIOX
from dac8565 import DAC8565

PIO0_BASE = 0x50200000          # RP2350 PIO0 registers
REG_SET_ALIAS = 0x2000          # atomic bit-set alias
SM_SEQ, SM_TS_STAGE, SM_TS_EXPOS, SM_PULSE = 0, 1, 2, 4   # PIO0: SM0..2, PIO1: SM4


class PicoHW:
    def __init__(self):
        # --- safe levels first (S4): buffers disabled, lasers off ---
        self.cam_oe_n = Pin(C.PIN_CAM_OE_N, Pin.OUT, value=1)
        self.stage_oe_n = Pin(C.PIN_STAGE_OE_N, Pin.OUT, value=1)
        self.laser = [Pin(C.PIN_LASER_ON_BASE + i, Pin.OUT, value=0) for i in range(C.N_CH)]
        self.wdi = Pin(C.PIN_WDI, Pin.OUT, value=0)
        self.frst = Pin(C.PIN_FAULT_RST, Pin.OUT, value=0)
        self.p_enable = Pin(C.PIN_ENABLE, Pin.IN)
        self.p_temp = Pin(C.PIN_TEMP_OK, Pin.IN)
        # trigger inputs read by the PIO ('wait gpio' / 'jmp pin'): set them up as digital inputs
        # (on the board they are driven by the 74LVC1G17 buffers, so no internal pull is needed)
        self.p_stage_in = Pin(C.PIN_STAGE_IN, Pin.IN)
        self.p_cam_expos = Pin(C.PIN_CAM_EXPOS, Pin.IN)
        # --- DAC on SPI0 (mode 1). NOTE: SPI0's default MISO is GPIO16 = CAM_OE_N on this board,
        # so the pin is re-claimed as an output right after the SPI is created.
        self.spi = SPI(0, baudrate=10_000_000, polarity=0, phase=1, bits=8, firstbit=SPI.MSB,
                       sck=Pin(C.PIN_DAC_SCLK), mosi=Pin(C.PIN_DAC_DIN))
        self.cam_oe_n = Pin(C.PIN_CAM_OE_N, Pin.OUT, value=1)
        self.dac = DAC8565(self.spi, Pin(C.PIN_DAC_SYNC, Pin.OUT, value=1))
        self.dac.init()
        self.mode = 'PC'
        f = C.SYS_CLK_HZ
        self.sm_seq = None
        self.sm_ts_stage = rp2.StateMachine(SM_TS_STAGE, PIOX.edge_ts, freq=f, jmp_pin=Pin(C.PIN_STAGE_IN))
        self.sm_ts_expos = rp2.StateMachine(SM_TS_EXPOS, PIOX.edge_ts, freq=f, jmp_pin=Pin(C.PIN_CAM_EXPOS))
        # start both time-stamp counters on the same clock edge (common time base)
        mem32[PIO0_BASE + REG_SET_ALIAS] = ((1 << SM_TS_STAGE) | (1 << SM_TS_EXPOS)) * 0x101
        self.sm_pulse = rp2.StateMachine(SM_PULSE, PIOX.pulse, freq=f, set_base=Pin(C.PIN_STAGE_OUT))
        self.sm_pulse.active(1)

    # ---- time ----
    def ticks_ms(self):
        return time.ticks_ms()

    def ticks_diff(self, a, b):
        return time.ticks_diff(a, b)

    # ---- safety I/O ----
    def enable(self):
        return self.p_enable.value() == 1

    def temp_ok(self):
        return self.p_temp.value() == 1

    def wdi_toggle(self):
        self.wdi.toggle()

    def fault_rst_pulse(self):
        self.frst.value(1); time.sleep_us(20); self.frst.value(0); time.sleep_us(20)

    def safe_outputs(self):
        self.set_laser_mask(0)
        for ch in range(C.N_CH):
            self.dac.write(ch, 0)
        self.cam_trig_enable(False)
        self.stage_out_enable(False)

    # ---- DAC ----
    def dac_write(self, ch, code):
        self.dac.write(ch, code)

    # ---- laser gates ----
    def set_mode(self, mode):
        if mode == self.mode:
            return
        if mode == 'TRIG':
            self.sm_seq = rp2.StateMachine(SM_SEQ, PIOX.frame_seq, freq=C.SYS_CLK_HZ,
                                           out_base=Pin(C.PIN_LASER_ON_BASE), sideset_base=Pin(C.PIN_CAM_TRIG))
            self.sm_seq.active(1)
        else:
            if self.sm_seq:
                self.seq_abort(); self.sm_seq.active(0)
            self.laser = [Pin(C.PIN_LASER_ON_BASE + i, Pin.OUT, value=0) for i in range(C.N_CH)]
            Pin(C.PIN_CAM_TRIG, Pin.OUT, value=0)
        self.mode = mode

    def set_laser_mask(self, mask):
        if self.mode == 'PC':
            for i in range(C.N_CH):
                self.laser[i].value((mask >> i) & 1)
        elif self.sm_seq and mask == 0:
            self.seq_abort()

    def laser_mask(self):
        m = 0
        for i in range(C.N_CH):
            m |= Pin(C.PIN_LASER_ON_BASE + i).value() << i   # reads the pad level in any mode
        return m

    # ---- hardware frames ----
    def seq_space(self):
        return 4 - self.sm_seq.tx_fifo()

    def seq_put(self, words):
        for w in words:
            self.sm_seq.put(w)

    def seq_done_count(self):
        n = 0
        while self.sm_seq.rx_fifo():
            self.sm_seq.get(); n += 1
        return n

    def seq_abort(self):
        if not self.sm_seq:
            return
        sm = self.sm_seq
        sm.active(0)
        sm.exec("mov(pins, null) .side(0)")       # lasers off, trigger low
        sm.restart()
        while sm.rx_fifo():
            sm.get()
        self.sm_seq = rp2.StateMachine(SM_SEQ, PIOX.frame_seq, freq=C.SYS_CLK_HZ,
                                       out_base=Pin(C.PIN_LASER_ON_BASE), sideset_base=Pin(C.PIN_CAM_TRIG))
        self.sm_seq.active(1)

    # ---- camera / stage outputs ----
    def cam_trig_enable(self, on):
        self.cam_oe_n.value(0 if on else 1)

    def stage_out_enable(self, on):
        self.stage_oe_n.value(0 if on else 1)

    def stage_pulse(self, reg):
        self.sm_pulse.put(reg)

    # ---- time stamps ----
    def ts_read(self, which):
        sm = self.sm_ts_stage if which == 'stage' else self.sm_ts_expos
        out = []
        while sm.rx_fifo():
            out.append(sm.get())
        return out

    # ---- per-unit limits in flash ----
    def load_limits(self):
        try:
            with open(C.LIMITS_FILE) as f:
                return json.load(f)
        except OSError:
            return None

    def save_limits(self, lim):
        with open(C.LIMITS_FILE, 'w') as f:
            json.dump(lim, f)
