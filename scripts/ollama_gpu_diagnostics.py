from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from runtime.ollama_gpu_diagnostics import collect_ollama_gpu_diagnostic, format_ollama_gpu_diagnostic

def main():
    d=collect_ollama_gpu_diagnostic()
    print('=== AURA OLLAMA GPU DIAGNOSTICS ===')
    print(format_ollama_gpu_diagnostic(d))
    out=ROOT/'logs'/'ollama_gpu_diagnostic.json'
    try:
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(d.to_dict(),ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'\nRapport: {out}')
    except Exception as e:
        print(f'Rapport non écrit: {e}')
    return 0 if d.ollama_on_nvidia else 2
if __name__=='__main__': raise SystemExit(main())
