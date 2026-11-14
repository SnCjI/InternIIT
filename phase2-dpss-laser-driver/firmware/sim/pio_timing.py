# Cycle-accurate verification of the PIO timing (requirement F4: trigger timing resolution <= 1 us).
# Runs the real PIO opcodes of firmware/dpss_pio.py in pioemu at 150 MHz.
import csv, random, os
import numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from piosim import *
import dpss_core as K

plt.rcParams.update({'font.family': 'Liberation Serif', 'mathtext.fontset': 'stix', 'font.size': 11})
OUT = os.path.join(HERE, 'results'); os.makedirs(OUT, exist_ok=True)
us = lambda cyc: cyc / F * 1e6


def regs(settle, lead, trig, wait=True):
    return (P.reg_for(settle, F, P.OVH_SETTLE if wait else P.OVH_GAP), P.reg_for(lead, F, P.OVH_LEAD),
            P.reg_for(trig, F, P.OVH_TRIG))


# ------------------------------------------------------------------ 1) random sweep
random.seed(2026)
rows = []
for k in range(25):
    settle = round(random.uniform(1, 60), 3); lead = round(random.uniform(1, 60), 3)
    trig = round(random.uniform(0.1, 10), 3); gap = round(random.uniform(1, 60), 3)
    exp_c = int(trig * F / 1e6) + random.randint(150, 3000); t_st = random.randint(40, 400)
    s1, l1, w1 = regs(settle, lead, trig, True)
    s2, l2, w2 = regs(gap, lead, trig, False)
    fr = [P.frame_words(True, s1, l1, w1, 1), P.frame_words(False, s2, l2, w2, 2)]
    tr, pushes = run_frames(fr, t_stage_cyc=t_st, cam_delay_cyc=3, cam_exp_cyc=exp_c)
    a, b = edges(tr, C.PIN_LASER_ON_BASE), edges(tr, C.PIN_LASER_ON_BASE + 1)
    tg = edges(tr, C.PIN_CAM_TRIG)
    # STAGE_IN is sampled by the emulator one cycle after it changes (pin update order); the
    # silicon adds a 2-cycle input synchroniser instead - both are constant and reported below.
    m_settle = us(a[0][0] - t_st); m_lead = us(tg[0][0] - a[0][0]); m_trig = us(tg[1][0] - tg[0][0])
    m_gap = us(b[0][0] - a[1][0])
    m_off = us(a[1][0] - (tg[0][0] + 3 + exp_c))
    rows.append(dict(settle_req=settle, settle_meas=m_settle, lead_req=lead, lead_meas=m_lead,
                     trig_req=trig, trig_meas=m_trig, gap_req=gap, gap_meas=m_gap, expos_end_to_off_us=m_off))
with open(os.path.join(OUT, 'pio_timing_sweep.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
errs = {k: [abs(r[k + '_meas'] - r[k + '_req']) * 1000 for r in rows] for k in ('settle', 'lead', 'trig', 'gap')}
off_ns = [r['expos_end_to_off_us'] * 1000 for r in rows]

# ------------------------------------------------------------------ 2) time stamps
random.seed(11)
ts_err = []
for trial in range(30):
    t, ev = random.randint(20, 80), []
    for k in range(8):
        t += random.randint(6, 2000); ev.append(t)
    raw = run_ts(ev, ev[-1] + 40)
    d = K.TsDecoder()
    ts_err += [(d.feed(r)[0] - e) for r, e in zip(raw, ev)]
ts_err_ns = [e / F * 1e9 for e in ts_err]

lines = ['Cycle-accurate PIO verification (pioemu, f_sys = %.0f MHz, 1 cycle = %.2f ns)' % (F / 1e6, 1e9 / F), '']
for k, v in errs.items():
    lines.append('%-7s interval error: max %.2f ns, mean %.2f ns  (%d random cases)' % (k, max(v), sum(v) / len(v), len(v)))
lines.append('Status Expos end -> LASER OFF: %.2f ns (+13.3 ns input synchroniser in silicon)' % max(off_ns))
lines.append('Time stamps: max error %.2f ns over %d edges (counter resolution %.1f ns)' %
             (max(abs(x) for x in ts_err_ns), len(ts_err_ns), 2e9 / F))
lines.append('Requirement F4: resolution <= 1 us  ->  met with margin x%.0f' % (1000 / max(max(max(v) for v in errs.values()), 1e9 / F)))
open(os.path.join(OUT, 'pio_timing_summary.txt'), 'w').write('\n'.join(lines) + '\n')
print('\n'.join(lines))

# ------------------------------------------------------------------ 3) waveform figure (mode B and mode A)
def waveforms(mode_b):
    S, L, Tw, G = 6.0, 8.0, 1.0, 5.0
    s1, l1, w1 = regs(S, L, Tw, True); s2, l2, w2 = regs(G, L, Tw, False)
    fr = [P.frame_words(True, s1, l1, w1, 1), P.frame_words(False, s2, l2, w2, 2)]
    t_st = int(3e-6 * F)
    if mode_b:
        tr, _ = run_frames(fr, t_stage_cyc=t_st, cam_delay_cyc=int(0.5e-6 * F), cam_exp_cyc=int(7e-6 * F))
    else:  # camera triggered by the PC: exposures at times unrelated to the board's trigger
        ext = [(int(18.4e-6 * F), int(26.0e-6 * F)), (int(44.0e-6 * F), int(50.5e-6 * F))]
        tr, _ = run_frames(fr, t_stage_cyc=t_st, expos_external=ext)
    t = np.array([c for c, _ in tr]) / F * 1e6
    v = np.array([pv for _, pv in tr])
    bit = lambda p: (v >> p) & 1
    stage = (np.array([c for c, _ in tr]) >= t_st).astype(int)
    if mode_b:
        expos = np.zeros_like(stage)
        tg = edges(tr, C.PIN_CAM_TRIG)
        for (tt, lvl) in tg:
            if lvl:
                a = tt + int(0.5e-6 * F); expos[(np.array([c for c, _ in tr]) >= a) & (np.array([c for c, _ in tr]) < a + int(7e-6 * F))] = 1
    else:
        cc = np.array([c for c, _ in tr]); expos = np.zeros_like(stage)
        for a, b in ext: expos[(cc >= a) & (cc < b)] = 1
    sig = [('STAGE_IN', stage), ('LASER_ON1', bit(C.PIN_LASER_ON_BASE)), ('LASER_ON2', bit(C.PIN_LASER_ON_BASE + 1)),
           ('CAM_TRIG', bit(C.PIN_CAM_TRIG) if mode_b else np.zeros_like(stage)), ('Status Expos', expos)]
    return t, sig


fig, axs = plt.subplots(2, 1, figsize=(7.2, 6.4), sharex=True)
for ax, mb, title in ((axs[0], True, '(a) Mode B: the board triggers the camera'),
                      (axs[1], False, '(b) Mode A: the PC triggers the camera, the board follows Status Expos')):
    t, sig = waveforms(mb)
    n = len(sig)
    for i, (name, y) in enumerate(sig):
        y0 = (n - 1 - i) * 1.4
        ax.step(t, y0 + 0.9 * y, where='post', color='k', lw=1.2)
        ax.text(-0.6, y0 + 0.45, name, ha='right', va='center', fontsize=10)
    ax.set_yticks([]); ax.set_title(title, fontsize=11, loc='left')
    for sp in ('left', 'right', 'top'): ax.spines[sp].set_visible(False)
    ax.set_xlim(0, t[-1] + 1)
axs[1].set_xlabel('Time (µs)  -  PIO emulated cycle by cycle at 150 MHz (intervals shortened for display)')
an = axs[0]
an.annotate('', xy=(3, 5.38), xytext=(9, 5.38), arrowprops=dict(arrowstyle='<->', lw=0.8)); an.text(6, 5.52, 'settle', ha='center', fontsize=9)
an.annotate('', xy=(9, 3.96), xytext=(17, 3.96), arrowprops=dict(arrowstyle='<->', lw=0.8)); an.text(13, 4.1, 'lead', ha='center', fontsize=9)
an.text(24.2, 3.3, 'OFF 13 ns after\nexposure end', ha='right', fontsize=8.5)
fig.subplots_adjust(left=0.17, right=0.98, top=0.95, bottom=0.09, hspace=0.25)
fig.savefig(os.path.join(OUT, 'fig_fw_pio_waveforms.png'), dpi=300)
print('figure saved')
