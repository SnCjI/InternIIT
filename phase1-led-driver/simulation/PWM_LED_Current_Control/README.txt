PWM CONTROL OF THE LED CURRENT  -  Phase 1, report Section V-C
Author: Julia Isabel Sanchez Cruz
=================================================================

Purpose
  Shows how the ESP32 sets the LED current: the constant-current stage
  (LDD-H in the product) fixes the current amplitude I_on, and the PWM duty
  cycle D sets the fraction of each 2 ms period during which it flows:

        I_avg = D x I_on        (D = duty / 1023)

  The NPN buffer inverts the signal, so the firmware writes 1023 - duty.

Files
  PWM_LED_current_simulation.pdsprj   Proteus 8.13 project. GPIO model
                                      (0/3.3 V, 500 Hz), R1 1k, Q1 2N2222,
                                      R2 10k pull-up (DIM), LDD-H stand-in
                                      (Q3 TIP122, Q2 2N2222, RS 1.8 ohm),
                                      LED stand-in (1N4007 + 6 ohm).
                                      Graph trace ILED = V(RS)/1.8.
  proteus_ILED_D<xx>pct.csv           Exported Proteus data (TIME, PWM,
                                      DIM, ILED) at D = 0, 5, 20, 50, 80
                                      and 100 %.
  proteus_duty_results.csv            Average current per Proteus run.
  ngspice_duty_sweep.cir              ngspice netlist of the same circuit,
                                      transient sweep D = 0-100 % (check).
  ngspice_duty_sweep_results.csv      Average current per 10 % step.
  sim_06 ... sim_09 (.png/.jpg)       Figures 13-16 of the report and the
                                      raw Proteus screenshot (50 %).

  To reproduce a duty cycle in Proteus: edit the PWM generator, set
  "Ancho pulso (%)" = 100 - D (the buffer inverts), run the graph
  (space bar). D = 100 %: set Pulsed (High) Voltage = 0 V.

Results
  Proteus   D (%)   I_avg (mA)   D x I_on (mA)
              0        0.0           0.0
              5       17.5          18.2
             20       72.0          72.7
             50      181.0         181.7
             80      290.0         290.7
            100      363.3         363.3
  I_on = 363.3 mA at every duty; I_off = 0 mA. Constant -0.7 mA offset
  = 3.6 us turn-on delay per pulse (about 2 LSB).
  ngspice D = 0-100 %: same linear behaviour, I_on = 356 mA.

Run:  ngspice -b ngspice_duty_sweep.cir
