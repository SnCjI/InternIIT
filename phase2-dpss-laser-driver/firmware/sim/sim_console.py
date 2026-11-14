# Interactive console: type the same commands the PC would send to the real board, and act on the
# simulated hardware (interlock, temperature, stage, camera). The firmware core runs unchanged.
#   python sim/sim_console.py
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, '../firmware')]
from sim_board import SimLink

HELP = """Firmware commands (as from the PC): *IDN?  STATUS  RESET  SET 1 200  ARM  ON 1  OFF ALL
  MODE TRIG  SETTLE 2000  LEAD 5000  GAP 30000  CAMTRIG ON  POS 1,2,3,4  DISARM  LIMIT 1 350 ...
Simulated hardware (start with !):
  !wait <ms>        let time pass (ramps, frames, heartbeat)
  !stage            the stage arrives (BNC in-position edge in 5 ms)
  !interlock open|close     !key off|on     !temp bad|ok
  !camera on|off    camera answers the trigger (mode B) or not
  !lasers           show LASER_ON lines and laser currents
  !help  !quit
Note: the firmware expects a command at least every 3 s while armed (heartbeat), like the real PC."""


def show_lasers(hw):
    return '  '.join('L%d %s %6.1f mA' % (ch + 1, 'ON ' if (hw.laser_mask() >> ch) & 1 and hw.latch else 'off',
                                         hw.current_ma(ch)) for ch in range(4)) + '   ENABLE=%d' % hw.latch


def main():
    link = SimLink(); hw = link.hw
    link.step(1000)
    print(HELP)
    while True:
        for r in link.rx:
            print('   <- ' + r)
        link.rx = []
        try:
            line = input('t=%.3f s > ' % (hw.t_us / 1e6)).strip()
        except EOFError:
            break
        if not line:
            continue
        p = line.split()
        if p[0].startswith('!'):
            c = p[0][1:].lower(); a = p[1].lower() if len(p) > 1 else ''
            if c == 'quit': break
            elif c == 'help': print(HELP)
            elif c == 'wait':
                ms = int(a or 100)
                for _ in range(ms):
                    link.step(1000)
            elif c == 'stage':
                hw.stage_arrive(hw.t_us + 5000); print('   stage edge scheduled')
            elif c == 'interlock': hw.interlock = (a != 'open')
            elif c == 'key': hw.key = (a != 'off')
            elif c == 'temp': hw.temp = (a != 'bad')
            elif c == 'camera': hw.cam_responds = (a != 'off')
            elif c == 'lasers': pass
            else: print('   unknown, type !help')
            link.step(1000)
            print('   ' + show_lasers(hw))
        else:
            link.write(line)
            link.step(1000)


if __name__ == '__main__':
    main()
