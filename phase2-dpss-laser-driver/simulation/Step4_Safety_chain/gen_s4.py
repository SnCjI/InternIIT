# Phase 2 - Step 4: safety chain -> ENABLE -> laser current (ngspice, analog + XSPICE logic)
# One netlist per scenario. Values from the KiCad schematic (safety.kicad_sch, laser_channel.kicad_sch).
import sys

TEMPLATE = r"""* Step 4 safety chain - {name}
* {desc}
.include channel_s4.lib
.include dpss.lib
Vp vp 0 5
Vn vn 0 -5
Vl vlas 0 -3.3
V33 v33 0 3.3
V5 v5 0 5
* ---- laser channel 1 at the 40 mW set point (DAC 2.244 V -> 359 mA), LASER_ON1 high from 4 ms
Vd dac 0 2.244
Vlon lon 0 PWL(0 0 4m 0 4.001m 3.3)
XC dac lon en 0 cath vlas vp vn rly CHANNEL
XL 0 cath popt DPSS params: TAU=100u
* ---- J701 KEY and J702 INTERLOCK in series: +3V3 -> KEY_LOOP -> CHAIN  (control 3.3 V = closed)
Vkey kc 0 {key}
Vint ic 0 {intl}
Skey v33 kloop kc 0 SWC
Sint kloop chain ic 0 SWC
.model SWC SW(Ron=0.1 Roff=1G Vt=1.65 Vh=0.1)
R701 chain 0 10k
C701 chain 0 {c701}
* ---- CHAIN input of the AND gate: threshold {vt_chain} V, hysteresis +-{vh_chain} V (inverting switch)
Rpc v33 chn 10k
Sch chn 0 chain 0 SWI1
.model SWI1 SW(Ron=1 Roff=1G Vt={vt_chain} Vh={vh_chain})
* ---- TEMP_OK from the PC817 opto (estimated turn-off: tau 20 us into R514 10 k)
Vtled tled 0 {temp}
Rtl tled tlag 20k
Ctl tlag 0 1n
Btemp temp 0 V = 3.3*min(1, 2*v(tlag)/3.3)
R514 temp 0 10k
Rpt v33 tmpn 10k
Stp tmpn 0 temp 0 SWI2
.model SWI2 SW(Ron=1 Roff=1G Vt={vt_temp} Vh={vh_temp})
* ---- TPS3823 RESET (open-drain, active low): {rst_note}
Vrst rstn 0 {rst}
* ---- U702 74LVC1G11 (AND3) -> SAFE_OK -> CLR of U703
Bsafe safe 0 V = 3.3*u(1.65-v(chn))*u(1.65-v(tmpn))*u(v(rstn)-1.65)
* ---- U703 74LVC2G74: D = 1, CLK = FAULT_RST, CLR = SAFE_OK (async) -> Q = ENABLE
Vfr frst 0 PWL(0 0 0.1m 0 0.10001m 3.3 0.12m 3.3 0.12001m 0 {frst2})
abr [safe frst] [safe_d frst_d] adcb
.model adcb adc_bridge(in_low=1.5 in_high=1.5)
ainv safe_d nsafe_d inv1
.model inv1 d_inverter(rise_delay=3n fall_delay=3n)
aone one pu1
.model pu1 d_pullup
azero zero pd1
.model pd1 d_pulldown
aff one frst_d zero nsafe_d q_d nq_d dff1
.model dff1 d_dff(clk_delay=5n reset_delay=5n)
aout [q_d] [en] dacb
.model dacb dac_bridge(out_low=0 out_high=3.3 t_rise=2n t_fall=2n)
* ---- relay K101 drive: Q102 + coil; contacts follow ENABLE after the G6K operate/release time
* G6K-2F-Y: operate and release time <= 3 ms (datasheet maximum) -> modelled as a 3 ms delay
arly q_d rly_d rdly
.model rdly d_buffer(rise_delay=3m fall_delay=3m)
arly2 [rly_d] [rly] dacb
* ---- emission indicator D701 (S2): Q701 gate = ENABLE, LED current from +5 V via R703 330R
Sled ledk 0 en 0 SWL
.model SWL SW(Ron=2 Roff=1G Vt=1.65 Vh=0.1)
Vledm v5 ledm 0
R703 ledm leda 330
Dled leda ledk DLED
.model DLED D(Is=1e-20 N=1.8)
.control
tran {tstep} {tstop} 0 {tmax}
wrdata {name}.txt v(chain) v(safe) v(en) i(v.xl.vs) v(rly) i(Vledm) v(popt) v(temp) v(rstn) v(frst) v(xc.c)
quit
.endc
.end
"""

PWL_ON = "DC 3.3"
def opens(t, back=None):
    s = "PWL(0 3.3 %.5fm 3.3 %.5fm 0" % (t, t + 0.0001)
    if back:
        s += " %.5fm 0 %.5fm 3.3" % (back, back + 0.0001)
    return s + ")"

T_EVT, T_BACK, T_RST2 = 6, 9, 11
FRST2 = "%.5fm 0 %.5fm 3.3 %.5fm 3.3 %.5fm 0" % (T_RST2, T_RST2 + 0.00001, T_RST2 + 0.02, T_RST2 + 0.02001)
CRL = "4.33u"     # 1 k x 4.33 uF: 50 % point at 3.0 ms = G6K max operate/release time

SC = {
  # name: (description, c701, vt, vh (chain), vt, vh (temp), key, intl, temp, rst, rst_note)
  'A_designed_typ': ("Interlock opens; schematic as drawn (C701 100 nF, plain CMOS input, typical threshold 1.5 V)",
                     "100n", 1.5, 0.0, 1.5, 0.0, PWL_ON, opens(T_EVT, T_BACK), PWL_ON, PWL_ON, "held high"),
  'A_designed_worst': ("Interlock opens; schematic as drawn, worst-case input threshold VIL = 0.8 V",
                     "100n", 0.8, 0.0, 0.8, 0.0, PWL_ON, opens(T_EVT, T_BACK), PWL_ON, PWL_ON, "held high"),
  'B_fixed_interlock': ("Interlock opens; proposed fix: C701 10 nF + Schmitt buffer 74LVC2G17 (VT- worst 0.8 V, hysteresis)",
                     "10n", 1.25, 0.45, 1.25, 0.45, PWL_ON, opens(T_EVT, T_BACK), PWL_ON, PWL_ON, "held high"),
  'C_fixed_key': ("Key switch turned off; proposed fix", "10n", 1.25, 0.45, 1.25, 0.45,
                     opens(T_EVT, T_BACK), PWL_ON, PWL_ON, PWL_ON, "held high"),
  'D_fixed_temp': ("Temperature unit drops TEMP_OK; proposed fix", "10n", 1.25, 0.45, 1.25, 0.45,
                     PWL_ON, PWL_ON, opens(T_EVT, T_BACK), PWL_ON, "held high"),
  'E_fixed_watchdog': ("Watchdog: firmware stopped toggling WDI, TPS3823 asserts RESET (after its 1.6 s timeout) for 200 ms",
                     "10n", 1.25, 0.45, 1.25, 0.45, PWL_ON, PWL_ON, PWL_ON,
                     "PWL(0 3.3 %.5fm 3.3 %.5fm 0 %.5fm 0 %.5fm 3.3)" % (T_EVT, T_EVT + 0.00001, T_EVT + 2.0, T_EVT + 2.00001),
                     "low at the event for 200 ms (shortened to the window)"),
}

for name, (desc, c701, vtc, vhc, vtt, vht, key, intl, temp, rst, note) in SC.items():
    open(name + '.cir', 'w').write(TEMPLATE.format(
        name=name, desc=desc, c701=c701, vt_chain=vtc, vh_chain=vhc, vt_temp=vtt, vh_temp=vht,
        key=key, intl=intl, temp=temp, rst=rst, rst_note=note, frst2=FRST2, crl=CRL,
        tstep='1u', tstop='16m', tmax='2u'))
print('\n'.join(SC))
