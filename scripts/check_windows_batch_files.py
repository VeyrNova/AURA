from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
files = sorted(p.name for p in ROOT.glob('*.bat'))
ok = True
print('=== AURA v0.7.0.14 - WINDOWS BATCH CHECK ===')
for name in files:
    p = ROOT / name
    data = p.read_bytes()
    ascii_ok = all(b < 128 for b in data)
    crlf = data.count(b'\r\n')
    lone_lf = data.count(b'\n') - crlf
    good = ascii_ok and crlf > 0 and lone_lf == 0
    print(f'{name:36} ASCII={ascii_ok} CRLF={crlf} lone_LF={lone_lf} -> {"PASS" if good else "FAIL"}')
    ok &= good
print('[PASS] Windows batch files are CMD-safe.' if ok else '[FAIL] One or more batch files are not CMD-safe.')
sys.exit(0 if ok else 1)
