"""Enable XTTS CUDA after the user has successfully run XTTS_GPU_PROBE.bat."""
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"

def update_env(values: dict[str,str]):
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.is_file() else []
    seen=set(); out=[]
    for line in lines:
        stripped=line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out.append(line); continue
        key=line.split("=",1)[0].strip()
        if key in values:
            out.append(f"{key}={values[key]}"); seen.add(key)
        else: out.append(line)
    for key,val in values.items():
        if key not in seen: out.append(f"{key}={val}")
    ENV.write_text("\n".join(out)+"\n",encoding="utf-8")

def main():
    try:
        import torch
        if not torch.cuda.is_available():
            print("[FAIL] CUDA n'est pas disponible dans ce venv.")
            return 2
        name=torch.cuda.get_device_name(torch.cuda.current_device())
    except Exception as exc:
        print(f"[FAIL] PyTorch/CUDA: {exc}")
        return 3
    update_env({"XTTS_DEVICE":"cuda","XTTS_ALLOW_CUDA":"true","XTTS_PREVIEW_FAST":"true"})
    print(f"[PASS] XTTS GPU activé : {name}")
    print(f"[OK] Configuration écrite dans : {ENV}")
    print("     XTTS_DEVICE=cuda")
    print("     XTTS_ALLOW_CUDA=true")
    print("Redémarre AURA / XTTS Voice Lab pour appliquer la configuration.")
    return 0
if __name__ == '__main__': raise SystemExit(main())
