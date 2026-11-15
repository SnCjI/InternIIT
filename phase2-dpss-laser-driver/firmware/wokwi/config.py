# Wokwi demo copy of firmware/config.py: only the two timeouts marked WOKWI DEMO ONLY differ.
# DPSS 4-channel laser driver - Pico 2 (RP2350) firmware configuration
# Pin numbers are GPIO numbers and match the KiCad schematic (controller.kicad_sch).

FW_VERSION = "DPSS4CH-FW 0.1 (Wokwi demo config)"
SYS_CLK_HZ = 2_000_000            # WOKWI DEMO ONLY: PIO clock 2 MHz (real: 150_000_000). Wokwi emulates
                                  # every PIO cycle, so 150 MHz runs at ~0 % speed. Resolution 1 us here.

# ---- GPIO map (Pico 2 pin -> GPIO) ----
PIN_LASER_ON_BASE = 2             # GPIO2..GPIO5 = LASER_ON1..4 (100 k pull-downs on the board)
N_CH = 4
PIN_WDI = 6                       # TPS3823 watchdog input (toggle < 1.6 s)
PIN_FAULT_RST = 7                 # clock of the 74LVC2G74 fault latch (re-arm ENABLE)
PIN_CAM_EXPOS = 10                # camera "Status Expos" (input, via 74LVC1G17)
PIN_CAM_TRIG = 11                 # camera exposure trigger (output, via 74LVC1G125)
PIN_STAGE_IN = 12                 # stage in-position trigger (input, via 74LVC1G17)
PIN_STAGE_OUT = 13                # trigger to the stage controller (output, via 74LVC1G125)
PIN_TEMP_OK = 14                  # temperature-OK from the lab's temperature unit (opto, active high)
PIN_ENABLE = 15                   # hardware safety chain output (read only)
PIN_CAM_OE_N = 16                 # camera trigger buffer enable, active low (pull-up = disabled)
PIN_DAC_SYNC = 17                 # DAC8565 SYNC (SPI0 CSn, driven by software)
PIN_DAC_SCLK = 18                 # SPI0 SCK
PIN_DAC_DIN = 19                  # SPI0 TX
PIN_STAGE_OE_N = 20               # stage trigger buffer enable, active low

# ---- current channel (hardware, see Step 2) ----
DAC_VREF_V = 2.5                  # DAC8565 internal reference -> full scale 2.5 V
GM_MA_PER_V = 160.0               # transconductance of the current sink: I = 160 mA/V * V_DAC
I_HW_CLAMP_MA = 400.0             # hardware clamp (VREF_LIM = 2.5 V); DJ532-40 absolute maximum
I_LIMIT_DEFAULT_MA = 330.0        # per-unit firmware limit until the unit is calibrated
                                  # (datasheet: 40 mW typ. at 330 mA; 50 mW max. reached ~382 mA)
RAMP_MIN_MS = 100                 # requirement E5: 0 -> limit takes at least 100 ms
RAMP_STEP_MS = 2                  # ramp update period

# ---- timing defaults (can be changed with commands) ----
SETTLE_US_DEFAULT = 2000          # stage in-position -> laser ON (mechanical settling)
LEAD_US_DEFAULT = 5000            # laser ON -> camera trigger (>= 5 tau of the DPSS output)
TRIG_US_DEFAULT = 10              # camera trigger pulse width (mode B)
STAGE_PULSE_US_DEFAULT = 100      # pulse to the stage controller
MAX_EMIT_MS_DEFAULT = 20000       # WOKWI DEMO ONLY (real: 2000) - time to press the camera button. laser ON longer than this without end of exposure -> FAULT
HEARTBEAT_MS = 120000             # WOKWI DEMO ONLY (real: 3000) - time to type by hand. no command from the PC for this long while emitting -> FAULT
WDI_PERIOD_MS = 200               # watchdog toggle period (TPS3823-33 timeout 1.6 s typ.)

# ---- camera protection (PCO.panda: 3.3 V LVTTL trigger input) ----
CAM_TRIG_MAX_US = 100             # longest trigger pulse the firmware will generate. The camera
                                  # exposure must last longer than the trigger pulse (the PIO
                                  # waits for Status Expos to rise after the pulse; an exposure
                                  # that ends inside the pulse is caught by EXPOSURE_TIMEOUT)
CAM_MIN_PERIOD_US = 25_000        # shortest time between triggers (panda 4.2 bi full frame ~40 fps)

LIMITS_FILE = "limits.json"       # per-unit current limits stored in the Pico flash
