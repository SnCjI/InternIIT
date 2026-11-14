# Cross-check: our DSL assembler vs Adafruit's independent text assembler (adafruit_pioasm)
import sys, os
sys.path[:0] = [os.path.dirname(__file__), os.path.join(os.path.dirname(__file__), '../firmware')]
import fake_rp2; fake_rp2.install()
import dpss_pio, adafruit_pioasm
TXT = {
'frame_seq': """
.side_set 1
pull block side 0
mov x, osr side 0
pull block side 0
mov y, osr side 0
pull block side 0
mov isr, osr side 0
pull block side 0
jmp !x go side 0
wait 0 gpio 12 side 0
wait 1 gpio 12 side 0
go:
out x, 28 side 0
settle:
jmp x-- settle side 0
out pins, 4 side 0
lead:
jmp y-- lead side 0
mov x, isr side 1
trig:
jmp x-- trig side 1
wait 1 gpio 10 side 0
wait 0 gpio 10 side 0
mov pins, null side 0
push noblock side 0
""",
'edge_ts': """
mov x, ~null
low:
jmp pin rise
jmp x-- low
rise:
mov isr, x
push noblock
high:
jmp pin h2
jmp fall
h2:
jmp x-- high
fall:
mov isr, x
push noblock
jmp x-- low
""",
'pulse': """
pull block
mov x, osr
set pins, 1
w:
jmp x-- w
set pins, 0
"""}
ok = True
for name, txt in TXT.items():
    mine = getattr(dpss_pio, name).opcodes
    ref = list(adafruit_pioasm.assemble(txt))
    same = mine == ref
    ok &= same
    print('%-10s %2d instr  match=%s' % (name, len(mine), same))
    if not same:
        for i, (a, b) in enumerate(zip(mine, ref)):
            if a != b: print('   #%d mine %04x ref %04x' % (i, a, b))
print('TOTAL PIO0 instructions (frame_seq + edge_ts):', len(dpss_pio.frame_seq.opcodes) + len(dpss_pio.edge_ts.opcodes), '/ 32')
print('ALL MATCH' if ok else 'MISMATCH')
