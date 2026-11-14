# Step 4 analysis: shutdown times, latch behaviour and emission indicator for each scenario
import numpy as np, csv
NAMES = ['A_designed_typ', 'A_designed_worst', 'B_fixed_interlock', 'C_fixed_key', 'D_fixed_temp', 'E_fixed_watchdog']
COLS = ['chain', 'safe', 'en', 'ilas', 'rly', 'iled', 'popt', 'temp', 'rstn', 'frst', 'vset']
T_EVT, T_BACK, T_RST2 = 6e-3, 9e-3, 11e-3


def load(name):
    d = np.loadtxt(name + '.txt')
    t = d[:, 0]
    return t, {c: d[:, 2 * i + 1] for i, c in enumerate(COLS)}


def first(t, cond, after):
    idx = np.where((t > after) & cond)[0]
    return t[idx[0]] if len(idx) else np.nan


def at(t, y, tt):
    return np.interp(tt, t, y)


rows = []
for n in NAMES:
    t, v = load(n)
    i0 = at(t, v['ilas'], T_EVT - 0.1e-3)
    r = dict(scenario=n)
    r['I_before_mA'] = i0 * 1e3
    r['t_logic_us'] = (first(t, v['safe'] < 1.65, T_EVT) - T_EVT) * 1e6
    r['t_enable_us'] = (first(t, v['en'] < 1.65, T_EVT) - T_EVT) * 1e6
    r['t_I_10pct_us'] = (first(t, v['ilas'] < 0.1 * i0, T_EVT) - T_EVT) * 1e6
    r['t_I_1pct_us'] = (first(t, v['ilas'] < 0.01 * i0, T_EVT) - T_EVT) * 1e6
    r['t_relay_short_ms'] = (first(t, v['rly'] < 1.65, T_EVT) - T_EVT) * 1e3
    r['S1_pass'] = r['t_I_1pct_us'] <= 1000
    # latch: chain restored at 9 ms, ENABLE must stay low until FAULT_RST at 11 ms
    seg = (t > T_BACK + 0.5e-3) & (t < T_RST2)
    p0 = at(t, v['popt'], T_EVT - 0.1e-3)
    r['P_before_mW'] = p0 * 1e3
    r['latched_until_reset'] = bool(np.all(v['en'][seg] < 1.65) and np.all(v['popt'][seg] < 0.01 * p0))
    # relay closing onto the de-energised laser: junction capacitance discharge (no optical output)
    tr = first(t, v['rly'] < 1.65, T_EVT)
    w = (t > tr - 1e-6) & (t < tr + 2e-6)
    r['relay_spike_peak_mA'] = float(np.max(np.abs(v['ilas'][w])) * 1e3) if np.any(w) else 0.0
    r['relay_spike_nC'] = abs(np.trapezoid(v['ilas'][w], t[w])) * 1e9 if np.any(w) else 0.0
    r['enable_after_reset'] = bool(at(t, v['en'], T_RST2 + 0.1e-3) > 1.65)
    r['I_end_mA'] = at(t, v['ilas'], 15.9e-3) * 1e3
    # S2 indicator: LED on while ENABLE high, off when low
    r['LED_on_mA'] = at(t, v['iled'], T_EVT - 0.1e-3) * 1e3
    r['LED_off_mA'] = at(t, v['iled'], T_EVT + 1e-3) * 1e3
    rows.append(r)

with open('step4_results.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
fmt = '%-20s %7s %8s %8s %9s %9s %8s %5s %7s %7s %7s %6s'
print(fmt % ('scenario', 'I0 mA', 'logic us', 'EN us', 'I<10% us', 'I<1% us', 'relay ms', 'S1', 'latch', 'rearm', 'LEDon', 'LEDoff'))
for r in rows:
    print(fmt % (r['scenario'], '%.1f' % r['I_before_mA'], '%.1f' % r['t_logic_us'], '%.1f' % r['t_enable_us'],
                 '%.1f' % r['t_I_10pct_us'], '%.1f' % r['t_I_1pct_us'], '%.2f' % r['t_relay_short_ms'],
                 'PASS' if r['S1_pass'] else 'FAIL', r['latched_until_reset'], r['enable_after_reset'],
                 '%.1f' % r['LED_on_mA'], '%.2f' % r['LED_off_mA']))
