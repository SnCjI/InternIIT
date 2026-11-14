# DPSS 4-channel laser driver - Pico 2 main program (MicroPython).
# The PC (supervisor's Python interface) is the master: it sends one text command per line over
# USB CDC serial and receives "OK ...", "ERR ..." or asynchronous "EVT ..." lines.
import sys, select, time
time.sleep(1)   # WOKWI ONLY: wait for USB and for the virtual flash
import config as C
from hw_pico import PicoHW
from dpss_core import Controller


def run():
    hw = PicoHW()                      # all outputs safe before anything else
    ctl = Controller(hw)
    poll = select.poll()
    poll.register(sys.stdin, select.POLLIN)
    buf = ''
    print('EVT BOOT %s' % C.FW_VERSION)
    while True:
        while poll.poll(0):            # read whatever the PC sent, without blocking
            ch = sys.stdin.read(1)
            if ch in ('\n', '\r'):
                if buf:
                    ctl.handle(buf)
                    buf = ''
            elif len(buf) < 120:
                buf += ch
        ctl.tick()
        while ctl.out:
            print(ctl.out.pop(0))
        time.sleep_ms(1)               # idle between loops (CPU sleeps; PIO keeps the timing)


try:
    run()
except Exception as e:                 # any firmware error: lasers off, watchdog stops -> chain opens
    try:
        from machine import Pin
        for i in range(C.N_CH):
            Pin(C.PIN_LASER_ON_BASE + i, Pin.OUT, value=0)
        Pin(C.PIN_CAM_OE_N, Pin.OUT, value=1)
        Pin(C.PIN_STAGE_OE_N, Pin.OUT, value=1)
    finally:
        print('EVT FAULT FIRMWARE_ERROR %r' % e)
        sys.print_exception(e)
