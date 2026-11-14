Phase 2 - Step 4: Safety chain simulation (ngspice-42, analog + XSPICE logic)
==========================================================================

What is simulated
-----------------
The hardware safety chain from the KiCad schematic, all the way to the laser current
and light output of channel 1 (40 mW set point, DAC 2.244 V -> 359 mA, DPSS tau 100 us):

  J701 KEY -> J702 INTERLOCK -> CHAIN (R701 10k, C701)
  CHAIN, TEMP_OK (PC817 U507, R514) and TPS3823 RESET -> U702 74LVC1G11 (AND3) -> SAFE_OK
  SAFE_OK -> CLR of U703 74LVC2G74 (D = 1, CLK = FAULT_RST GP7) -> ENABLE (GP15)
  ENABLE -> U101 AND (with LASER_ON1) -> U102 TS5A3159 (DAC or GND) -> current loop
  ENABLE -> Q102 -> relay K101 (G6K, NC contacts short the laser, 3 ms max)
  ENABLE -> Q701 -> D701 emission LED (R703 330 R from +5 V)

Sequence in every run: FAULT_RST at 0.1 ms (arm), LASER_ON1 at 4 ms, safety input lost at 6 ms,
input restored at 9 ms (the latch must stay open), FAULT_RST at 11 ms (re-arm), end at 16 ms.

Scenarios
---------
A_designed_typ     Interlock opens, schematic as drawn: C701 100 nF, plain CMOS AND input,
                   typical threshold 1.5 V
A_designed_worst   Same, worst-case input threshold VIL = 0.8 V (74LVC datasheet)
B_fixed_interlock  Interlock opens, proposed fix: C701 10 nF + 74LVC2G17 Schmitt buffer
                   (switches at about 1.7 V rising / 0.8 V falling, worst case used)
C_fixed_key        Key switch turned off, proposed fix
D_fixed_temp       Temperature unit drops TEMP_OK (opto turn-off tau 20 us, estimated)
E_fixed_watchdog   TPS3823 asserts RESET (firmware stopped toggling WDI; the real device
                   waits its 1.6 s typical timeout first, not included in the times below)

Results (times from the moment the safety input changes)
--------------------------------------------------------
Scenario            ENABLE low   I < 10 %   I < 1 %    Relay short   S1 (<= 1 ms)
A_designed_typ        790 us      800 us     822 us     3.79 ms       PASS (small margin)
A_designed_worst     1418 us     1428 us    1450 us     4.42 ms       FAIL
B_fixed_interlock     144 us      154 us     176 us     3.14 ms       PASS
C_fixed_key           144 us      154 us     176 us     3.14 ms       PASS
D_fixed_temp           43 us       54 us      75 us     3.04 ms       PASS
E_fixed_watchdog      0.02 us      10 us      32 us     3.00 ms       PASS

All scenarios:
- Latch: ENABLE stays low after the input is restored, until FAULT_RST (no automatic restart).
- Re-arm: FAULT_RST switches ENABLE on again; the laser emits only after the relay opens (3 ms).
- S2 emission LED: 9.3 mA while ENABLE is high, 0 mA when low.
- Relay closing on the de-energised laser: junction-capacitance discharge of 0.1-1 A for a few ns
  (0.06-0.2 nC), no optical output (forward voltage already below threshold).

Finding and fix (applied in KiCad Rev B, 2026-11-07)
------------------------
With C701 = 100 nF the CHAIN node falls with tau = 10k x 100n = 1 ms into a non-Schmitt input.
At the worst-case threshold (0.8 V) the AND gate switches 1.42 ms after the interlock opens,
so requirement S1 (current cut within 1 ms) is not met. The slow edge also violates the
74LVC input rise/fall rule (slow input edges can cause oscillation and extra supply current).

Fix:
1. C701 100 nF -> 10 nF (tau 100 us, still filters contact bounce and cable noise).
2. Add a 74LVC2G17 dual Schmitt buffer between CHAIN / TEMP_OK and the U702 inputs.
Result: worst case 176 us to 1 % current, 5.7x margin to S1.

Files
-----
gen_s4.py            writes the six netlists (*.cir) from one template
*.cir                ngspice netlists, one per scenario
channel_s4.lib       laser channel subcircuit (Step 2 channel + relay contacts)
dpss.lib             DPSS laser model (Step 2)
analyze4.py          measures every scenario, writes step4_results.csv
plots4.py            writes the three figures
step4_results.csv    full results table
fig_s4_interlock.png interlock opening: as drawn (typ / worst) vs fix
fig_s4_sequence.png  full sequence with the fix: fault, latch, re-arm, relay, LED
fig_s4_paths.png     current turn-off for watchdog, TEMP_OK and key/interlock

How to run (Linux or WSL, ngspice 42 with XSPICE)
-------------------------------------------------
python3 gen_s4.py
for f in *.cir; do ngspice -b $f > ${f%.cir}.log; done
python3 analyze4.py
python3 plots4.py
