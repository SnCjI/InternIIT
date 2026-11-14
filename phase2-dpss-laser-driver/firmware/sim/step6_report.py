# Step 6 report: runs the mode comparison and the Status Expos check, writes CSV, summary and figures.
import os, csv
import numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
import mode_compare as M

OUT = M.OUT
SEEDS = [1, 2, 3, 4, 5]
NAMES = {'B': 'Mode B: board triggers camera (SMA in #1)',
         'A1': 'Mode A1: PC trigger, tuned timing loop',
         'A2': 'Mode A2: PC trigger, Python 3.11+ sleep',
         'A3': 'Mode A3: PC trigger, default 15.6 ms timer'}

runs = {m: [M.run_scan(m, s) for s in SEEDS] for m in NAMES}
rows = []
stat = {}
for m, rr in runs.items():
    met = [x for r in rr for x in M.metrics(r)]
    extra = np.array([x['on_time'] - x['useful'] for x in met]) / 1e3          # ms of light not used
    start = np.array([x['start_after_ready'] for x in met]) / 1e3             # ms after laser stable
    first = np.array([x['t0'] - x['t_stage'] - M.SETTLE - M.LEAD for x in met if x['first']])
    rowmin = min(x['row_min'] for x in met); xt = max(x['xtalk_max'] for x in met)
    npos = sum(r['n_pos'] for r in rr)
    per_pos = np.mean([(r['t_scan'] * 1e6 - r['n_pos'] * M.MOVE_US) / r['n_pos'] / 1e3 for r in rr])
    on_frac = np.mean([x['on_time'] for x in met]) / np.mean([x['useful'] for x in met])
    stat[m] = dict(extra=extra, start=start, first=first)
    rows.append(dict(scenario=m, description=NAMES[m], images=len(met), faults=sum(len(r['faults']) for r in rr),
                     scan_s=np.mean([r['t_scan'] for r in rr]), per_position_ms=per_pos,
                     exp_start_after_laser_stable_ms_mean=start.mean(), p99=np.percentile(start, 99), max=start.max(),
                     extra_laser_on_ms_mean=extra.mean(), extra_laser_on_ms_max=extra.max(),
                     laser_on_vs_needed=on_frac,
                     exposure_vs_stage_jitter_us=first.max() - first.min(),
                     row_uniformity_min=rowmin, crosstalk_max=xt))
with open(os.path.join(OUT, 'step6_results.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader()
    for r in rows:
        w.writerow({k: ('%.6g' % v if isinstance(v, (float, np.floating)) else v) for k, v in r.items()})

# ---- Status Expos signal timing (mode B, one position, 4 lasers)
exp_cases = [('overall', 10_000, "'overall time of All lines' (any line integrating)"),
             ('first', 10_000, "'First Line'"),
             ('common', 40_000, "'common time of All lines', exposure 40 ms"),
             ('common', 10_000, "'common time of All lines', exposure 10 ms")]
exp_rows = []
prof = {}
for ex, T, lab in exp_cases:
    r = M.run_scan('B', 7, expos=ex, exposure_us=T, rows=1, cols=1)
    if r['frames']:
        met = M.metrics(r, T)
        fr = r['frames'][0]; own, _ = M.frame_rows(fr, None, T); prof[(ex, T)] = own
        res = 'rows lit %.1f-%.1f %%' % (min(x['row_min'] for x in met) * 100, max(x['row_max'] for x in met) * 100)
        dark = int(np.sum(own < 0.5))
    else:
        res = 'no Status Expos pulse -> %s' % (r['faults'][0][1] if r['faults'] else 'stuck'); dark = M.N_ROWS
    exp_rows.append((lab, T, res, dark))

L = ['Step 6 - Camera trigger mode A vs mode B (firmware core + board model + rolling-shutter camera)', '',
     'Camera model (pco.panda 4.2 bi manual): rolling shutter, line time %.3f us, 2048 lines -> %.1f ms from first' % (M.LINE_US, M.SPAN_US / 1e3),
     'to last line start; trigger -> exposure 2 line times + jitter <= 1 line time; Status Expos = overall time of All lines.',
     'Scan: %d x %d positions x 4 lasers, %d seeds, stage step %.0f ms (assumed), SETTLE %.0f ms, LEAD %.0f ms,' % (
         M.ROWS, M.COLS, len(SEEDS), M.MOVE_US / 1e3, M.SETTLE / 1e3, M.LEAD / 1e3),
     'exposure %.0f ms, GAP %.0f ms, DPSS tau %.0f us (Step 1 worst case).' % (M.EXPOSURE / 1e3, M.GAP / 1e3, M.TAU_US),
     'PC latencies of A1-A3 are ASSUMPTIONS (to be measured with the board time stamps on the real PC).', '']
fmt = '%-4s %6s %6s %8s %9s %9s %9s %9s %9s %10s %9s'
L.append(fmt % ('', 'images', 'faults', 'scan s', 'pos ms', 'start ms', 'p99 ms', 'max ms', 'extra ms', 'jitter us', 'rows min'))
for r in rows:
    L.append(fmt % (r['scenario'], r['images'], r['faults'], '%.2f' % r['scan_s'], '%.1f' % r['per_position_ms'],
                    '%.3f' % r['exp_start_after_laser_stable_ms_mean'], '%.3f' % r['p99'], '%.3f' % r['max'],
                    '%.2f' % r['extra_laser_on_ms_mean'], '%.0f' % r['exposure_vs_stage_jitter_us'],
                    '%.4f' % r['row_uniformity_min']))
L += ['  start = exposure start (first line) after the laser is stable (LASER_ON + LEAD)',
      '  extra = laser light that no camera line uses (LEAD + waiting for the trigger), per image',
      '  jitter = spread of the exposure start relative to the stage in-position edge', '',
      'Status Expos signal timing (mode B, tau 1 ms):']
for lab, T, res, dark in exp_rows:
    L.append('  %-58s %s, rows below 50 %%: %d of 2048' % (lab, res, dark))
open(os.path.join(OUT, 'step6_summary.txt'), 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))

# ================================================================ figures (IEEE, black and white)
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Liberation Serif', 'Times New Roman', 'DejaVu Serif'],
                     'mathtext.fontset': 'stix', 'font.size': 10, 'axes.linewidth': 0.8})

# ---- Fig. 1: one position, mode B vs mode A2
fig, axs = plt.subplots(2, 1, figsize=(7.0, 6.0), sharex=True)
for ax, m, title in ((axs[0], 'B', '(a) Mode B: the board triggers the camera'),
                     (axs[1], 'A2', '(b) Mode A (A2): the PC triggers the camera by software')):
    r = runs[m][0]; fl = r['frames'][4:8]; mv = r['moves'][1]
    t0 = mv[1] - 3000; t1 = fl[-1]['t_off'] + 8000
    ms = lambda u: (u - mv[1]) / 1e3
    sig = [('STAGE_IN', [(mv[1], mv[1] + 1000)])]
    for k in range(4):
        sig.append(('LASER_ON%d' % (k + 1), [(f['t_on'], f['t_off']) for f in fl if f['mask'] == 1 << k]))
    if m == 'B':
        sig.append(('CAM_TRIG (board)', [(f['t_trig'], f['t_trig'] + 300) for f in fl]))
    else:
        sig.append(('PC soft trigger', [(f['cam']['t_x'], f['cam']['t_x'] + 300) for f in fl]))
    sig.append(('Status Expos', [f['exp'] for f in fl]))
    n = len(sig)
    for i, (name, iv) in enumerate(sig):
        y0 = (n - 1 - i) * 1.3; tt, vv = [ms(t0)], [0]
        for a, b in iv:
            tt += [ms(a), ms(a), ms(b), ms(b)]; vv += [0, 1, 1, 0]
        tt.append(ms(t1)); vv.append(0)
        ax.plot(tt, y0 + 0.85 * np.array(vv), 'k', lw=1.0)
        ax.text(ms(t0) - 3, y0 + 0.42, name, ha='right', va='center', fontsize=9)
    f = fl[0]
    ax.text(ms(f['t_off']) + 2, 5 * 1.3 + 0.5, 'laser on -> exposure start: %.1f ms (LEAD 5 ms%s)' % (
        (f['cam']['t0'] - f['t_on']) / 1e3, '' if m == 'B' else ' + PC latency'), fontsize=8, va='center')
    ax.set_yticks([]); ax.set_title(title, fontsize=10, loc='left')
    for sp in ('left', 'right', 'top'): ax.spines[sp].set_visible(False)
    ax.set_xlim(ms(t0), ms(t1)); ax.set_ylim(-0.3, 9.0)
axs[1].set_xlabel('Time after the stage in-position edge (ms)')
fig.subplots_adjust(left=0.2, right=0.98, top=0.95, bottom=0.08, hspace=0.25)
fig.savefig(os.path.join(OUT, 'fig_s6_timeline.png'), dpi=300); plt.close(fig)

# ---- Fig. 2: extra laser-on time per image and exposure start spread
fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.9))
styles = {'B': '-', 'A1': '--', 'A2': '-.', 'A3': ':'}
for m in NAMES:
    s = np.sort(stat[m]['start']); y = np.arange(1, len(s) + 1) / len(s)
    axs[0].semilogx(np.maximum(s, 1e-3), y, 'k', ls=styles[m], lw=1.2, label=m)
    e = np.sort(stat[m]['extra']); axs[1].plot(e, np.arange(1, len(e) + 1) / len(e), 'k', ls=styles[m], lw=1.2, label=m)
axs[0].set_xlabel('Exposure start after laser stable (ms)'); axs[0].set_ylabel('Fraction of images')
axs[1].set_xlabel('Laser light not used by the camera (ms/image)')
axs[0].legend(fontsize=8, frameon=False, loc='lower right'); axs[0].set_title('(a)', fontsize=10, loc='left')
axs[1].set_title('(b)', fontsize=10, loc='left'); axs[1].set_xlim(4.5, None)
fig.tight_layout(); fig.savefig(os.path.join(OUT, 'fig_s6_latency.png'), dpi=300); plt.close(fig)

# ---- Fig. 3: row illumination for the Status Expos settings
fig, ax = plt.subplots(figsize=(7.0, 2.8))
for (ex, T), ls, lab in ((('overall', 10_000), '-', "Overall time of All lines (10 ms)  - recommended"),
                         (('first', 10_000), '--', "First Line (10 ms)"),
                         (('common', 40_000), ':', "Common time of All lines (40 ms)")):
    ax.plot(np.arange(M.N_ROWS), prof[(ex, T)] * 100, 'k', ls=ls, lw=1.2, label=lab)
ax.text(1080, 14, "Common time of All lines with 10 ms: no window\n(exposure < 24.9 ms read-out) -> EXPOSURE_TIMEOUT fault",
        fontsize=8)
ax.set_xlabel('Sensor row'); ax.set_ylabel('Light received (%)'); ax.set_xlim(0, 2047); ax.set_ylim(-3, 108)
ax.legend(fontsize=8, frameon=False, loc='lower left')
fig.tight_layout(); fig.savefig(os.path.join(OUT, 'fig_s6_expos_setting.png'), dpi=300); plt.close(fig)
print('figures saved')
