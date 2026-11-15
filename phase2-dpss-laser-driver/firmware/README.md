# Step 5 - Pico 2 Firmware (MicroPython + PIO) and its Simulation

Phase 2, DPSS 4-channel laser driver. Simulation-only: the firmware is complete and ready to be
copied to a Raspberry Pi Pico 2, and it was verified on the PC without hardware.

## Folder

| Path | Content |
|---|---|
| `firmware/main.py` | Main loop: USB serial commands, periodic safety tasks |
| `firmware/dpss_core.py` | Operating states, command set, current limits and ramps, frame queue, time stamps |
| `firmware/dpss_pio.py` | PIO programs: `frame_seq` (hardware-timed frames), `edge_ts` (time stamps), `pulse` (stage output) |
| `firmware/dac8565.py` | DAC8565 driver (frame format from the TI datasheet) |
| `firmware/hw_pico.py` | Pico 2 pins, SPI, state machines (only file that touches the hardware) |
| `firmware/config.py` | GPIO map (matches the KiCad schematic), limits, timing defaults |
| `pc/dpss_client.py` | PC client (pyserial) for the supervisor's Python interface |
| `pc/scan_example.py` | Snake-by-row scan example (stage and camera are placeholders) |
| `sim/` | Simulation: PIO assembler, cycle-accurate PIO runs, board model, unit tests |
| `sim/results/` | Figures, CSV and the verification report |
| `run_all.py` | Runs the whole verification |

## How the timing works

At each stage position the PIO state machine runs one frame per laser, without the CPU:

stage in-position edge (BNC) -> SETTLE -> LASER_ON(k) -> LEAD -> camera trigger -> wait for
Status Expos high -> Status Expos low -> LASER_OFF -> "frame done" to the CPU.

The next laser starts GAP after the previous exposure (camera read-out). Two more state machines
time-stamp every edge of STAGE_IN and Status Expos (13.3 ns counter). The PC receives `EVT` lines
with the time stamps.

* Mode A: the PC triggers the camera with the PCO SDK; the board switches the laser off at the end of
  Status Expos. The camera trigger output stays disabled (CAM_OE_N high, JP501 open).
* Mode B: the board also triggers the camera (`CAMTRIG ON` and JP501 closed).

## Commands (USB CDC serial, one line each, answer `OK ...` or `ERR reason`)

| Command | Function |
|---|---|
| `*IDN?`, `PING`, `STATUS` | Identity, heartbeat, full state |
| `RESET` | Re-arm the hardware ENABLE latch (key, interlock and temperature must be OK) |
| `SET <ch> <mA>` / `LIMIT <ch> <mA>` | Set point (ramp >= 100 ms 0->400 mA) / per-unit limit (stored in flash) |
| `ARM` / `DISARM` | READY (set points ramped in) / back to ARMED (ramped to 0) |
| `MODE PC` / `MODE TRIG` | Laser gates from commands / from the PIO frames |
| `ON <ch>` / `OFF <ch or ALL>` | Manual gates (MODE PC) |
| `SETTLE`, `LEAD`, `GAP`, `TRIGW <us>` | Frame timing |
| `CAMTRIG ON/OFF` | Camera trigger output (mode B only) |
| `POS 1,2,3,4 [WAIT/NOWAIT]` | Queue the frames of one stage position |
| `ABORT`, `STAGEPULSE <us>` | Stop frames / pulse to the stage controller |

## Safety behaviour (firmware side; the hardware chain acts independently)

* Power-up and reset: DAC = 0, all LASER_ON low, camera and stage outputs disabled.
* Set point above the unit limit (default 330 mA) or a limit above 400 mA: rejected.
* Any FAULT (chain open, temperature, USB silent > 3 s while armed, exposure never ending > 2 s):
  lasers off, DAC = 0, outputs disabled, and the firmware stops the watchdog so the hardware
  ENABLE latch opens too. Only `RESET` re-arms, and the set points must be sent again.
* Camera: trigger pulse <= 100 us, minimum period 25 ms, output only in mode B. The exposure
  must last longer than the trigger pulse.

## Verification results (`python run_all.py`)

| Check | Result |
|---|---|
| PIO opcodes vs Adafruit's independent assembler | 36/36 identical |
| MicroPython syntax (mpy-cross v1.29) | all 6 files compile |
| Unit tests against the requirements (F2, F4, E2, E3, E5, S1, S4, S5, camera) | 15/15 pass |
| Interval error, 100 random intervals, cycle-accurate | <= 3.3 ns (requirement 1 us) |
| Time-stamp error, 120 edges | <= 6.7 ns |
| End of exposure -> laser off | 13.3 ns (+13.3 ns input synchroniser) |
| LEAD 5 ms with DPSS tau = 1 ms (worst case of Step 1) | 0.067 % energy deficit |
| Snake scan 4 x 5, 4 lasers, PC client in the loop | 80/80 images fully illuminated, 9.05 s |
| Real firmware on a virtual Pico in Wokwi (`wokwi/`) | boot, interlock fault, hardware-timed frame: all OK |

## Running the simulation

```
pip install rp2040-pio-emulator adafruit-circuitpython-pioasm pytest numpy matplotlib pyserial
python run_all.py
```

Interactive test of the firmware (same commands as the PC, plus `!` commands that act on the
simulated hardware: interlock, key, temperature, stage, camera):

```
python sim/sim_console.py
```

## Loading on the Pico 2 (when the board exists)

1. Flash MicroPython for the Pico 2 (RP2350) from micropython.org.
2. Copy the six files of `firmware/` to the Pico with Thonny.
3. From the PC: `DPSSDriver.open('COM5')` (see `pc/dpss_client.py`).

## Open points (to confirm with the supervisor)

* HO-MPC-4H BNC: direction, voltage level and the real step time (300 ms assumed here).
* Camera trigger mode A or B, and the PCO exposure / trigger settings.
* Real DPSS response time of each unit (LEAD can be reduced if tau is short).

Note: SPI0's default MISO pin is GPIO16 (CAM_OE_N on this board); `hw_pico.py` re-claims the pin as
an output right after creating the SPI.
