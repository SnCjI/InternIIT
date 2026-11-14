# PIO programs for the DPSS driver (MicroPython rp2 assembler).
# All programs run at the system clock (150 MHz -> 6.67 ns per instruction).
#
#  frame_seq  : one exposure frame per 4 FIFO words, fully timed in hardware:
#               [stage edge] -> settle -> LASER ON -> lead -> camera trigger -> Status Expos high
#               -> Status Expos low -> LASER OFF -> push "done" to the CPU.
#  edge_ts    : free-running counter (2 clock cycles = 13.3 ns per count) that pushes the counter
#               value at each rising and falling edge of one input pin (time stamps).
#  pulse      : one output pulse of programmable width (trigger to the stage controller).
#
# The 'wait' instructions use absolute GPIO numbers (gpio 10 = CAM_EXPOS, gpio 12 = STAGE_IN),
# so they must match config.py.
import rp2
from rp2 import PIO, asm_pio

SEQ_INSTR = 20          # instruction counts (PIO memory is 32 instructions per block)
TS_INSTR = 11


@asm_pio(out_init=(PIO.OUT_LOW,) * 4, sideset_init=PIO.OUT_LOW,
         out_shiftdir=PIO.SHIFT_RIGHT)
# FIFOs are not joined: the TX FIFO holds exactly one frame (4 words) and the RX FIFO returns the
# "frame done" words. The CPU refills the TX FIFO during the frame (milliseconds of margin).
def frame_seq():
    # word 0: 1 = wait for a rising edge on STAGE_IN before starting, 0 = start at once
    pull(block)                 .side(0)
    mov(x, osr)
    # word 1: lead cycles (laser ON -> camera trigger)
    pull(block)
    mov(y, osr)
    # word 2: camera trigger width cycles (kept in ISR)
    pull(block)
    mov(isr, osr)
    # word 3: settle cycles in bits 0..27, laser mask (LASER_ON1..4) in bits 28..31
    pull(block)
    jmp(not_x, "go")
    wait(0, gpio, 12)
    wait(1, gpio, 12)           # stage in position (rising edge)
    label("go")
    out(x, 28)
    label("settle")
    jmp(x_dec, "settle")
    out(pins, 4)                # LASER ON (selected channel)
    label("lead")
    jmp(y_dec, "lead")
    mov(x, isr)                 .side(1)   # camera trigger HIGH (only leaves the board in mode B)
    label("trig")
    jmp(x_dec, "trig")          .side(1)
    wait(1, gpio, 10)           .side(0)   # trigger LOW, wait for exposure start (Status Expos)
    wait(0, gpio, 10)           # end of exposure
    mov(pins, null)             # LASER OFF
    push(noblock)               # frame done -> CPU


@asm_pio()
def edge_ts():
    mov(x, invert(null))        # counter = 0xFFFFFFFF, counts down every 2 cycles
    wrap_target()
    label("low")
    jmp(pin, "rise")
    jmp(x_dec, "low")
    label("rise")
    mov(isr, x)
    push(noblock)               # time stamp of a rising edge
    label("high")
    jmp(pin, "h2")
    jmp("fall")
    label("h2")
    jmp(x_dec, "high")
    label("fall")
    mov(isr, x)
    push(noblock)               # time stamp of a falling edge
    jmp(x_dec, "low")
    wrap()


@asm_pio(set_init=PIO.OUT_LOW)
def pulse():
    pull(block)
    mov(x, osr)
    set(pins, 1)
    label("w")
    jmp(x_dec, "w")
    set(pins, 0)


# ---------------- cycle bookkeeping (measured with the cycle-accurate emulator, sim/) ----------------
# Each interval of frame_seq equals (register value + fixed overhead) clock cycles:
OVH_SETTLE = 4          # stage edge detected -> LASER ON  (+2 cycles input synchronizer in silicon)
OVH_LEAD = 2            # LASER ON -> camera trigger HIGH
OVH_TRIG = 2            # trigger HIGH -> LOW
OVH_GAP = 12            # frame without stage wait: previous LASER OFF -> this LASER ON
# edge_ts: time between consecutive edges = 2 * (x_prev - x_now) + TS_EVENT_CYC cycles (error <= 1 cycle)
TS_CYCLES_PER_COUNT = 2
TS_EVENT_CYC = 3


def us_to_cycles(us, f_hz):
    return int(round(us * f_hz / 1_000_000))


def reg_for(us, f_hz, overhead):
    """Register value that makes an interval last 'us' (exact to one clock cycle)."""
    return max(0, us_to_cycles(us, f_hz) - overhead)


def frame_words(wait_stage, settle_reg, lead_reg, trig_reg, mask):
    if settle_reg >= (1 << 28):
        raise ValueError("settle too long")
    return (1 if wait_stage else 0, lead_reg, trig_reg, (settle_reg & 0x0FFFFFFF) | ((mask & 0xF) << 28))
