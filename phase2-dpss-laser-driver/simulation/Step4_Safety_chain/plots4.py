# Step 4 figures (IEEE style, black and white)
import numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from analyze4 import load, T_EVT

plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Liberation Serif', 'Times New Roman', 'DejaVu Serif'],
                     'mathtext.fontset': 'stix', 'font.size': 10, 'axes.linewidth': 0.8})
ms = lambda t: t * 1e3

# ---------- Fig. 1: interlock opening, as drawn vs proposed fix ----------
cases = [('A_designed_typ', 'As drawn (C701 100 nF), typ. threshold 1.5 V', '-'),
         ('A_designed_worst', 'As drawn, worst-case threshold 0.8 V', '--'),
         ('B_fixed_interlock', 'Fix: C701 10 nF + Schmitt 74LVC2G17', ':')]
fig, ax = plt.subplots(3, 1, figsize=(7.0, 6.2), sharex=True)
for n, lab, ls in cases:
    t, v = load(n)
    m = (t > 5.8e-3) & (t < 8.0e-3)
    ax[0].plot(ms(t[m]) - 6, v['chain'][m], 'k', ls=ls, lw=1.2, label=lab)
    ax[1].plot(ms(t[m]) - 6, v['en'][m], 'k', ls=ls, lw=1.2)
    ax[2].plot(ms(t[m]) - 6, v['ilas'][m] * 1e3, 'k', ls=ls, lw=1.2)
for y, txt in ((1.5, 'typ. 1.5 V'), (0.8, 'VIL 0.8 V')):
    ax[0].axhline(y, color='0.5', lw=0.6); ax[0].text(1.62, y + 0.06, txt, fontsize=8, color='0.3')
for a in ax:
    a.axvline(1.0, color='k', lw=0.6, ls='-.')
ax[2].text(1.02, 300, 'S1 limit\n1 ms', fontsize=8)
ax[0].set_ylabel('V(CHAIN) (V)'); ax[1].set_ylabel('ENABLE (V)'); ax[2].set_ylabel('Laser current (mA)')
ax[2].set_xlabel('Time after the interlock opens (ms)')
ax[0].legend(fontsize=8, frameon=False, loc='upper right')
for a, l in zip(ax, 'abc'):
    a.set_title('(%s)' % l, fontsize=9, loc='left', pad=2)
ax[2].set_xlim(-0.2, 2.0)
fig.tight_layout(); fig.savefig('fig_s4_interlock.png', dpi=300); plt.close(fig)

# ---------- Fig. 2: complete sequence with the fix (fault, latch, re-arm) ----------
t, v = load('B_fixed_interlock')
rows = [('Interlock\n(CHAIN)', v['chain'] / 3.3), ('SAFE_OK', v['safe'] / 3.3), ('FAULT_RST', v['frst'] / 3.3),
        ('ENABLE', v['en'] / 3.3), ('Laser current\n(0-400 mA)', v['ilas'] / 0.4),
        ('Relay short\nacross laser', 1 - v['rly'] / 3.3), ('Emission LED', v['iled'] / 0.0093)]
fig, ax = plt.subplots(figsize=(7.0, 5.4))
for k, (name, y) in enumerate(rows):
    y0 = (len(rows) - 1 - k) * 1.35
    ax.plot(ms(t), y0 + np.clip(y, -0.05, 1.05), 'k', lw=1.1)
    ax.text(-0.4, y0 + 0.45, name, ha='right', va='center', fontsize=9)
for x, txt in ((0.1, 'RESET'), (4.0, 'LASER_ON1'), (6, 'interlock\nopens'), (9, 'interlock\ncloses'), (11, 'RESET\n(FAULT_RST)')):
    ax.axvline(x, color='0.6', lw=0.6, ls='--'); ax.text(x + 0.1, 9.45, txt, fontsize=8, va='bottom')
ax.annotate('junction C discharge\nat relay closure (no light)', xy=(9.15, 2.9), xytext=(9.6, 3.35), fontsize=7.5,
            arrowprops=dict(arrowstyle='->', lw=0.6))
ax.text(14.1, 3.15, 'emits after relay\nopens (3 ms)', fontsize=7.5)
ax.set_yticks([]); ax.set_xlim(0, 16); ax.set_ylim(-0.3, 10.3)
for s in ('left', 'right', 'top'): ax.spines[s].set_visible(False)
ax.set_xlabel('Time (ms)')
fig.subplots_adjust(left=0.18, right=0.98, top=0.97, bottom=0.09)
fig.savefig('fig_s4_sequence.png', dpi=300); plt.close(fig)

# ---------- Fig. 3: current turn-off for every safety input (fix applied) ----------
fig, ax = plt.subplots(figsize=(7.0, 3.0))
for n, lab, ls in (('E_fixed_watchdog', 'Watchdog RESET (TPS3823)', '-'), ('D_fixed_temp', 'TEMP_OK lost (opto, est.)', '--'),
                   ('C_fixed_key', 'Key switch / interlock (C701 10 nF)', ':')):
    t, v = load(n)
    m = (t > 5.98e-3) & (t < 6.25e-3)
    ax.plot((t[m] - 6e-3) * 1e6, v['ilas'][m] * 1e3, 'k', ls=ls, lw=1.2, label=lab)
ax.set_xlabel('Time after the safety input changes (µs)'); ax.set_ylabel('Laser current (mA)')
ax.legend(fontsize=8, frameon=False); ax.set_xlim(-20, 250)
fig.tight_layout(); fig.savefig('fig_s4_paths.png', dpi=300); plt.close(fig)
print('ok')
