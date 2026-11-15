# Running the real firmware on a virtual Raspberry Pi Pico (Wokwi)

Wokwi simulates the Raspberry Pi Pico with MicroPython, PIO, SPI and the USB serial port, so the
firmware runs unchanged, including `hw_pico.py` (pins, SPI, PIO state machines, synchronized
start), which the PC simulation does not execute.

Board used: **Raspberry Pi Pico (RP2040)**. The firmware uses only features common to the RP2040 and
the RP2350 (same PIO instruction set and registers, same pins). The Pico 2 (RP2350) model of Wokwi was
tried first: the firmware booted, but Wokwi's RP2350 support is partial and MicroPython showed random
errors on files whose SHA-256 matched the originals, so the RP2040 model was used.

## Files in this folder

| File | Content |
|---|---|
| `diagram.json` | virtual circuit (below) |
| `main.py` | `firmware/main.py` + 1 s start-up wait (Wokwi only) |
| `config.py` | `firmware/config.py` with three demo-only values: PIO clock 2 MHz (Wokwi emulates every PIO cycle; 150 MHz runs at ~0 % speed), USB heartbeat 120 s and exposure timeout 20 s (manual test) |
| `wokwi_run_trig_frame.jpg` | screenshot of the hardware-timed frame test |

The other four files (`dac8565.py`, `dpss_pio.py`, `dpss_core.py`, `hw_pico.py`) are used exactly as
they are in `firmware/`.

## Virtual circuit

| Board signal | GPIO | Wokwi part |
|---|---|---|
| LASER_ON1..4 | GP2..GP5 | green LEDs "LASER 1..4" |
| CAM_TRIG / STAGE_OUT | GP11 / GP13 | orange LEDs |
| WDI (watchdog) | GP6 | white LED |
| CAM_OE_N | GP16 | blue LED, on = camera trigger output enabled |
| ENABLE (safety chain + latch) | GP15 | slide switch |
| TEMP_OK | GP14 | slide switch |
| STAGE_IN | GP12 | blue push button (10 k pull-down) |
| CAM_EXPOS (Status Expos) | GP10 | yellow push button (10 k pull-down) |
| DAC SPI: SCLK, DIN, SYNC | GP18, GP19, GP17 | logic analyzer D0..D2 (the DAC8565 itself is not simulated) |
| LASER 1, LASER 2, CAM_TRIG, CAM_EXPOS, STAGE_IN | | logic analyzer D3..D7 |

## Steps

1. Open https://wokwi.com/projects/new/micropython-pi-pico
2. Replace `diagram.json` and `main.py` with the files of this folder; add `config.py` (this folder)
   and `dac8565.py`, `dpss_pio.py`, `dpss_core.py`, `hw_pico.py` (from `firmware/`).
3. Start the simulation (about 1 minute until `EVT BOOT`; the simulation runs at a few % of real time).

## Results (7 Nov 2026)

| Test | Result |
|---|---|
| Boot: SPI, PIO state machines, synchronized start | `EVT BOOT DPSS4CH-FW 0.1` |
| ENABLE and TEMP_OK switches on | `EVT ARMED`, watchdog LED active |
| `SET 1 200`, `ARM`, `ON 1` | `OK` x3, LASER 1 LED on |
| ENABLE switch off (interlock opened) | `EVT FAULT CHAIN_OPEN`, LASER 1 off |
| ENABLE on, `RESET`, `SET 1 200`, `ARM`, `MODE TRIG`, `POS 1` | `EVT ARMED`, `OK 1 frames queued` |
| STAGE button | `EVT TS STAGE_IN t_us=2274757`, LASER 1 switched on by the PIO |
| CAMERA button press / release | `EXPOS_START`, `EXPOS_END`, LASER 1 off, `FRAME_DONE ch=1` |

Two firmware fixes came out of this run (already in `firmware/`):
* `hw_pico.py`: STAGE_IN and CAM_EXPOS are now configured as digital inputs (`Pin.IN`); without this
  the PIO never saw the stage edge.
* `main.py`: the main loop sleeps 1 ms (`time.sleep_ms(1)`) instead of busy-waiting, and a firmware
  error now prints its full traceback.
