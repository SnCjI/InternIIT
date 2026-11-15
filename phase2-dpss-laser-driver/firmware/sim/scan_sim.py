# System-level simulation: the PC client (pc/dpss_client.py) runs a snake-by-row scan against the
# simulated board (firmware core + board model). Also justifies LEAD with the DPSS model of Step 1.
import os, sys
import numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, '../firmware'), os.path.join(HERE, '../pc')]
from sim_board import SimLink
from dpss_client import DPSSDriver
from scan_example import snake_positions

plt.rcParams.update({'font.family': 'Liberation Serif', 'mathtext.fontset': 'stix', 'font.size': 11})
OUT = os.path.join(HERE, 'results'); os.makedirs(OUT, exist_ok=True)

# ------------------------------------------------------------------ 1) LEAD vs DPSS response (Step 1 model)
T_EXP = 10e-3
taus = [10e-6, 100e-6, 1e-3]
leads = np.logspace(-5, -1.7, 300)
def deficit(L, tau, T=T_EXP):          # 1 - (mean optical power during the exposure) / P_steady
    return tau / T * np.exp(-L / tau) * (1 - np.exp(-T / tau))
fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.9))
t = np.linspace(0, 20e-3, 2000)
L0 = 5e-3
for tau, ls in zip(taus, ['-', '--', ':']):
    axs[0].plot(t * 1e3, 1 - np.exp(-t / tau), 'k', ls=ls, lw=1.2, label='τ = %g µs' % (tau * 1e6) if tau < 1e-3 else 'τ = 1 ms')
    axs[1].loglog(leads * 1e3, np.maximum(deficit(leads, tau), 1e-9) * 100, 'k', ls=ls, lw=1.2,
                  label='τ = %g µs' % (tau * 1e6) if tau < 1e-3 else 'τ = 1 ms')
axs[0].axvspan(L0 * 1e3, (L0 + T_EXP) * 1e3, color='0.88', lw=0)
axs[0].text((L0 + T_EXP / 2) * 1e3, 0.45, 'exposure\n(10 ms)', ha='center', fontsize=9)
axs[0].annotate('', xy=(0, 0.2), xytext=(L0 * 1e3, 0.2), arrowprops=dict(arrowstyle='<->', lw=0.8))
axs[0].text(L0 * 1e3 / 2, 0.24, 'LEAD', ha='center', fontsize=9)
axs[0].set_xlabel('Time after LASER_ON (ms)'); axs[0].set_ylabel('P / P$_{ss}$'); axs[0].set_xlim(0, 20)
axs[0].set_ylim(0, 1.08); axs[0].legend(fontsize=8.5, frameon=False, loc='lower right'); axs[0].set_title('(a)', fontsize=10, loc='left')
axs[1].axhline(0.1, color='k', lw=0.6); axs[1].axvline(5, color='k', lw=0.6, ls='-.')
axs[1].text(4.6, 3, 'default\nLEAD = 5 ms', fontsize=8.5, ha='right')
axs[1].set_xlabel('LEAD (ms)'); axs[1].set_ylabel('Energy deficit in exposure (%)')
axs[1].set_ylim(1e-4, 20); axs[1].set_title('(b)', fontsize=10, loc='left')
fig.tight_layout(); fig.savefig(os.path.join(OUT, 'fig_fw_lead_dpss.png'), dpi=300)
lead_lines = ['LEAD justification (DPSS first-order model of Step 1, exposure 10 ms):']
for tau in taus:
    d5 = deficit(5e-3, tau) * 100
    need = tau * np.log(tau / T_EXP * (1 - np.exp(-T_EXP / tau)) / 1e-3) * 1e3 if deficit(0, tau) > 1e-3 else 0.0
    lead_lines.append('  tau = %7.0f us : energy deficit at LEAD 5 ms = %s,  LEAD needed for < 0.1 %% = %.2f ms' % (
        tau * 1e6, ('%.3f %%' % d5) if d5 > 1e-6 else '< 1e-6 %', need))

# ------------------------------------------------------------------ 2) snake scan, mode B
ROWS, COLS, PITCH = 4, 5, 0.5          # positions, mm
MOVE_US = 300_000                       # assumed stage step time (HO-MPC-4H speed to be confirmed)
SETTLE, LEAD, EXPOSURE, GAP = 2000, 5000, 10_000, 30_000
link = SimLink(); hw = link.hw
drv = DPSSDriver(link)
link.step(1000)
drv.reset()
for ch, ma in zip((1, 2, 3, 4), (300, 280, 320, 250)):
    drv.set_current(ch, ma)
drv.arm()
for _ in range(150):
    link.step(1000)
drv.mode('TRIG'); drv.settle(SETTLE); drv.lead(LEAD); drv.trig_width(10); drv.gap(GAP)
drv.camera_trigger(True)
hw.cam_exposure_us = EXPOSURE
plan = list(snake_positions(ROWS, COLS, PITCH, PITCH))
moves = []
t_scan0 = hw.t_us
for (r, c, x, y) in plan:
    drv.position([1, 2, 3, 4], wait=True)          # queued before the move
    t_move = hw.t_us
    hw.stage_arrive(t_move + MOVE_US)               # stage raises its BNC trigger on arrival
    moves.append((t_move, t_move + MOVE_US, r, c))
    drv.wait_frames(4)
t_scan = (hw.t_us - t_scan0) / 1e6
drv.disarm()
fl = hw.frame_log
assert len(fl) == 4 * len(plan)
err_settle, err_lead, err_gap = [], [], []
for i, f in enumerate(fl):
    err_lead.append(abs((f['t_trig'] - f['t_on']) - LEAD))
    if i % 4 == 0:
        err_settle.append(abs((f['t_on'] - moves[i // 4][1]) - SETTLE))
    else:
        err_gap.append(abs((f['t_on'] - fl[i - 1]['t_off']) - GAP))
dark = [f for f in fl if not (f['t_on'] <= f['exp'][0] and f['t_off'] >= f['exp'][1])]
cur = [hw.dac_log[-1]]
summary = lead_lines + ['',
    'Snake-by-row scan (mode B), %d x %d positions, 4 lasers, %d frames' % (ROWS, COLS, len(fl)),
    '  scan time %.2f s (stage step %.0f ms assumed), per position %.1f ms of laser/camera time' % (
        t_scan, MOVE_US / 1e3, (t_scan * 1e6 - len(plan) * MOVE_US) / len(plan) / 1e3),
    '  settle error max %.1f ns, lead error max %.1f ns, gap error max %.1f ns' % (
        max(err_settle) * 1e3, max(err_lead) * 1e3, max(err_gap) * 1e3),
    '  exposures not fully illuminated: %d of %d' % (len(dark), len(fl)),
    '  laser order per position: %s' % [f['mask'] for f in fl[:4]],
    '  PC events received: %d (FRAME_DONE %d, time stamps %d)' % (
        len(drv.events), sum('FRAME_DONE' in e for e in drv.events), sum(' TS ' in e for e in drv.events)),
    '  snake order: ' + ' '.join('(%d,%d)' % (r, c) for r, c, _, _ in plan)]
open(os.path.join(OUT, 'scan_summary.txt'), 'w').write('\n'.join(summary) + '\n')
print('\n'.join(summary))

# ------------------------------------------------------------------ figure: path + timeline
fig = plt.figure(figsize=(7.2, 5.6))
ax0 = fig.add_axes([0.07, 0.60, 0.30, 0.36]); ax1 = fig.add_axes([0.20, 0.08, 0.77, 0.40])
xs = [x for _, _, x, _ in plan]; ys = [y for _, _, _, y in plan]
ax0.plot(xs, ys, 'k-', lw=0.9)
for i, (x, y) in enumerate(zip(xs, ys)):
    ax0.plot(x, y, 'o', ms=12, mfc='white', mec='k'); ax0.text(x, y, str(i + 1), ha='center', va='center', fontsize=7.5)
ax0.set_xlabel('x (mm)'); ax0.set_ylabel('y (mm)'); ax0.invert_yaxis(); ax0.set_aspect('equal')
ax0.set_title('(a) Snake-by-row order', fontsize=10, loc='left')
ax1.set_title('(b) Timeline of the first two positions (simulated board, PC client in the loop)', fontsize=10, loc='left')
fig.text(0.47, 0.83, 'Simulation settings', fontsize=10, weight='bold')
fig.text(0.47, 0.62, '\n'.join([
    '%d x %d positions, pitch %.1f mm, 4 lasers' % (ROWS, COLS, PITCH),
    'stage step %.0f ms (assumed, to be confirmed)' % (MOVE_US / 1e3),
    'SETTLE %.0f ms, LEAD %.0f ms, GAP %.0f ms' % (SETTLE / 1e3, LEAD / 1e3, GAP / 1e3),
    'exposure %.0f ms, mode B (board triggers camera)' % (EXPOSURE / 1e3),
    'total scan %.2f s, %d images' % (t_scan, len(fl)),
    'interval error (cycle-accurate PIO check): <= 3.3 ns']), fontsize=9.5, linespacing=1.5)
t0 = moves[0][0]; tend = fl[7]['t_off'] + 20_000
ms = lambda u: (u - t0) / 1e3
rows = ['Stage moving', 'STAGE_IN', 'LASER_ON1', 'LASER_ON2', 'LASER_ON3', 'LASER_ON4', 'Status Expos']
n = len(rows)
def trace(y0, intervals):
    tt, vv = [0], [0]
    for a, b in intervals:
        tt += [ms(a), ms(a), ms(b), ms(b)]; vv += [0, 1, 1, 0]
    tt.append(ms(tend)); vv.append(0)
    ax1.plot(tt, y0 + 0.8 * np.array(vv), 'k', lw=1.1)
for i, name in enumerate(rows):
    y0 = (n - 1 - i) * 1.25
    ax1.text(-15, y0 + 0.4, name, ha='right', va='center', fontsize=9.5)
    if name == 'Stage moving':
        trace(y0, [(a, b) for a, b, _, _ in moves[:2]])
    elif name == 'STAGE_IN':
        trace(y0, [(b, b + 1000) for a, b, _, _ in moves[:2]])
    elif name.startswith('LASER_ON'):
        k = int(name[-1]) - 1
        trace(y0, [(f['t_on'], f['t_off']) for f in fl[:8] if f['mask'] == 1 << k])
    else:
        trace(y0, [f['exp'] for f in fl[:8]])
ax1.set_xlim(0, ms(tend)); ax1.set_yticks([]); ax1.set_xlabel('Time (ms)')
for sp in ('left', 'right', 'top'): ax1.spines[sp].set_visible(False)
fig.savefig(os.path.join(OUT, 'fig_fw_scan_timeline.png'), dpi=300)
print('figures saved')
