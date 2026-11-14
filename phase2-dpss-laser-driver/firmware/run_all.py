# Runs the complete Step 5 verification and writes everything to sim/results/
import subprocess, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, 'sim', 'results'); os.makedirs(R, exist_ok=True)
steps = [('PIO opcodes vs independent assembler', [sys.executable, 'sim/check_asm.py']),
         ('Firmware unit tests (requirements)', [sys.executable, '-m', 'pytest', '-v', 'sim/test_firmware.py']),
         ('Cycle-accurate PIO timing', [sys.executable, 'sim/pio_timing.py']),
         ('Snake scan + LEAD justification', [sys.executable, 'sim/scan_sim.py'])]
report = []
for name, cmd in steps:
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    report.append('=' * 70 + '\n' + name + '   [exit %d]\n' % r.returncode + '=' * 70 + '\n' + r.stdout + r.stderr)
    print(name, 'OK' if r.returncode == 0 else 'FAILED')
open(os.path.join(R, 'verification_report.txt'), 'w').write('\n'.join(report))
