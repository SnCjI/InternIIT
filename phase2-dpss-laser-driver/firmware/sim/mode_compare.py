# Step 6 - Camera trigger mode A (PC triggers the PCO.panda by software) vs mode B (the board triggers
# it through SMA input #1). The real firmware core runs against the board model; the camera is a
# rolling-shutter model with the timing of the pco.panda 4.2 manual; the PC is modelled with
# latency distributions (assumptions, to be measured on the real set-up with the board time stamps).
import os, sys, json
import numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, '../firmware'), os.path.join(HERE, '../pc')]
import sim_board as SB
from sim_board import SimHW, SimLink
from dpss_client import DPSSDriver, DriverError
from scan_example import snake_positions
P, F = SB.P, SB.F

plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Liberation Serif', 'Times New Roman', 'DejaVu Serif'],
                     'mathtext.fontset': 'stix', 'font.size': 10, 'axes.linewidth': 0.8})
OUT = os.path.join(HERE, 'results', 'step6'); os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- camera (pco.panda 4.2 bi manual)
LINE_US = 12.174          # line time (manual: 12.136 us panda 4.2, 12.174 us panda 4.2 bi UV)
N_ROWS = 2048
SPAN_US = (N_ROWS - 1) * LINE_US     # first-line start -> last-line start (24.9 ms)
T_RSYS = 2 * LINE_US      # trigger -> first line start: fixed 2 line times ...
T_JIT = LINE_US           # ... plus jitter <= 1 line time
# ---------------------------------------------------------------- scan (same as Step 5)
ROWS, COLS, PITCH = 4, 5, 0.5
MOVE_US = 300_000         # stage step time (assumed, HO-MPC-4H to be confirmed)
SETTLE, LEAD, EXPOSURE = 2000, 5000, 10_000
GAP = 20_000              # firmware rule in mode B: GAP + LEAD >= 25 ms camera minimum period
TAU_US = 1000.0           # DPSS output time constant, worst case of Step 1 (1 ms)
CURRENTS = (300, 280, 320, 250)


class CamHW(SimHW):
    """Board model + rolling-shutter camera. Status Expos signal timing selectable as in the manual:
    'overall' = any line integrating, 'first' = first line, 'common' = all lines exposed together."""

    def __init__(self, rng, expos='overall', exposure_us=EXPOSURE):
        super().__init__()
        self.rng, self.expos, self.T = rng, expos, exposure_us
        self.pending_ts = []          # stage edges reported only when they really happen
        self.ext = []                 # mode A: exposures started by the PC (dicts)

    def stage_arrive(self, t_us):
        self.stage_edges.append(t_us)
        self.pending_ts += [t_us, t_us + 1000]

    def _update(self):
        while self.pending_ts and self.pending_ts[0] <= self.t_us:
            self._ts_add('stage', self.pending_ts.pop(0))
        super()._update()

    def camera_trigger(self, t_x):
        """A trigger reaches the camera at t_x (hardware or software): returns the frame."""
        t0 = t_x + T_RSYS + self.rng.uniform(0, T_JIT)
        win = {'overall': (t0, t0 + SPAN_US + self.T),
               'first': (t0, t0 + self.T),
               'common': (t0 + SPAN_US, t0 + self.T) if self.T > SPAN_US else None}[self.expos]
        return dict(t_x=t_x, t0=t0, win=win, used=False)

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
            r['phase'] = 'run'; r['cam'] = None
        if r['phase'] == 'run':
            if t >= r['t_on'] and not r.get('on'):
                r['on'] = True; self._mask_seq = r['mask']; self._log_mask_at(r['t_on'])
            if t >= r['t_trig_off'] and not r.get('trig_done'):
                r['trig_done'] = True
                if self.cam_oe:                                   # mode B: hardware trigger
                    self.trig_log.append((r['t_trig'], r['t_trig_off']))
                    r['cam'] = self.camera_trigger(r['t_trig'])
            if r.get('trig_done') and r['cam'] is None and not self.cam_oe:
                # mode A: PIO waits for Status Expos; it catches the first PC exposure still running
                for c in self.ext:
                    if not c['used'] and c['win'] and c['win'][1] > r['t_trig_off']:
                        c['used'] = True; r['cam'] = c; break
            c = r['cam']
            if c and c['win'] and t >= c['win'][1] + 2 / F * 1e6:
                t_off = max(c['win'][1], r['t_trig_off']) + 2 / F * 1e6
                self._mask_seq = 0; self._log_mask_at(t_off)
                self._ts_add('expos', c['win'][0]); self._ts_add('expos', c['win'][1])
                r['t_off'] = t_off; r['exp'] = c['win']
                self.t_free = t_off
                self.frame_log.append(dict(r))
                self.running = None; self.done += 1


# ---------------------------------------------------------------- PC latency models (assumptions)
def pc_model(name, rng):
    """Delay from the board event to the camera trigger, on top of the planned wait (us).
    rx  : firmware loop -> USB CDC full speed (1 ms frames) -> pyserial readline
    wait: the PC waits SETTLE+LEAD (or GAP+LEAD); timer error of that wait
    sdk : PCO SDK software trigger over USB 3 -> camera FPGA"""
    u, e = rng.uniform, rng.exponential
    tail = lambda p, lo, hi: u(lo, hi) if rng.random() < p else 0.0
    if name == 'A1':   # tuned: busy-wait timing loop, dedicated thread, no other load
        return u(0, 1000) + e(100), u(0, 50), 300 + e(200)
    if name == 'A2':   # typical Python 3.11+ (high-resolution time.sleep ~1 ms), occasional OS stalls
        return u(0, 1000) + e(300) + tail(0.01, 2000, 10000), u(500, 1500), 500 + e(500) + tail(0.01, 5000, 20000)
    if name == 'A3':   # default Windows timer (15.6 ms tick)
        return u(0, 1000) + e(300) + tail(0.01, 2000, 10000), u(0, 15625), 500 + e(500) + tail(0.01, 5000, 20000)
    raise ValueError(name)


def run_scan(mode, seed, expos='overall', exposure_us=EXPOSURE, rows=ROWS, cols=COLS):
    rng = np.random.default_rng(seed)
    hw = CamHW(rng, expos, exposure_us); link = SimLink(hw); drv = DPSSDriver(link)
    link.step(1000); drv.reset()
    for ch, ma in zip((1, 2, 3, 4), CURRENTS):
        drv.set_current(ch, ma)
    drv.arm()
    for _ in range(150):
        link.step(1000)
    drv.mode('TRIG'); drv.settle(SETTLE); drv.lead(LEAD); drv.trig_width(10); drv.gap(GAP)
    if mode == 'B':
        drv.camera_trigger(True)
    plan = list(snake_positions(rows, cols, PITCH, PITCH))
    moves, pc_log, faults = [], [], []
    t_scan0 = hw.t_us; last_ping = hw.t_us
    for (r, c, x, y) in plan:
        drv.position([1, 2, 3, 4], wait=True)
        t_move = hw.t_us; hw.stage_arrive(t_move + MOVE_US); moves.append((t_move, t_move + MOVE_US))
        done = 0
        while done < 4:
            new = drv.poll(1000); now = hw.t_us
            for ev in new:
                if 'FAULT' in ev:
                    faults.append((now, ev)); done = 99; break
                planned = None
                if ev.startswith('EVT TS STAGE_IN'):
                    planned = SETTLE + LEAD
                if 'FRAME_DONE' in ev:
                    done += 1
                    if done < 4:
                        planned = GAP + LEAD
                if mode != 'B' and planned is not None:
                    d_rx, d_wait, d_sdk = pc_model(mode, rng)
                    t_x = now + d_rx + planned + d_wait + d_sdk
                    hw.ext.append(hw.camera_trigger(t_x))
                    pc_log.append(dict(t_event=now, d_rx=d_rx, d_wait=d_wait, d_sdk=d_sdk, t_x=t_x))
            if hw.t_us - last_ping > 1_000_000:
                drv.ping(); last_ping = hw.t_us
            if hw.t_us - t_move > 5_000_000:
                faults.append((hw.t_us, 'stuck')); done = 99
        if done == 99:
            break
    t_scan = (hw.t_us - t_scan0) / 1e6
    return dict(hw=hw, frames=hw.frame_log, moves=moves, pc=pc_log, faults=faults, t_scan=t_scan,
                events=drv.events, n_pos=len(plan))


# ---------------------------------------------------------------- DPSS output and row doses
def dose(t_on, t_off, a, b, tau=TAU_US):
    """Energy of a first-order DPSS (rise and fall tau) between a and b (arrays), unit power."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    def F_on(t):    # integral of 1 - exp(-(t - t_on)/tau) from t_on
        x = np.clip(t, t_on, t_off) - t_on
        return x - tau * (1 - np.exp(-x / tau))
    p_off = 1 - np.exp(-(t_off - t_on) / tau)
    def F_off(t):   # tail after t_off
        x = np.maximum(t, t_off) - t_off
        return p_off * tau * (1 - np.exp(-x / tau))
    return (F_on(b) - F_on(a)) + (F_off(b) - F_off(a))


def frame_rows(fr, prev, T):
    t0 = fr['cam']['t0']
    a = t0 + np.arange(N_ROWS) * LINE_US; b = a + T
    own = dose(fr['t_on'], fr['t_off'], a, b) / T
    xt = dose(prev['t_on'], prev['t_off'], a, b) / T if prev is not None else np.zeros(N_ROWS)
    return own, xt


def metrics(res, T=EXPOSURE):
    fl = res['frames']; out = []
    for i, fr in enumerate(fl):
        own, xt = frame_rows(fr, fl[i - 1] if i else None, T)
        t_ready = fr['t_on'] + LEAD
        out.append(dict(i=i, ch=int(np.log2(fr['mask'])) + 1, first=(i % 4 == 0),
                        start_after_ready=fr['cam']['t0'] - t_ready,
                        on_time=fr['t_off'] - fr['t_on'], useful=SPAN_US + T,
                        row_min=own.min(), row_max=own.max(), xtalk_max=xt.max(),
                        t_stage=res['moves'][i // 4][1], t0=fr['cam']['t0']))
    return out


if __name__ == '__main__':
    import time
    SEEDS = [1, 2, 3, 4, 5]
    allres = {}
    for mode in ('B', 'A1', 'A2', 'A3'):
        t = time.time(); runs = [run_scan(mode, s) for s in SEEDS]
        allres[mode] = runs
        print(mode, 'scan %.2f s' % np.mean([r['t_scan'] for r in runs]), 'frames', sum(len(r['frames']) for r in runs),
              'faults', sum(len(r['faults']) for r in runs), '(%.0f s wall)' % (time.time() - t))
    import pickle
    pickle.dump({m: [dict(frames=[{k: v for k, v in f.items()} for f in r['frames']], moves=r['moves'], pc=r['pc'],
                          faults=r['faults'], t_scan=r['t_scan'], n_pos=r['n_pos'], trig=r['hw'].trig_log)
                     for r in runs] for m, runs in allres.items()}, open(os.path.join(OUT, 'runs.pkl'), 'wb'))
