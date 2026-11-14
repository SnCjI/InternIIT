# Microscope Illumination Drivers — IIT Kharagpur Summer Internship 2026

This repository collects my work from the **IEEE EMBS Summer Internship 2026** (virtual mode), organized by the IEEE EMBS Student Branch Chapter, the IEEE Student Branch and the IEEE Kharagpur Section at IIT Kharagpur.

The goal of the internship is to build the electronics that light up a sample in a scanning microscope. The project has two phases:

| Phase | What it is | Status |
|---|---|---|
| [**Phase 1 — Multispectral LED driver**](phase1-led-driver/) | A five-channel driver for high-power LEDs (UV, Blue, Green, Red, NIR). An ESP32 sets each LED's brightness with PWM, and a MEAN WELL LDD-H module keeps the current constant. | Complete: designed, simulated, fabrication-ready |
| [**Phase 2 — DPSS laser driver**](phase2-dpss-laser-driver/) | A four-channel driver for DPSS lasers (starting with a Thorlabs DJ532-40, 532 nm). A Raspberry Pi Pico 2 sets each laser's current and times every laser pulse against the camera and the motorized stage. | Complete in simulation; open points waiting on the supervisor |

**Important:** both phases were done **entirely in simulation**. No hardware was bought or built. Every result here comes from circuit simulators (Proteus, ngspice), firmware simulators (Velxio, Wokwi, a PIO emulator and a board model written in Python) and KiCad's design-rule checks. The boards are ready to be manufactured, but they have not been tested on a bench yet.

<p align="center">
  <img src="docs/images/phase2/fig_system.png" width="760" alt="Phase 2 system block diagram">
  <br><em>Phase 2 system: the PC controls the camera and stage, and the driver board times the lasers.</em>
</p>

---

## The idea in a few lines

A microscope that takes images at several wavelengths needs a light source that can switch from one color to another quickly, and that gives the same amount of light every time. Both phases solve this the same way:

1. **Separate "how much current" from "when".** A dedicated analog stage regulates the current through the LED or laser. The microcontroller never carries that current; it only decides when the light is on and what the target current is.
2. **Make the timing hardware-driven.** In Phase 1 the ESP32's LEDC peripheral generates the PWM by itself. In Phase 2 the Pico 2's PIO state machines switch the lasers and time-stamp the camera and stage signals with nanosecond resolution, without involving the CPU.
3. **Verify everything before building.** Each block was simulated on its own, then together, and the PCB was checked with ERC/DRC until it was clean.

---

## What has been done so far

### Phase 1 — LED driver (October 2026)

- ✅ Requirements and architecture for a five-channel driver
- ✅ KiCad schematic (0 ERC errors) and a two-layer 118 × 43 mm PCB (0 DRC violations, 0 unrouted nets)
- ✅ A design review that caught two fatal mistakes before fabrication: a transistor pinout mismatch and reversed LED polarity
- ✅ ESP32 firmware with a simple serial command protocol, tested in a simulator
- ✅ Proteus and ngspice simulations: current regulation, PWM switching, and how the duty cycle sets the LED current
- ✅ Fabrication package: Gerber X2, Excellon drill files, BOM and pick-and-place file
- ✅ IEEE-format report

➡️ Details in [`phase1-led-driver/`](phase1-led-driver/)

### Phase 2 — DPSS laser driver (November 2026)

- ✅ Requirements and architecture, refined over three revisions with the supervisor
- ✅ An ngspice model of the DJ532-40 laser, fitted to its datasheet
- ✅ A precision current channel: 160 mA/V, 400 mA hardware clamp, 8.3 µs edges, no overshoot
- ✅ A hierarchical KiCad schematic with real parts (183 components) and a four-layer 170 × 120 mm PCB, ERC/DRC clean
- ✅ A hardware safety chain (key, interlock, temperature, watchdog → latched ENABLE). The simulation found it was too slow in the worst case, and Rev B fixed it (1.45 ms → 0.18 ms).
- ✅ MicroPython firmware with PIO programs, a PC client, 15/15 unit tests and a run on a virtual Pico
- ✅ A full system simulation with the camera's rolling shutter, which found the camera setting that has to be used
- ✅ Fabrication package (Rev B) and an IEEE-format report

➡️ Details in [`phase2-dpss-laser-driver/`](phase2-dpss-laser-driver/)

---

## What comes next

These are the future objectives, roughly in order:

1. **Close the open points with the supervisor**: the voltage level and direction of the stage's BNC signal, the electrical form of the temperature-OK signal, the camera settings (Status Expos and trigger mode), and the specifications of the other three lasers.
2. **Upsize the −3.3 V laser supply in Phase 2.** The current converter runs at 77 % of its rating when all four lasers are at 400 mA. A 5 A part (for example the LM2678-ADJ) would bring it under the 50 % target.
3. **Repeat the Phase 2 current-channel simulation with the vendor models** of the OPA4197 and NDT3055L.
4. **Phase 1 board v1.1**: add pull-ups on the PWM inputs so the LEDs stay off while the ESP32 boots, and replace the LED footprints with terminal blocks for the COB LEDs.
5. **Build and measure**: fabricate the boards, then measure the LDD-H dimming response, the real DPSS response time, the safety-chain timing and the PC trigger latency (the Phase 2 board time-stamps all of these itself).
6. **Calibrate each laser module** and set its individual current limit.
7. **Firmware improvements**: relax the conservative GAP rule (about 57 ms saved per stage position) and add a check that compares the measured Status Expos width with the expected value before every scan.

---

## Repository map

```
.
├── README.md                     ← you are here
├── docs/images/                  figures used in the READMEs
├── phase1-led-driver/
│   ├── README.md                 step-by-step explanation of Phase 1
│   ├── report/                   IEEE-format report (PDF)
│   ├── kicad/                    KiCad 10 project (schematic + PCB)
│   ├── fabrication/              Gerbers, drill, BOM, positions, schematic PDF, ready-to-order ZIP
│   ├── firmware/                 ESP32 Arduino sketch
│   └── simulation/               Proteus projects, ngspice netlist, CSV results, plots
└── phase2-dpss-laser-driver/
    ├── README.md                 step-by-step explanation of Phase 2
    ├── docs/                     IEEE-format report + requirements & architecture (Rev 3)
    ├── kicad/                    KiCad 10 hierarchical project (5 sheets + PCB)
    ├── fabrication/              Gerbers (4 layers), drill, BOM, positions, PCB images, ZIP (Rev B)
    ├── firmware/                 MicroPython + PIO firmware, PC client, simulators and tests
    └── simulation/               ngspice and Python simulations, Steps 1, 2, 4 and 6
```

## Tools used

KiCad 10 · Freerouting · Proteus 8 · ngspice · Python (NumPy, Matplotlib) · Arduino / ESP32 · MicroPython · Raspberry Pi Pico 2 PIO · Wokwi · Velxio

## Author

**Julia Isabel Sanchez Cruz** — Electronic Engineering, 4th year
Summer Internship 2026 (virtual), IEEE EMBS SBC, IEEE SB and IEEE Kharagpur Section, IIT Kharagpur
