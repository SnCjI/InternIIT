# Minimal CPython stand-in for MicroPython's 'rp2' module: assembles @asm_pio programs into the
# real 16-bit PIO opcodes (RP2040/RP2350 datasheet, PIO instruction set) so they can be run in a
# cycle-accurate emulator (pioemu). Only the instructions used by the firmware are implemented.
import sys, types


class PIO:
    OUT_LOW, OUT_HIGH, IN_LOW, IN_HIGH = 2, 3, 0, 1
    SHIFT_LEFT, SHIFT_RIGHT = 0, 1
    JOIN_NONE, JOIN_TX, JOIN_RX = 0, 1, 2
    IRQ_SM0 = 0x100


class _Op:
    def __init__(self, prog, kind, args):
        self.prog, self.kind, self.args = prog, kind, args
        self.side_val, self.delay = None, 0

    def side(self, v):
        self.side_val = v
        return self

    def __getitem__(self, d):
        self.delay = d
        return self


class Program:
    def __init__(self, name, ops, labels, wrap_target, wrap, kw):
        self.name, self.kw = name, kw
        self.labels = labels
        self.wrap_target = wrap_target
        self.wrap = wrap if wrap is not None else len(ops) - 1
        ss = kw.get('sideset_init')
        self.sideset_count = 0 if ss is None else (len(ss) if isinstance(ss, tuple) else 1)
        self.opcodes = [self._encode(o) for o in ops]

    def _ds(self, o):
        n = self.sideset_count
        if n == 0:
            return o.delay & 0x1F
        sv = o.side_val if o.side_val is not None else 0
        # MicroPython encodes side-set 0 when .side() is omitted (non-optional side-set)
        return ((sv & ((1 << n) - 1)) << (5 - n)) | (o.delay & ((1 << (5 - n)) - 1))

    def _encode(self, o):
        k, a = o.kind, o.args
        ds = self._ds(o) << 8
        if k == 'jmp':
            if len(a) == 1:
                cond, lab = 0, a[0]
            else:
                cond, lab = a
            return 0x0000 | ds | (cond << 5) | self.labels[lab]
        if k == 'wait':
            pol, src, idx = a
            return 0x2000 | ds | (pol << 7) | (src << 5) | idx
        if k == 'in':
            src, n = a
            return 0x4000 | ds | (src << 5) | (n & 31)
        if k == 'out':
            dst, n = a
            return 0x6000 | ds | (dst << 5) | (n & 31)
        if k == 'push':
            iffull, block = a
            return 0x8000 | ds | (iffull << 6) | (block << 5)
        if k == 'pull':
            ifempty, block = a
            return 0x8080 | ds | (ifempty << 6) | (block << 5)
        if k == 'mov':
            dst, src = a
            op = 0
            if isinstance(src, tuple):
                op, src = src
            return 0xA000 | ds | (dst << 5) | (op << 3) | src
        if k == 'set':
            dst, val = a
            return 0xE000 | ds | (dst << 5) | (val & 31)
        if k == 'nop':
            return 0xA042 | ds          # mov y, y
        raise NotImplementedError(k)


# operand codes
class _Src:  # names used inside programs
    pass


def _dsl():
    ops, labels, state = [], {}, {'wt': 0, 'w': None}
    def add(kind, *args):
        o = _Op(None, kind, args); ops.append(o); return o
    ns = dict(
        # jmp conditions
        not_x=1, x_dec=2, not_y=3, y_dec=4, x_not_y=5, pin=6, not_osre=7,
        # mov/in/out/set operands (context dependent numbers are resolved below)
        pins=0, x=1, y=2, null=3, pindirs=4, pc=5, isr=6, osr=7, status=5,
        gpio=0, irq=2, block=1, noblock=0, iffull=1, ifempty=1,
    )
    ns['invert'] = lambda s: (1, s)
    ns['reverse'] = lambda s: (2, s)
    ns['label'] = lambda name: labels.__setitem__(name, len(ops))
    ns['wrap_target'] = lambda: state.__setitem__('wt', len(ops))
    ns['wrap'] = lambda: state.__setitem__('w', len(ops) - 1)
    def jmp(*a):
        return add('jmp', *a)
    def wait(pol, src, idx):
        # 'pin' as wait source is 1 (jmp-cond 'pin' constant is 6, so remap)
        return add('wait', pol, 1 if src == 6 else src, idx)
    def in_(src, n): return add('in', src, n)
    def out(dst, n):
        # out destinations: pins 0, x 1, y 2, null 3, pindirs 4, pc 5, isr 6, exec 7
        return add('out', dst, n)
    def push(*a):
        iffull = 1 if ('iffull' in a) else 0
        block = 0 if (0 in a and len(a) and a[-1] == 0) else 1
        return add('push', 0, block)
    def pull(*a):
        block = 0 if (len(a) and a[-1] == 0) else 1
        return add('pull', 0, block)
    def mov(dst, src): return add('mov', dst, src)
    def set_(dst, val): return add('set', dst, val)
    def nop(): return add('nop')
    ns.update(jmp=jmp, wait=wait, in_=in_, out=out, push=push, pull=pull, mov=mov, set=set_, nop=nop)
    return ns, ops, labels, state


def asm_pio(**kw):
    def deco(fn):
        ns, ops, labels, state = _dsl()
        g = dict(fn.__globals__); g.update(ns)
        types.FunctionType(fn.__code__, g)()
        return Program(fn.__name__, ops, labels, state['wt'], state['w'], kw)
    return deco


class StateMachine:          # placeholder so that firmware modules import under CPython
    def __init__(self, *a, **k): pass


def install():
    m = types.ModuleType('rp2')
    m.PIO, m.asm_pio, m.StateMachine = PIO, asm_pio, StateMachine
    sys.modules['rp2'] = m
    return m
