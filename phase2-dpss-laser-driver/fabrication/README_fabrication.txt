DPSS_Driver_4ch - Fabrication package, Rev B (2026-11-07)
Author: Julia Isabel Sanchez Cruz - IEEE EMBS SBC internship 2026, Phase 2

Board: 4 layers, 170 x 120 mm, FR-4 1.6 mm, 1 oz copper.
Layer use: F.Cu signals + GND pour | In1.Cu GND plane | In2.Cu LAS_NEG (-3.3 V) under
the laser channels, GND elsewhere | B.Cu signals + GND pour.
Checks (KiCad 10): ERC 0 errors; DRC 0 errors, 0 unconnected, schematic parity 0.

1_Gerbers_and_Drill  Gerber X2 (4 copper, 2 mask, 2 paste, 2 silkscreen, edge cuts,
                     job file), Excellon PTH and NPTH with drill maps
2_Assembly           BOM (grouped by value and footprint), component positions (mm)
3_Documentation      Schematic PDF (8 sheets), PCB top/bottom images, Gerber preview
4_KiCad_Sources      KiCad 10 project: schematic (5 files), PCB, project rules

Rev B: C701 100 nF -> 10 nF and U704 74LVC2G17 Schmitt buffer + C705 in the safety
chain (Step 4 simulation: worst-case current cut 1.45 ms -> 0.18 ms).
Before ordering: confirm the stage BNC level and the temperature-OK signal with the
supervisor, and consider a 5 A converter for the -3.3 V rail (see report, Sec. IX).
Jumpers JP501 (camera trigger) and JP502 (stage output) are left OPEN.
