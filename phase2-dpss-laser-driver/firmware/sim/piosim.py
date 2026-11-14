# Cycle-accurate runs of the firmware PIO programs (pioemu) with simple stage and camera models.
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, '../firmware')]
import fake_rp2; fake_rp2.install()
import config as C, dpss_pio as P
from pioemu import emulate, State
from collections import deque

F = C.SYS_CLK_HZ
NS = 1e9 / F          # ns per cycle

OUT_MASK = (0xF << C.PIN_LASER_ON_BASE) | (1 << C.PIN_CAM_TRIG)


def run_frames(frames, t_stage_cyc=None, cam_delay_cyc=0, cam_exp_cyc=0, max_cyc=2_000_000,
               expos_external=None):
    """frames: list of 4-word tuples. Stage edge at t_stage_cyc (None = never).
    Camera model: Status Expos goes high cam_delay_cyc after each rising edge of CAM_TRIG and
    stays high cam_exp_cyc. expos_external: optional list of (t_on, t_off) cycles instead (mode A,
    camera triggered by the PC). Returns the per-cycle trace of the relevant pins."""
    words = deque(w for f in frames for w in f)
    cam = {'last_trig': 0, 'starts': []}

    def inputs(state: State) -> int:
        t = state.clock
        v = 0
        if t_stage_cyc is not None and t >= t_stage_cyc:
            v |= 1 << C.PIN_STAGE_IN
        trig = (state.pin_values >> C.PIN_CAM_TRIG) & 1
        if trig and not cam['last_trig']:
            cam['starts'].append(t + cam_delay_cyc)
        cam['last_trig'] = trig
        win = expos_external if expos_external is not None else [(s, s + cam_exp_cyc) for s in cam['starts']]
        if any(a <= t < b for a, b in win):
            v |= 1 << C.PIN_CAM_EXPOS
        return v

    init = State(pin_directions=OUT_MASK, transmit_fifo=words)
    prog = P.frame_seq
    trace = []
    pushes = []
    n_done = [0]
    def stop(op, st):
        return st.clock >= max_cyc or n_done[0] >= len(frames)
    for before, after in emulate(prog.opcodes, stop_when=stop, initial_state=init, input_source=inputs,
                                 shift_osr_right=True, out_base=C.PIN_LASER_ON_BASE, out_count=4,
                                 side_set_base=C.PIN_CAM_TRIG, side_set_count=1,
                                 wrap_target=prog.wrap_target, wrap_top=prog.wrap):
        trace.append((after.clock, after.pin_values))
        if len(after.receive_fifo) > len(before.receive_fifo):
            pushes.append(after.clock); n_done[0] += 1
    return trace, pushes


def edges(trace, pin):
    out, last = [], None
    for t, v in trace:
        b = (v >> pin) & 1
        if last is not None and b != last:
            out.append((t, b))
        last = b
    return out


def run_ts(edge_times, max_cyc):
    """edge_ts program on one input pin (gpio 0 here); edge_times = alternating rising/falling."""
    def inputs(clock: int) -> int:
        lvl = 0
        for t in edge_times:
            if clock >= t:
                lvl ^= 1
        return lvl
    prog = P.edge_ts
    got = []
    for before, after in emulate(prog.opcodes, stop_when=lambda op, st: st.clock >= max_cyc,
                                 initial_state=State(), input_source=inputs, jmp_pin=0,
                                 wrap_target=prog.wrap_target, wrap_top=prog.wrap):
        if len(after.receive_fifo) > len(before.receive_fifo):
            got.append(after.receive_fifo[-1])
    return got
