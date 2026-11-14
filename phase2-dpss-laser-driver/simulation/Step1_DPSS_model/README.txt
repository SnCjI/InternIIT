PHASE 2 - STEP 1: DPSS LASER MODEL (Thorlabs DJ532-40)
Author: Julia Isabel Sanchez Cruz
==========================================================
Source: Thorlabs "DPSS Laser Diode DJ532-40" spec sheet, 22441-S01 Rev B
        (June 13, 2012): specification table and Typical Operation Curve.

Datasheet values used
  Optical output power ....... 40 mW typ, 50 mW max
  Operating current @ Po ..... 330 mA typ, 400 mA max
  Operating voltage @ Po ..... 1.9 V typ, 2.2 V max
  Slope efficiency ........... 0.1 W/A min, 0.2 W/A typ
  LD reverse voltage (max) ... 2 V
  Operating temperature ...... 20-25 C
  Pinout (Style E) ........... pin 2 = case = LD anode, pin 3 = LD cathode,
                               pin 1 = not connected

Model (ngspice, dpss_model.cir)
  Electrical : pump diode fitted to the LIV voltage curve
               (Is = 1.52e-14 A, N = 2.13, Rs = 0.58 ohm):
               1.55 V @ 20 mA, 1.89 V @ 330 mA, 1.94 V @ 400 mA.
  Optical    : green light is produced by frequency doubling (KTP), so the
               output grows roughly with the square of the pump current above
               threshold:  P = K (I - Ith)^2,  fitted to the LIV curve:
               K = 1.027 W/A^2, Ith = 162 mA.
               First-order lag tau. tau is NOT specified by Thorlabs, so it
               is swept: 10 us, 100 us, 1 ms. (Optical power as voltage,
               1 V = 1 W.)

Results
  On the typical curve: 40 mW at 359 mA, 50 mW at about 382 mA,
  58 mW at 400 mA. The table value (40 mW at 330 mA typ) shows that units
  differ by tens of mA.
  -> The 50 mW optical limit can be reached BELOW the 400 mA current limit.
     Keep 400 mA as the hardware clamp, and add a per-unit current limit
     set from calibration (firmware), so that P never exceeds 50 mW.

  Step 0 -> 359 mA (40 mW):  tau     t90       t99
                             10 us   24 us     47 us
                             100 us  231 us    462 us
                             1 ms    2.3 ms    4.6 ms
  Fraction of the ideal light dose delivered when the laser is switched on
  at the start of the camera exposure:
                      exposure:  100 us   1 ms    10 ms
                      tau 10 us   89 %    99 %    100 %
                      tau 100 us  36 %    90 %     99 %
                      tau 1 ms     5 %    37 %     90 %
  Switching the pump current at the exposure edge is only acceptable when
  exposure >> 5 tau. Otherwise turn the laser on 5 tau before the exposure
  (camera programmable delay 0-5 s) or gate the light with an AOM.

Design note: the case is the LD anode. If the laser mount is grounded, the
anode is at ground and the driver must be designed for it (or the mount
must be electrically isolated). To be resolved in Step 2.

Run: ngspice -b dpss_model.cir ; python3 analyze1.py
