# DPSS driver firmware core: operating states, command set, current limits and ramps,
# frame sequencing and time stamps. Hardware access goes through 'hw' (hw_pico.py on the Pico 2,
# a simulated board in sim/), so the same code runs in MicroPython and in the PC simulation.
#
# States (Rev 2 document, Fig. "Firmware operating states"):
#   OFF      hardware ENABLE low (chain open, or chain closed but the fault latch not re-armed yet)
#   ARMED    ENABLE high (after RESET with the chain closed), set points at 0
# The ENABLE latch (74LVC2G74) is cleared by any opening of the chain and is only set again by a
# FAULT_RST pulse from the PC's RESET command: re-arming is always a deliberate operator action.
# On any FAULT the firmware also stops toggling the watchdog, so the hardware chain opens as well
# (defence in depth: the lasers go off even if the firmware's own switch-off path failed).
#   READY    PC sent ARM, set points ramped to their values, laser gates closed
#   EMITTING at least one LASER_ON line high (manual ON, or a hardware frame running)
#   FAULT    latched; cleared by RESET only when the chain is closed again
import config as C
import dpss_pio as PIOX

OFF, ARMED, READY, EMITTING, FAULT = 'OFF', 'ARMED', 'READY', 'EMITTING', 'FAULT'
MODE_PC, MODE_TRIG = 'PC', 'TRIG'

CODE_FS = 0xFFFF


def ma_to_code(ma):
    """Set point (mA) -> DAC8565 code. I = GM * V_DAC, V_DAC = code / 65536 * VREF."""
    v = ma / C.GM_MA_PER_V
    code = int(round(v / C.DAC_VREF_V * 65536))
    return max(0, min(CODE_FS, code))


def code_to_ma(code):
    return code / 65536 * C.DAC_VREF_V * C.GM_MA_PER_V


class TsDecoder:
    """Turns raw edge_ts counter values into time stamps in clock cycles since the PIO start."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.prev = None
        self.t = 0
        self.level = 0           # level after the last edge (0 -> next edge is rising)
        self.events = []         # (t_cycles, rising)

    def feed(self, raw):
        if raw >= 0xFFFFFFF0:    # counter wrap marker (every 57 s), not a real edge
            return None
        if self.prev is None:
            self.t = PIOX.TS_CYCLES_PER_COUNT * (0xFFFFFFFF - raw)
        else:
            d = (self.prev - raw) & 0xFFFFFFFF
            self.t += PIOX.TS_CYCLES_PER_COUNT * d + PIOX.TS_EVENT_CYC
        self.prev = raw
        self.level ^= 1
        ev = (self.t, self.level == 1)
        self.events.append(ev)
        if len(self.events) > 64:
            self.events.pop(0)
        return ev


class Controller:
    def __init__(self, hw):
        self.hw = hw
        self.out = []                                   # lines to send to the PC
        self.state = OFF
        self.mode = MODE_PC
        self.fault_reason = ''
        self.limit_ma = [C.I_LIMIT_DEFAULT_MA] * C.N_CH
        self.set_ma = [0.0] * C.N_CH                    # requested set points
        self.code_now = [0] * C.N_CH                    # DAC codes written
        self.code_target = [0] * C.N_CH
        self.mask_on = 0                                # manual LASER_ON lines
        self.settle_us = C.SETTLE_US_DEFAULT
        self.lead_us = C.LEAD_US_DEFAULT
        self.trig_us = C.TRIG_US_DEFAULT
        self.gap_us = C.CAM_MIN_PERIOD_US
        self.cam_trig_enabled = False
        self.frames_pending = []                        # (ch, words) not yet in the PIO FIFO
        self.frames_running = []                        # ch of frames in the PIO
        self.frame_t0 = None
        self.frames_done = 0
        self.t_last_cmd = hw.ticks_ms()
        self.t_last_ramp = hw.ticks_ms()
        self.t_last_wdi = hw.ticks_ms()
        self.wdi_hold = False
        self.ts_stage = TsDecoder()
        self.ts_expos = TsDecoder()
        lim = hw.load_limits()
        if lim:
            for i in range(min(len(lim), C.N_CH)):
                self.limit_ma[i] = min(float(lim[i]), C.I_HW_CLAMP_MA)
        hw.safe_outputs()                               # S4: everything off at power-up

    # ------------------------------------------------------------------ helpers
    def say(self, s):
        self.out.append(s)

    def _all_off_now(self):
        self.hw.seq_abort()
        self.frames_pending = []
        self.frames_running = []
        self.mask_on = 0
        self.hw.set_laser_mask(0)
        for ch in range(C.N_CH):
            self.code_now[ch] = self.code_target[ch] = 0
            self.hw.dac_write(ch, 0)
        self.cam_trig_enabled = False
        self.hw.cam_trig_enable(False)
        self.hw.stage_out_enable(False)

    def fault(self, reason):
        if self.state != FAULT:
            self._all_off_now()
            self.state = FAULT
            self.fault_reason = reason
            self.wdi_hold = True             # stop the watchdog -> hardware chain opens too
            self.say('EVT FAULT %s' % reason)

    def chain_ok(self):
        return self.hw.enable() and self.hw.temp_ok()

    # ------------------------------------------------------------------ periodic work
    def tick(self):
        hw = self.hw
        now = hw.ticks_ms()
        # watchdog: only toggled while this loop runs (a hung firmware opens the chain)
        if not self.wdi_hold and hw.ticks_diff(now, self.t_last_wdi) >= C.WDI_PERIOD_MS:
            hw.wdi_toggle()
            self.t_last_wdi = now
        en, tok = hw.enable(), hw.temp_ok()
        if self.state == OFF:
            if en and tok:
                self.state = ARMED
                self.say('EVT ARMED')
        elif self.state == ARMED:
            if not (en and tok):
                self.state = OFF
                self.say('EVT OFF chain open')
                self._all_off_now()
        elif self.state in (READY, EMITTING):
            if not tok:
                self.fault('TEMP_NOT_OK')
            elif not en:
                self.fault('CHAIN_OPEN')
            elif hw.ticks_diff(now, self.t_last_cmd) > C.HEARTBEAT_MS:
                self.fault('USB_TIMEOUT')
        # set-point ramps (E5)
        if self.state in (READY, EMITTING, ARMED) and hw.ticks_diff(now, self.t_last_ramp) >= C.RAMP_STEP_MS:
            steps = hw.ticks_diff(now, self.t_last_ramp) // C.RAMP_STEP_MS
            self.t_last_ramp = now
            max_step = max(1, (ma_to_code(C.I_HW_CLAMP_MA) * C.RAMP_STEP_MS) // C.RAMP_MIN_MS) * steps
            for ch in range(C.N_CH):
                d = self.code_target[ch] - self.code_now[ch]
                if d:
                    d = max(-max_step, min(max_step, d))
                    self.code_now[ch] += d
                    hw.dac_write(ch, self.code_now[ch])
        # hardware frames
        if self.mode == MODE_TRIG and self.state in (READY, EMITTING):
            self._service_frames(now)
        self._service_ts()

    def _service_frames(self, now):
        hw = self.hw
        while self.frames_pending and hw.seq_space() >= 4:
            ch, words = self.frames_pending.pop(0)
            hw.seq_put(words)
            self.frames_running.append(ch)
        for _ in range(hw.seq_done_count()):
            ch = self.frames_running.pop(0) if self.frames_running else -1
            self.frames_done += 1
            self.frame_t0 = None
            self.say('EVT FRAME_DONE ch=%d n=%d' % (ch + 1, self.frames_done))
        if self.frames_running:
            self.state = EMITTING
            if hw.laser_mask() and self.frame_t0 is None:
                self.frame_t0 = now
            if self.frame_t0 is not None and hw.ticks_diff(now, self.frame_t0) > C.MAX_EMIT_MS_DEFAULT:
                self.fault('EXPOSURE_TIMEOUT')
        elif self.state == EMITTING and not self.mask_on:
            self.state = READY

    def _service_ts(self):
        f = C.SYS_CLK_HZ / 1e6
        for raw in self.hw.ts_read('stage'):
            ev = self.ts_stage.feed(raw)
            if ev and ev[1]:
                self.say('EVT TS STAGE_IN t_us=%.3f' % (ev[0] / f))
        for raw in self.hw.ts_read('expos'):
            ev = self.ts_expos.feed(raw)
            if ev:
                self.say('EVT TS EXPOS_%s t_us=%.3f' % ('START' if ev[1] else 'END', ev[0] / f))

    # ------------------------------------------------------------------ commands
    def handle(self, line):
        self.t_last_cmd = self.hw.ticks_ms()
        parts = line.strip().split()
        if not parts:
            return
        cmd, args = parts[0].upper(), parts[1:]
        fn = getattr(self, 'cmd_' + cmd.replace('*', 'STAR_').replace('?', 'Q'), None)
        if fn is None:
            self.say('ERR unknown command')
            return
        try:
            r = fn(*args)
            self.say('OK' if r is None else 'OK ' + r)
        except CmdError as e:
            self.say('ERR %s' % e.args[0])
        except (ValueError, TypeError, IndexError):
            self.say('ERR bad arguments')

    def _ch(self, s):
        ch = int(s) - 1
        if not 0 <= ch < C.N_CH:
            raise CmdError('channel must be 1..%d' % C.N_CH)
        return ch

    def cmd_STAR_IDNQ(self):
        return C.FW_VERSION

    def cmd_PING(self):
        return None

    def cmd_STATUS(self):
        ma = ','.join('%.2f' % code_to_ma(c) for c in self.code_now)
        sp = ','.join('%.2f' % v for v in self.set_ma)
        lim = ','.join('%.1f' % v for v in self.limit_ma)
        return ('state=%s mode=%s enable=%d temp_ok=%d i_ma=%s set_ma=%s limit_ma=%s on=%d camtrig=%d '
                'settle_us=%d lead_us=%d trig_us=%d gap_us=%d frames_done=%d fault=%s' % (
                    self.state, self.mode, self.hw.enable(), self.hw.temp_ok(), ma, sp, lim,
                    self.mask_on | self.hw.laser_mask(), self.cam_trig_enabled, self.settle_us,
                    self.lead_us, self.trig_us, self.gap_us, self.frames_done, self.fault_reason or '-'))

    def cmd_SET(self, ch, ma):
        ch = self._ch(ch); ma = float(ma)
        if ma < 0 or ma > self.limit_ma[ch]:
            raise CmdError('outside 0..%.1f mA (unit limit)' % self.limit_ma[ch])
        self.set_ma[ch] = ma
        if self.state in (READY, EMITTING):
            self.code_target[ch] = ma_to_code(ma)
        return None

    def cmd_LIMIT(self, ch, ma):
        ch = self._ch(ch); ma = float(ma)
        if ma <= 0 or ma > C.I_HW_CLAMP_MA:
            raise CmdError('limit must be 0..%.0f mA' % C.I_HW_CLAMP_MA)
        if self.set_ma[ch] > ma:
            raise CmdError('set point above new limit')
        self.limit_ma[ch] = ma
        self.hw.save_limits(self.limit_ma)
        return None

    def cmd_ARM(self):
        if self.state == FAULT:
            raise CmdError('fault latched, send RESET')
        if self.state == OFF or not self.chain_ok():
            raise CmdError('safety chain open')
        if self.state == ARMED:
            for ch in range(C.N_CH):
                self.code_target[ch] = ma_to_code(self.set_ma[ch])
            self.state = READY
        return None

    def cmd_DISARM(self):
        self.hw.seq_abort()
        self.frames_pending, self.frames_running = [], []
        self.mask_on = 0
        self.hw.set_laser_mask(0)
        self.code_target = [0] * C.N_CH            # ramp down to zero
        self.cam_trig_enabled = False
        self.hw.cam_trig_enable(False)
        if self.state in (READY, EMITTING):
            self.state = ARMED
        return None

    def cmd_ON(self, ch):
        ch = self._ch(ch)
        if self.mode != MODE_PC:
            raise CmdError('ON/OFF only in MODE PC')
        if self.state not in (READY, EMITTING):
            raise CmdError('not ARMed')
        if self.code_now[ch] != self.code_target[ch]:
            raise CmdError('set point still ramping')
        self.mask_on |= 1 << ch
        self.hw.set_laser_mask(self.mask_on)
        self.state = EMITTING
        return None

    def cmd_OFF(self, ch=None):
        if ch is None or str(ch).upper() == 'ALL':
            self.mask_on = 0
        else:
            self.mask_on &= ~(1 << self._ch(ch))
        self.hw.set_laser_mask(self.mask_on)
        if self.state == EMITTING and not self.mask_on and not self.frames_running:
            self.state = READY
        return None

    def cmd_MODE(self, m):
        m = m.upper()
        if m not in (MODE_PC, MODE_TRIG):
            raise CmdError('MODE PC or MODE TRIG')
        if self.state == EMITTING:
            raise CmdError('lasers on')
        self.mask_on = 0
        self.hw.set_mode(m)
        self.mode = m
        if m == MODE_PC:
            self.cam_trig_enabled = False
            self.hw.cam_trig_enable(False)
        return None

    def _us_arg(self, v, lo, hi):
        v = int(v)
        if not lo <= v <= hi:
            raise CmdError('value must be %d..%d us' % (lo, hi))
        return v

    def cmd_SETTLE(self, us):
        self.settle_us = self._us_arg(us, 0, 1_000_000); return None

    def cmd_LEAD(self, us):
        self.lead_us = self._us_arg(us, 0, 1_000_000); return None

    def cmd_TRIGW(self, us):
        self.trig_us = self._us_arg(us, 1, C.CAM_TRIG_MAX_US); return None

    def cmd_GAP(self, us):
        self.gap_us = self._us_arg(us, 0, 1_000_000); return None

    def cmd_CAMTRIG(self, onoff):
        on = onoff.upper() == 'ON'
        if on and self.mode != MODE_TRIG:
            raise CmdError('camera trigger only in MODE TRIG')
        if on and self.state not in (READY, EMITTING):
            raise CmdError('not ARMed')
        self.cam_trig_enabled = on
        self.hw.cam_trig_enable(on)
        return 'jumper JP501 must also be closed' if on else None

    def _frame(self, ch, wait_stage, settle_us):
        f = C.SYS_CLK_HZ
        if self.code_target[ch] == 0:
            raise CmdError('channel %d set point is 0' % (ch + 1))
        return PIOX.frame_words(wait_stage,
                                PIOX.reg_for(settle_us, f, PIOX.OVH_SETTLE if wait_stage else PIOX.OVH_GAP),
                                PIOX.reg_for(self.lead_us, f, PIOX.OVH_LEAD),
                                PIOX.reg_for(self.trig_us, f, PIOX.OVH_TRIG),
                                1 << ch)

    def cmd_POS(self, chans, wait='WAIT'):
        """Queue the frames of one stage position. 'chans' = order of lasers, e.g. 1,2,3,4.
        The first frame waits for the stage in-position edge (unless NOWAIT); the following
        frames start 'gap_us' after the previous exposure ended (camera read-out)."""
        if self.mode != MODE_TRIG:
            raise CmdError('POS only in MODE TRIG')
        if self.state not in (READY, EMITTING):
            raise CmdError('not ARMed')
        lst = [self._ch(c) for c in chans.split(',')]
        if self.cam_trig_enabled and self.gap_us + self.lead_us < C.CAM_MIN_PERIOD_US:
            raise CmdError('gap+lead below camera minimum period %d us' % C.CAM_MIN_PERIOD_US)
        frames = []
        for i, ch in enumerate(lst):
            first = i == 0
            frames.append((ch, self._frame(ch, first and wait.upper() == 'WAIT',
                                           self.settle_us if first else self.gap_us)))
        self.frames_pending += frames
        return '%d frames queued' % len(frames)

    def cmd_ABORT(self):
        self.hw.seq_abort()
        self.frames_pending, self.frames_running = [], []
        self.hw.set_laser_mask(self.mask_on)
        if self.state == EMITTING and not self.mask_on:
            self.state = READY
        return None

    def cmd_STAGEPULSE(self, us=None):
        us = C.STAGE_PULSE_US_DEFAULT if us is None else self._us_arg(us, 1, 100_000)
        self.hw.stage_out_enable(True)
        self.hw.stage_pulse(PIOX.reg_for(us, C.SYS_CLK_HZ, 2))
        return None

    def cmd_RESET(self):
        """Re-arm the hardware ENABLE latch (from OFF or FAULT). Needs key, interlock and
        temperature OK; the set points are cleared and must be sent again."""
        if self.state not in (OFF, FAULT):
            return 'already armed'
        if not self.hw.temp_ok():
            raise CmdError('temperature not OK')
        self.wdi_hold = False
        self.hw.wdi_toggle()
        self.t_last_wdi = self.hw.ticks_ms()
        self.hw.fault_rst_pulse()
        if not self.hw.enable():
            raise CmdError('chain still open (key, interlock or watchdog) - retry')
        self.fault_reason = ''
        self.set_ma = [0.0] * C.N_CH
        self.state = ARMED
        self.say('EVT ARMED')
        return None


class CmdError(Exception):
    pass
