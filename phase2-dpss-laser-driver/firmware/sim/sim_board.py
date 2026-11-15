# Simulated driver board for the firmware core (virtual time, 1 us resolution).
# Models: safety chain (key, interlock, TEMP_OK), TPS3823 watchdog, 74LVC2G74 ENABLE latch,
# DAC8565 writes, LASER_ON gates, the PIO frame sequencer (timing formulas measured in the
# cycle-accurate emulator), time-stamp counters, a stage and a camera.
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, '../firmware')]
import fake_rp2; fake_rp2.install()
import config as C
import dpss_pio as P

F = C.SYS_CLK_HZ


class SimHW:
    WD_TIMEOUT_US = 1_600_000       # TPS3823-33 typical watchdog timeout
    WD_RESET_US = 200_000           # reset pulse length

    def __init__(self):
        self.t_us = 0
        self.key = True; self.interlock = True; self.temp = True
        self.latch = False                       # ENABLE latch (cleared at power-up)
        self.wd_last = 0; self.wd_reset_until = -1
        self.dac = [0] * 4; self.dac_log = []    # (t_us, ch, code)
        self.mask_pc = 0; self.mode = 'PC'
        self.cam_oe = False; self.stage_oe = False
        self.fifo = []                           # frames waiting (words)
        self.running = None                      # dict of the active frame
        self.done = 0
        self.laser_log = []                      # (t_us, mask)
        self.trig_log = []                       # (t_on_us, t_off_us)
        self.ts = {'stage': [], 'expos': []}
        self.ts_events = {'stage': [], 'expos': []}   # true edge times (cycles) for checking
        self.stage_edges = []                    # future rising edges of STAGE_IN (us)
        self.cam_delay_us = 2.0                  # camera trigger -> exposure start (mode B)
        self.cam_exposure_us = 10_000.0
        self.cam_external = []                   # mode A: (start_us, end_us) exposures by the PC
        self.cam_responds = True
        self.stage_pulses = []
        self.limits = None
        self._mask_seq = 0
        self.frame_log = []

    # ---------------- time ----------------
    def ticks_ms(self):
        return self.t_us // 1000

    def ticks_diff(self, a, b):
        return a - b

    def advance(self, dt_us):
        end = self.t_us + dt_us
        while self.t_us < end:
            step = min(end - self.t_us, 50)
            self.t_us += step
            self._update()

    # ---------------- safety chain ----------------
    def _wd_ok(self):
        if self.t_us - self.wd_last > self.WD_TIMEOUT_US:
            self.wd_reset_until = self.t_us + self.WD_RESET_US     # watchdog fires a reset pulse
            self.wd_last = self.wd_reset_until                     # timer restarts at reset release
        return not (self.t_us <= self.wd_reset_until)

    def safe_ok(self):
        return self.key and self.interlock and self.temp and self._wd_ok()

    def _update(self):
        if not self.safe_ok():
            self.latch = False                   # CLR of the 74LVC2G74
        self._run_frames()

    def enable(self):
        self._update()
        return self.latch

    def temp_ok(self):
        return self.temp

    def wdi_toggle(self):
        self.wd_last = self.t_us

    def fault_rst_pulse(self):
        if self.safe_ok():
            self.latch = True                    # D = 1 clocked in

    def safe_outputs(self):
        self.set_laser_mask(0)
        for ch in range(4):
            self.dac_write(ch, 0)
        self.cam_trig_enable(False); self.stage_out_enable(False)

    # ---------------- DAC / gates ----------------
    def dac_write(self, ch, code):
        self.dac[ch] = code; self.dac_log.append((self.t_us, ch, code))

    def set_mode(self, m):
        self.mode = m; self.mask_pc = 0; self._log_mask()

    def set_laser_mask(self, mask):
        if self.mode == 'PC':
            self.mask_pc = mask
        elif mask == 0:
            self.seq_abort()
        self._log_mask()

    def laser_mask(self):
        return self.mask_pc if self.mode == 'PC' else self._mask_seq

    def _log_mask(self):
        m = self.laser_mask() if self.latch else 0      # ENABLE low -> no current at all
        if not self.laser_log or self.laser_log[-1][1] != m:
            self.laser_log.append((self.t_us, m))

    def current_ma(self, ch):
        """Laser current from the hardware model: DAC -> gate (ENABLE AND LASER_ON) -> clamp."""
        on = self.latch and (self.laser_mask() >> ch) & 1
        v = self.dac[ch] / 65536 * C.DAC_VREF_V
        return min(v, 2.5) * C.GM_MA_PER_V if on else 0.0

    # ---------------- PIO frame sequencer (behavioural, cycle formulas from the emulator) -------
    def seq_space(self):
        return 4 if not self.fifo else 0

    def seq_put(self, words):
        self.fifo.append((self.t_us, tuple(words)))

    def seq_done_count(self):
        n, self.done = self.done, 0
        return n

    def seq_abort(self):
        self.fifo = []; self.running = None; self._mask_seq = 0; self._log_mask()

    def _run_frames(self):
        t = self.t_us
        if self.running is None and self.fifo and self.mode == 'TRIG':
            t_put, w = self.fifo.pop(0)
            settle = (w[3] & 0x0FFFFFFF); mask = (w[3] >> 28) & 0xF
            t0 = max(t_put, getattr(self, 't_free', 0))
            self.running = dict(wait=w[0], lead=w[1], trig=w[2], settle=settle, mask=mask,
                                t0=t0, phase='wait' if w[0] else 'settle')
        r = self.running
        if not r:
            return
        cyc = lambda us: us * F / 1e6
        if r['phase'] == 'wait':
            edges = [e for e in self.stage_edges if e >= r['t0']]
            if edges and t >= edges[0]:
                r['t_start'] = edges[0]; r['phase'] = 'settle'
                self.stage_edges.remove(edges[0])
            else:
                return
        if r['phase'] == 'settle':
            ovh = P.OVH_SETTLE if r['wait'] else P.OVH_GAP
            r.setdefault('t_start', r['t0'])
            r['t_on'] = r['t_start'] + (r['settle'] + ovh) / F * 1e6
            r['t_trig'] = r['t_on'] + (r['lead'] + P.OVH_LEAD) / F * 1e6
            r['t_trig_off'] = r['t_trig'] + (r['trig'] + P.OVH_TRIG) / F * 1e6
            r['phase'] = 'run'
        if r['phase'] == 'run':
            if t >= r['t_on'] and not r.get('on'):
                r['on'] = True; self._mask_seq = r['mask']; self._log_mask_at(r['t_on'])
            if t >= r['t_trig_off'] and not r.get('trig_done'):
                r['trig_done'] = True
                if self.cam_oe:
                    self.trig_log.append((r['t_trig'], r['t_trig_off']))
                # camera exposure: triggered by the board (mode B) or by the PC (mode A)
                if self.cam_oe and self.cam_responds:
                    r['exp'] = (r['t_trig'] + self.cam_delay_us, r['t_trig'] + self.cam_delay_us + self.cam_exposure_us)
                else:
                    ext = [e for e in self.cam_external if e[0] >= r['t_trig']]
                    r['exp'] = ext[0] if ext else None
            if r.get('trig_done') and r['exp'] and t >= r['exp'][1] + 2 / F * 1e6:
                t_off = r['exp'][1] + 2 / F * 1e6        # Expos low -> LASER OFF: 2 cycles
                self._mask_seq = 0; self._log_mask_at(t_off)
                self._ts_add('expos', r['exp'][0]); self._ts_add('expos', r['exp'][1])
                r['t_off'] = t_off
                self.t_free = t_off
                self.frame_log.append(dict(r))
                self.running = None; self.done += 1

    def _log_mask_at(self, t):
        m = self.laser_mask() if self.latch else 0
        self.laser_log.append((t, m))

    # ---------------- time stamps (encode like edge_ts so the firmware decoder is exercised) ------
    def _ts_add(self, which, t_us):
        cyc = int(round(t_us * F / 1e6))
        ev = self.ts_events[which]
        k = len(ev)
        # inverse of the decoder: t = 2*(0xFFFFFFFF - raw) + 3*k
        raw = 0xFFFFFFFF - (cyc - P.TS_EVENT_CYC * k) // P.TS_CYCLES_PER_COUNT
        ev.append(cyc)
        self.ts[which].append(raw & 0xFFFFFFFF)

    def stage_arrive(self, t_us):
        """Stage reaches the position at t_us: rising edge on STAGE_IN (and falls 1 ms later)."""
        self.stage_edges.append(t_us)
        self._ts_add('stage', t_us); self._ts_add('stage', t_us + 1000)

    def ts_read(self, which):
        out, self.ts[which] = self.ts[which], []
        return out

    # ---------------- outputs ----------------
    def cam_trig_enable(self, on):
        self.cam_oe = bool(on)

    def stage_out_enable(self, on):
        self.stage_oe = bool(on)

    def stage_pulse(self, reg):
        if self.stage_oe:
            self.stage_pulses.append((self.t_us, (reg + 2) / F * 1e6))

    def load_limits(self):
        return self.limits

    def save_limits(self, lim):
        self.limits = list(lim)


class SimLink:
    """Text link PC <-> simulated Pico: same lines as the USB serial port."""
    def __init__(self, hw=None):
        import dpss_core
        self.hw = hw or SimHW()
        self.ctl = dpss_core.Controller(self.hw)
        self.rx = []

    def step(self, dt_us=1000):
        self.hw.advance(dt_us)
        self.ctl.tick()
        self.rx += self.ctl.out; self.ctl.out = []

    def write(self, line):
        self.ctl.handle(line)
        self.rx += self.ctl.out; self.ctl.out = []

    def readline(self):
        return self.rx.pop(0) if self.rx else None
