"""PC-side client for the DPSS 4-channel driver (Pico 2 firmware).

Usage with the real board (USB serial):
    from dpss_client import DPSSDriver
    drv = DPSSDriver.open('COM5')            # Windows; '/dev/ttyACM0' on Linux
    print(drv.idn())
    drv.reset()                              # re-arm the hardware ENABLE latch (key + interlock closed)
    drv.set_current(1, 200.0)                # mA, ramp-limited in the firmware
    drv.arm()

The same class runs against the simulated board (sim/sim_board.SimLink) for the Phase 2 simulation.
Every command returns 'OK ...' or raises DriverError with the firmware's reason; asynchronous
'EVT ...' lines (time stamps, frame done, faults) are collected in .events.
"""
import time


class DriverError(Exception):
    pass


class SerialLink:
    def __init__(self, port, baud=115200, timeout=0.05):
        import serial                         # pip install pyserial
        self.ser = serial.Serial(port, baud, timeout=timeout)

    def write(self, line):
        self.ser.write((line + '\n').encode())

    def readline(self):
        b = self.ser.readline()
        return b.decode(errors='replace').strip() if b else None

    def step(self, dt_us=1000):
        time.sleep(dt_us / 1e6)


class DPSSDriver:
    def __init__(self, link, timeout_s=2.0):
        self.link = link
        self.timeout_s = timeout_s
        self.events = []

    @classmethod
    def open(cls, port):
        return cls(SerialLink(port))

    # ---------------- low level ----------------
    def cmd(self, line):
        self.link.write(line)
        t0 = time.monotonic(); n = 0
        while True:
            r = self.link.readline()
            if r is None:
                self.link.step(1000); n += 1
                if n > self.timeout_s * 1000 and time.monotonic() - t0 > self.timeout_s:
                    raise DriverError('no answer to %r' % line)
                continue
            if r.startswith('EVT'):
                self.events.append(r); continue
            if r.startswith('OK'):
                return r[2:].strip()
            if r.startswith('ERR'):
                raise DriverError('%s -> %s' % (line, r[3:].strip()))

    def poll(self, dt_us=1000):
        """Let time pass (simulation) / read pending lines (hardware); returns new events."""
        self.link.step(dt_us)
        new = []
        while True:
            r = self.link.readline()
            if r is None:
                break
            if r.startswith('EVT'):
                new.append(r)
        self.events += new
        return new

    # ---------------- command set (Table VI of the Rev 2 document + extensions) ----------------
    def idn(self):                return self.cmd('*IDN?')
    def ping(self):               return self.cmd('PING')
    def reset(self):              return self.cmd('RESET')
    def arm(self):                return self.cmd('ARM')
    def disarm(self):             return self.cmd('DISARM')
    def set_current(self, ch, ma): return self.cmd('SET %d %.3f' % (ch, ma))
    def set_limit(self, ch, ma):  return self.cmd('LIMIT %d %.1f' % (ch, ma))
    def on(self, ch):             return self.cmd('ON %d' % ch)
    def off(self, ch='ALL'):      return self.cmd('OFF %s' % ch)
    def mode(self, m):            return self.cmd('MODE %s' % m)          # 'PC' or 'TRIG'
    def settle(self, us):         return self.cmd('SETTLE %d' % us)
    def lead(self, us):           return self.cmd('LEAD %d' % us)
    def trig_width(self, us):     return self.cmd('TRIGW %d' % us)
    def gap(self, us):            return self.cmd('GAP %d' % us)
    def camera_trigger(self, on): return self.cmd('CAMTRIG %s' % ('ON' if on else 'OFF'))
    def position(self, chans, wait=True):
        return self.cmd('POS %s %s' % (','.join(str(c) for c in chans), 'WAIT' if wait else 'NOWAIT'))
    def abort(self):              return self.cmd('ABORT')
    def stage_pulse(self, us=100): return self.cmd('STAGEPULSE %d' % us)

    def status(self):
        s = self.cmd('STATUS')
        return dict(kv.split('=', 1) for kv in s.split())

    def wait_frames(self, n, timeout_s=10.0, step_us=500):
        """Wait until n 'FRAME_DONE' events arrived (keeps the heartbeat alive)."""
        done, t, last_ping = 0, 0, 0
        while done < n:
            for e in self.poll(step_us):
                if 'FRAME_DONE' in e:
                    done += 1
                if 'FAULT' in e:
                    raise DriverError(e)
            t += step_us
            if t - last_ping > 1_000_000:
                self.ping(); last_ping = t
            if t > timeout_s * 1e6:
                raise DriverError('timeout waiting for frames')
        return done
