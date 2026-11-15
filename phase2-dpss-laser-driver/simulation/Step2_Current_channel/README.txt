PHASE 2 - STEP 2: LASER CURRENT-DRIVER CHANNEL (one channel, DJ532-40)
Author: Julia Isabel Sanchez Cruz
=====================================================================
Design assumptions (pending confirmation from the supervisor)
  - Laser case (= LD anode) may be on a grounded heatsink -> grounded-anode
    topology: the anode is GND and the current is sunk from the cathode into
    a negative laser rail V_LAS = -3.3 V. (Also valid if the mount is isolated.)
  - Laser switched through the drive current; the camera gate (Status Expos)
    AND the Pico 2 ENABLE pass the set point (AOM kept as alternative).
  - Op-amps on +/-5 V; logic 3.3 V.

Circuit (channel.lib, figure fig_s2_schematic.png)
  DAC 0-2.5 V -> S1 gate switch (ENABLE AND GATE, 74LVC1G08)
  -> RC slew limiter 1 k / 2.2 nF (tau 2.2 us)
  -> precision clamp 2.5 V (U3 + diode) + buffer U4   => I <= 400 mA in hardware
  -> level shifter U2: 0.16*V + V_LAS
  -> U1 + N-MOSFET M1 + RS 1 ohm: I = 160 mA/V x V_DAC
  Protection: antiparallel Schottky D2 (reverse voltage), 1 nF across laser,
  shorting relay across the laser while ENABLE is low.
  Op-amps and MOSFET are behavioral/generic models (GBW 10 MHz op-amp,
  logic-level NMOS Vth 1.5 V); real part numbers are chosen in Step 3.

Tests and results (ngspice)
  T1 DC transfer (t1_dc.cir)
     slope 160.00 mA/V, offset 0.08 mA, non-linearity < 0.001 mA
     DAC 2.244 V -> 358.5 mA (40 mW); DAC 2.5-3.3 V -> 400.1 mA (clamp)
     V_LAS -3.135 / -3.465 V (+/-5 %): current change < 0.02 mA
  T2 Camera gating at 40 mW, 100 us pulses (t2_gate.cir)
     no overshoot (0.000 %); rise 10-90 % = 8.3 us (t50 = 3.6 us);
     fall t50 = 2.6 us; off current 0.1 mA (below threshold, no light);
     charge delivered in a 100 us gate = 100.0 % of ideal
  T3 Power-up / power-down (t3_power.cir)
     rails ramping, DAC stuck at 3.3 V, GATE high, ENABLE low:
     laser current 0.000 mA; firmware ramp 0 -> 359 mA in 100 ms, no
     overshoot; power-down with laser on: no current spike, no reverse V
  T4 Reverse kick, 2 A / 1 us into the cathode (t4_reverse.cir)
     max reverse voltage 0.47 V (abs. max 2 V); laser current restored
  T5 Worst-case compliance: laser at 2.2 V, rail -5 % (t5_compliance.cir)
     400 mA still regulated, MOSFET Vds = 0.54 V, P_MOSFET = 0.22 W

Note: 50 mW can be reached at ~382 mA (Step 1), so the firmware must apply a
per-unit current limit below the 400 mA hardware clamp.

Run: ngspice -b t1_dc.cir (etc.) ; python3 analyze2.py ; python3 plots2.py
