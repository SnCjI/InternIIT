MULTISPECTRAL LED DRIVER, 5 CHANNELS  -  FABRICATION PACKAGE v1.0
Phase 1 (design and simulation)  -  October 2026
Author: Julia Isabel Sanchez Cruz
=====================================================================

1. BOARD SPECIFICATIONS
   Dimensions ............. 118.0 x 43.0 mm
   Layers ................. 2 (F.Cu / B.Cu)
   Material ............... FR-4, 1.6 mm
   Copper ................. 1 oz (35 um)
   Minimum track width .... 0.3 mm (PWM signals)
   Power tracks ........... 0.8 mm (VIN+, GND, LED VOUT)
   Minimum clearance ...... 0.2 mm
   Minimum drill .......... 0.75 mm (TO-92 pads)
   Mounting holes ......... 4 x 3.2 mm non-plated (M3 screw)
   Suggested finish ....... HASL, green solder mask, white silkscreen

2. CONTENTS
   1_Gerbers_and_Drill/   Gerber X2 (copper, mask, paste, silkscreen,
                          outline), .gbrjob job file and Excellon drill
                          files (PTH and NPTH).
   2_Assembly/            Bill of materials (BOM) and component
                          position file (CSV, mm).
   3_Documentation/       Schematic (PDF), Gerber preview and DRC result.
   4_KiCad_Sources/       Editable KiCad 10 project (.kicad_pro/sch/pcb).

3. BILL OF MATERIALS
   Ref.            Qty    Value        Package
   Qe1-Qe5         5      P2N2222A     TO-92
   R1-R5           5      1 kOhm 1/4W  Axial DIN0207, 10.16 mm pitch
   J0-J4           5      Header 1x6   2.54 mm  (to MEAN WELL LDD-H modules)
   J5              1      Header 1x8   2.54 mm  (12 V input + ESP32 PWM)
   D0-D4           5      LED 5 mm     LED output of each channel
                                       (VOUT+/VOUT-). In the final system
                                       the COB LED leads are soldered here.

4. IMPORTANT ASSEMBLY NOTES
   - TRANSISTOR: use exactly P2N2222A (pinout 1 = Collector, 2 = Base,
     3 = Emitter). The PN2222A has a different pin order (E-B-C) and is
     NOT compatible with this footprint.
   - LED: the square pad is the cathode (K, to VOUT-).
   - WARNING: do NOT fit 5 mm LEDs in D0-D4 while an LDD-H module is
     installed; the LDD-H delivers 350-700 mA and would destroy a 5 mm
     LED. With an LDD-H installed, connect the COB LED leads to D0-D4.
   - J5: pin 1 = +12 V, pins 2-3 = GND, pins 4-8 = PWM_CH0..CH4
     (ESP32 GPIO 4, 5, 18, 19, 21). The ESP32 ground must be connected
     to GND on this board.
   - Channels: CH0 = UV, CH1 = Blue, CH2 = Green, CH3 = Red, CH4 = NIR.
   - The NPN stages invert the dimming signal (open collector on the
     LDD-H DIM input); the firmware must invert the duty cycle
     (1023 - duty) so that SET/ALL give the requested brightness.
     Reference firmware: 500 Hz, 10-bit PWM (within the 100 Hz - 1 kHz
     DIM range specified in the LDD-H datasheet).
   - While the ESP32 is booting or being programmed, the PWM outputs are
     not driven and the LEDs may turn on at full current; do not look
     directly at the UV channel during start-up.

5. VERIFICATION
   ERC (schematic): 0 errors.
   DRC (KiCad 10): 0 errors, 0 warnings, 0 unrouted connections,
   0 schematic-parity differences.
