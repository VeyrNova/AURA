from __future__ import annotations
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; ENV=ROOT/'.env'
def main():
    lines=ENV.read_text(encoding='utf-8').splitlines() if ENV.is_file() else []
    vals={'XTTS_DEVICE':'cpu','XTTS_ALLOW_CUDA':'false'}; seen=set(); out=[]
    for line in lines:
        if '=' in line and not line.lstrip().startswith('#'):
            key=line.split('=',1)[0].strip()
            if key in vals: out.append(f'{key}={vals[key]}'); seen.add(key); continue
        out.append(line)
    for k,v in vals.items():
        if k not in seen: out.append(f'{k}={v}')
    ENV.write_text('\n'.join(out)+'\n',encoding='utf-8')
    print('[PASS] XTTS repassera sur CPU au prochain démarrage.')
if __name__=='__main__': main()
