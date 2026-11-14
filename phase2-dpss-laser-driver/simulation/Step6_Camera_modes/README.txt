Phase 2 - Step 6: Camera trigger mode A vs mode B (simulation)
=============================================================

Question
--------
Who triggers the PCO.panda 4.2 bi exposure?
  Mode A: the PC, by software (PCO SDK), as the supervisor controls the camera.
          The board does not drive the camera input at all; it only reads Status Expos.
  Mode B: the board, through the camera trigger input (SMA #1), using CAM_TRIG + JP501.
In both modes the board switches each laser on LEAD before the exposure and off at the
falling edge of Status Expos, so every image belongs to exactly one laser.

How it was simulated
--------------------
- The real firmware core (Firmware_Step5/firmware) runs against the board model, with the
  PC client in the loop: snake scan of 4 x 5 positions x 4 lasers, repeated with 5 seeds
  (400 images per scenario).
- Camera: rolling-shutter model with the timing of the pco.panda 4.2 manual:
  line time 12.174 us, 2048 lines (24.9 ms from first to last line), trigger -> exposure
  2 line times + jitter <= 1 line time. Status Expos signal timing is selectable as in the
  camera (First Line / common time of All lines / overall time of All lines).
- Laser: first-order DPSS response with tau = 1 ms (worst case of Step 1), LEAD 5 ms.
- PC (mode A): board event -> USB CDC -> Python -> wait -> SDK trigger. The latencies are
  ASSUMPTIONS, three cases:
    A1 tuned timing loop (busy-wait, dedicated thread)
    A2 typical Python 3.11+ on Windows (time.sleep ~1 ms, 1 % OS stalls of 2-20 ms)
    A3 default Windows timer (15.6 ms tick)
  They can be measured on the real PC: the board time-stamps STAGE_IN and Status Expos with
  13.3 ns resolution, so (exposure start - laser on - LEAD) is the real PC latency.
- Scan settings: stage step 300 ms (assumed), SETTLE 2 ms, LEAD 5 ms, exposure 10 ms,
  GAP 20 ms (firmware rule GAP + LEAD >= 25 ms camera minimum period).

Results (step6_results.csv, step6_summary.txt)
----------------------------------------------
                                   B        A1        A2        A3
Images fully and evenly lit     400/400   400/400   400/400   400/400
Faults                             0         0         0         0
Exposure start after laser
  stable, mean (max)          0.031 ms  1.5 (3.6)  3.4 (22)  9.9 (31) ms
Laser light not used by the
  camera per image (mean)       5.0 ms    6.5 ms    8.4 ms   14.9 ms
Time per position (no move)    222 ms    228 ms    236 ms    262 ms
Scan 4 x 5 (300 ms moves)     10.44 s   10.57 s   10.71 s   11.23 s
Exposure start vs stage edge
  (spread)                       12 us   2.1 ms    14 ms     27 ms
Row uniformity (min row)        99.93 %   99.96 %   99.98 %   99.99 %

Reading the table:
- Both modes produce correct images: the board waits for Status Expos and keeps the laser
  on until the last sensor line has finished, so a late PC trigger costs time, not images.
- Mode B is deterministic: the exposure follows the board trigger within the camera's own
  jitter (<= 1 line time, 12 us); the board edges themselves are at ns level (F4 met).
- Mode A costs 1.5-10 ms of extra laser light per image and 1-8 % of scan time, depending
  on how well the PC software is timed. Its exposure timing varies by milliseconds, but the
  board time stamps record the true times in both modes.
- Camera safety: mode A has no electrical connection to the camera trigger input. Mode B
  drives it through the protected buffer (74LVC1G125, CAM_OE_N, JP501, pulse <= 100 us,
  period >= 25 ms); camera input is 3.3 V LVTTL, 5 V tolerant.

Important finding for both modes: Status Expos signal timing
-------------------------------------------------------------
The panda has a rolling shutter: line 2048 starts 24.9 ms after line 1. Because the board
turns the laser off at the end of Status Expos, the camera must be set (Camware / SDK) to
"Status Expos = overall time of All lines" (any line integrating):
  overall time of All lines, 10 ms : all rows 99.9-100 % lit            -> correct
  First Line, 10 ms                : laser off after line 1 -> 1555 of 2048 rows below 50 %
  common time of All lines, 40 ms  : rows from 100 % down to 40 %
  common time of All lines, 10 ms  : no common window (exposure < read-out), no pulse,
                                     the firmware stops with EXPOSURE_TIMEOUT (safe)
(fig_s6_expos_setting.png)

Recommendation
--------------
Start with mode A: it follows the supervisor's decision (the PC controls the camera),
needs no wiring to the camera input (no camera risk) and the simulation shows the cost is
small. Use mode B only if microsecond-repeatable exposure timing or the shortest laser
exposure of the sample becomes necessary. In both modes, set Status Expos to "overall time
of All lines". Possible later firmware improvement: the GAP rule (GAP + LEAD >= 25 ms) is
conservative, because the read-out is already inside Status Expos; allowing GAP ~1 ms would
save about 57 ms per position (3 gaps).

Files
-----
fig_s6_timeline.png       one position, mode B vs mode A (A2)
fig_s6_latency.png        exposure start after laser stable, unused laser light per image
fig_s6_expos_setting.png  light per sensor row for the Status Expos settings
step6_results.csv         all metrics per scenario
step6_summary.txt         printed summary
Scripts (in Firmware_Step5\sim): mode_compare.py (models), step6_report.py (runs all,
writes this folder's results to sim\results\step6). Run from Firmware_Step5:
    py -3.13 sim\step6_report.py
Source for the camera timing: pco.panda 4.2 / 4.2 bi user manual (Excelitas PCO),
chapters 6 and 7 (line time, trigger delay and jitter, Status Expos options, I/O levels).
