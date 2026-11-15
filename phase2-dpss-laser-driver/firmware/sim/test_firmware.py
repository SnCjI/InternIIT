# Firmware verification against the Phase 2 requirements (run: python -m pytest -v sim/test_firmware.py)
import sys, os, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, '../firmware'), os.path.join(HERE, '../pc')]
import fake_rp2; fake_rp2.install()
import pytest
import config as C, dpss_pio as P, dac8565, dpss_core as K
from sim_board import SimHW, SimLink
from dpss_client import DPSSDriver, DriverError


def board():
    link = SimLink()
    drv = DPSSDriver(link)
    return link, link.hw, drv


def armed(ma=(300, 300, 300, 300)):
    link, hw, drv = board()
    link.step(1000)
    drv.reset()
    for i, m in enumerate(ma):
        drv.set_current(i + 1, m)
    drv.arm()
    for _ in range(200):           # let the ramps finish (>= 100 ms)
        link.step(1000)
    return link, hw, drv


# ---------------- DAC8565 frames (datasheet format) ----------------
def test_dac_frames():
    assert dac8565.frame(0, 0x1234) == 0x101234      # LD1:LD0 = 01, channel A
    assert dac8565.frame(3, 0xFFFF) == 0x16FFFF      # channel D
    assert dac8565.REF_ALWAYS_ON == 0x011000
    assert dac8565.to_bytes(0x101234) == b'\x10\x12\x34'


# ---------------- F2 / E2: current scaling and resolution ----------------
def test_current_scaling():
    assert K.ma_to_code(0) == 0
    assert K.ma_to_code(400) == 0xFFFF                 # 2.5 V full scale = 400 mA = hardware clamp
    lsb = K.code_to_ma(1)
    assert lsb < 0.1                                    # F2: <= 0.1 mA steps (6.1 uA per LSB)
    for ma in (0.1, 1.0, 123.4, 330.0):
        assert abs(K.code_to_ma(K.ma_to_code(ma)) - ma) <= lsb / 2 + 1e-9


# ---------------- S4: fail-safe power-up ----------------
def test_power_up_safe():
    link, hw, drv = board()
    assert hw.dac == [0, 0, 0, 0] and hw.laser_mask() == 0
    assert hw.cam_oe is False and hw.stage_oe is False
    assert hw.latch is False                            # ENABLE low until RESET
    st = drv.status()
    assert st['state'] == 'OFF'
    with pytest.raises(DriverError):
        drv.arm()


# ---------------- E3: per-unit limit, E2: hardware maximum ----------------
def test_limits():
    link, hw, drv = board()
    with pytest.raises(DriverError):
        drv.set_current(1, 331)                         # default unit limit 330 mA
    with pytest.raises(DriverError):
        drv.set_limit(1, 401)                           # above the 400 mA clamp / datasheet max
    drv.set_limit(1, 360)
    drv.set_current(1, 355)
    assert hw.limits[0] == 360                          # stored in flash


# ---------------- E5: ramp-limited set points ----------------
def test_ramp_at_least_100ms():
    link, hw, drv = board()
    drv.set_limit(1, 400); drv.reset(); drv.set_current(1, 400); drv.arm()
    t0 = hw.t_us
    while hw.dac[0] != 0xFFFF:
        link.step(1000)
    assert hw.t_us - t0 >= C.RAMP_MIN_MS * 1000         # 0 -> 400 mA takes >= 100 ms
    steps = [c for (_, ch, c) in hw.dac_log if ch == 0]
    jumps = max(b - a for a, b in zip(steps, steps[1:]))
    assert jumps <= K.ma_to_code(400) * C.RAMP_STEP_MS // C.RAMP_MIN_MS + 1


def test_on_refused_while_ramping():
    link, hw, drv = board()
    link.step(1000); drv.reset(); drv.set_current(2, 300); drv.arm()
    with pytest.raises(DriverError):
        drv.on(2)
    for _ in range(150):
        link.step(1000)
    drv.on(2)
    assert hw.laser_mask() == 0b0010
    assert abs(hw.current_ma(1) - 300) < 0.01


# ---------------- S1/S5: safety chain, watchdog, heartbeat ----------------
def test_interlock_opens_while_emitting():
    link, hw, drv = armed()
    drv.on(1)
    hw.interlock = False                                # door opened
    link.step(100)
    assert hw.current_ma(0) == 0.0                      # hardware: ENABLE low at once
    link.step(1000)
    assert drv.status()['state'] == 'FAULT'
    assert hw.dac == [0, 0, 0, 0] and hw.laser_mask() == 0
    hw.interlock = True
    link.step(1000)
    assert drv.status()['state'] == 'FAULT'             # stays latched until RESET
    drv.reset()
    assert drv.status()['state'] == 'ARMED'
    assert drv.status()['set_ma'] == '0.00,0.00,0.00,0.00'   # set points must be sent again


def test_usb_heartbeat_timeout():
    link, hw, drv = armed()
    drv.on(1)
    for _ in range(C.HEARTBEAT_MS + 50):
        link.step(1000)                                 # PC silent for > 3 s
    assert any('USB_TIMEOUT' in e for e in link.rx + drv.events) or drv.status()['fault'] == 'USB_TIMEOUT'
    assert hw.laser_mask() == 0


def test_fault_stops_watchdog_hardware_follows():
    link, hw, drv = armed()
    drv.on(1)
    hw.temp = False
    link.step(1000)
    hw.temp = True                                      # temperature recovers
    for _ in range(2000):
        link.step(1000)                                 # firmware holds WDI -> TPS3823 fires
    assert hw.latch is False                            # hardware ENABLE low as well
    drv.reset()                                         # RESET restarts WDI and re-arms
    assert hw.latch is True


def test_reset_refused_with_chain_open():
    link, hw, drv = board()
    hw.key = False
    with pytest.raises(DriverError):
        drv.reset()
    hw.key = True
    drv.reset()
    assert drv.status()['state'] == 'ARMED'


# ---------------- camera protection ----------------
def test_camera_protection():
    link, hw, drv = armed()
    assert hw.cam_oe is False                           # trigger output disabled by default
    with pytest.raises(DriverError):
        drv.camera_trigger(True)                        # not allowed in MODE PC
    drv.mode('TRIG')
    with pytest.raises(DriverError):
        drv.trig_width(C.CAM_TRIG_MAX_US + 1)           # pulse too long
    drv.camera_trigger(True)
    assert hw.cam_oe is True
    drv.gap(1000); drv.lead(5000)
    with pytest.raises(DriverError):
        drv.position([1, 2])                            # faster than the camera can read out
    drv.mode('PC') if False else None
    drv.disarm()
    assert hw.cam_oe is False                           # DISARM always disables the output


# ---------------- F4: hardware-timed frames ----------------
def test_frames_timing_mode_b():
    link, hw, drv = armed()
    drv.mode('TRIG'); drv.settle(2000); drv.lead(5000); drv.trig_width(10); drv.gap(30000)
    drv.camera_trigger(True)
    hw.cam_exposure_us = 8000
    drv.position([1, 2, 3, 4])
    t_stage = hw.t_us + 3000
    hw.stage_arrive(t_stage)
    drv.wait_frames(4)
    fl = hw.frame_log
    assert len(fl) == 4
    f0 = fl[0]
    assert abs((f0['t_on'] - t_stage) - 2000) < 0.01        # settle exact (< 10 ns)
    assert abs((f0['t_trig'] - f0['t_on']) - 5000) < 0.01   # lead exact
    for a, b in zip(fl, fl[1:]):
        assert abs((b['t_on'] - a['t_off']) - 30000) < 0.02  # camera read-out gap
    masks = [f['mask'] for f in fl]
    assert masks == [1, 2, 4, 8]
    ts = [e for e in drv.events if 'TS EXPOS_START' in e]
    assert len(ts) == 4


def test_exposure_timeout_fault():
    link, hw, drv = armed()
    drv.mode('TRIG'); drv.settle(100); drv.lead(100)
    hw.cam_responds = False                             # camera never exposes (mode A, PC failed)
    drv.position([1], wait=False)
    with pytest.raises(DriverError):
        drv.wait_frames(1, timeout_s=5)
    assert hw.laser_mask() == 0


# ---------------- time-stamp decoder against the cycle-accurate emulator ----------------
def test_timestamp_decoder_cycle_accurate():
    from piosim import run_ts
    random.seed(7)
    for trial in range(10):
        t, ev = random.randint(20, 80), []
        for k in range(8):
            t += random.randint(6, 500); ev.append(t)
        raw = run_ts(ev, ev[-1] + 40)
        d = K.TsDecoder()
        got = [d.feed(r)[0] for r in raw]
        err = [g - e for g, e in zip(got, ev)]
        assert max(abs(x) for x in err) <= 1            # <= 1 clock cycle = 6.7 ns (F4: <= 1 us)


def test_timestamp_wrap_marker_ignored():
    d = K.TsDecoder()
    assert d.feed(0xFFFFFFFF) is None
