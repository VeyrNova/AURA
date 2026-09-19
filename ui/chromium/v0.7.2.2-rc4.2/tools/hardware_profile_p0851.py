# AURA P0.8.5.1.2 — Unified Hardware Profile + System State telemetry foundation
# Read-only Windows hardware inventory for the authenticated local shell.
# No settings are modified. No network request is made.
from __future__ import annotations

import ctypes
import datetime as _dt
import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

SCHEMA = "aura.hardware-profile.v1"
CACHE_SECONDS = 8.0
_CACHE = {"at": 0.0, "data": None}


def _safe(value, limit=300):
    return " ".join(str(value or "").split())[:limit]


def _gib(value):
    try:
        return round(float(value) / (1024 ** 3), 2)
    except Exception:
        return None


def _memory_status():
    # Prefer the same lightweight psutil family already used by AURA when available.
    try:
        import psutil  # type: ignore
        m = psutil.virtual_memory()
        return {
            "total_bytes": int(m.total),
            "available_bytes": int(m.available),
            "total_gib": _gib(m.total),
            "available_gib": _gib(m.available),
            "used_percent": round(float(m.percent), 1),
            "source": "psutil",
        }
    except Exception:
        pass
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        s = MEMORYSTATUSEX(); s.dwLength = ctypes.sizeof(s)
        try:
            ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
            if ok:
                return {
                    "total_bytes": int(s.ullTotalPhys),
                    "available_bytes": int(s.ullAvailPhys),
                    "total_gib": _gib(s.ullTotalPhys),
                    "available_gib": _gib(s.ullAvailPhys),
                    "used_percent": float(s.dwMemoryLoad),
                    "source": "GlobalMemoryStatusEx",
                }
        except Exception:
            pass
    # Portable fallback for diagnostics/simulation only.
    try:
        pages = int(os.sysconf("SC_PHYS_PAGES")); page = int(os.sysconf("SC_PAGE_SIZE")); total = pages * page
        avpages = int(os.sysconf("SC_AVPHYS_PAGES")); avail = avpages * page
        return {"total_bytes": total, "available_bytes": avail, "total_gib": _gib(total), "available_gib": _gib(avail), "used_percent": round((1-avail/total)*100,1), "source":"sysconf"}
    except Exception:
        return {"total_bytes": None, "available_bytes": None, "total_gib": None, "available_gib": None, "used_percent": None, "source": "unavailable"}


def _cpu_model():
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                value, _ = winreg.QueryValueEx(k, "ProcessorNameString")
                if value:
                    return _safe(value, 180), "winreg"
        except Exception:
            pass
    value = platform.processor() or platform.machine() or "CPU inconnu"
    return _safe(value, 180), "platform"


def _cpu_info():
    model, source = _cpu_model()
    logical = os.cpu_count() or 1
    physical = None
    try:
        import psutil  # type: ignore
        physical = psutil.cpu_count(logical=False)
    except Exception:
        pass
    return {
        "model": model,
        "logical_cores": int(logical),
        "physical_cores": int(physical) if physical else None,
        "architecture": platform.machine() or "unknown",
        "source": source,
    }


def _nvidia_rows():
    exe = shutil.which("nvidia-smi")
    if not exe and os.name == "nt":
        candidates = [
            Path(os.environ.get("ProgramW6432", r"C:\\Program Files")) / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe",
            Path(os.environ.get("SystemRoot", r"C:\\Windows")) / "System32" / "nvidia-smi.exe",
        ]
        exe = next((str(p) for p in candidates if p.is_file()), None)
    if not exe:
        return []
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    queries = [
        ("name,memory.total,memory.used,driver_version,temperature.gpu,utilization.gpu", 6),
        ("name,memory.total,memory.used,driver_version", 4),
    ]
    for fields, minimum in queries:
        cmd = [exe, f"--query-gpu={fields}", "--format=csv,noheader,nounits"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=2.8, creationflags=flags, check=False)
            if r.returncode != 0:
                continue
            out=[]
            for line in (r.stdout or "").splitlines():
                parts=[x.strip() for x in line.split(",")]
                if len(parts) < minimum:
                    continue
                try: total=int(float(parts[1])); used=int(float(parts[2]))
                except Exception: total=used=None
                row={"name":_safe(parts[0],180),"dedicated_vram_mib":total,"used_vram_mib":used,"free_vram_mib":max(0,total-used) if total is not None and used is not None else None,"driver":_safe(parts[3],80),"source":"nvidia-smi"}
                if len(parts) >= 6:
                    try: row["temperature_c"]=round(float(parts[4]),1)
                    except Exception: row["temperature_c"]=None
                    try: row["utilization_percent"]=round(float(parts[5]),1)
                    except Exception: row["utilization_percent"]=None
                out.append(row)
            if out:
                return out
        except Exception:
            continue
    return []

def _pick_compute_gpu(name_hint=""):
    hint=_safe(name_hint,180).lower(); rows=_nvidia_rows()
    if rows:
        if hint:
            for row in rows:
                n=row.get("name","").lower()
                tokens=[x for x in re_split_gpu(hint) if len(x)>2]
                if hint in n or n in hint or (tokens and sum(t in n for t in tokens)>=max(1,len(tokens)//2)):
                    return row
        return rows[0]
    return {"name":_safe(name_hint,180) or "Non détecté", "dedicated_vram_mib":None,"used_vram_mib":None,"free_vram_mib":None,"driver":"","source":"bridge-runtime" if name_hint else "unavailable"}


def re_split_gpu(text):
    cur=""; out=[]
    for ch in text.lower():
        if ch.isalnum(): cur+=ch
        elif cur: out.append(cur); cur=""
    if cur: out.append(cur)
    return out


def _audio_info(rt=None):
    runtime_state = "ready" if bool(getattr(rt,"voice_ready",False)) else "warming" if bool(getattr(rt,"voice_warming",False)) else "standby"
    base={"runtime_state":runtime_state,"default_input":"","default_output":"","input_devices":0,"output_devices":0,"source":"runtime"}
    try:
        import sounddevice as sd  # type: ignore
        devices=sd.query_devices(); default=sd.default.device
        try: di=int(default[0])
        except Exception: di=-1
        try: do=int(default[1])
        except Exception: do=-1
        inputs=sum(1 for d in devices if int(d.get("max_input_channels",0) or 0)>0)
        outputs=sum(1 for d in devices if int(d.get("max_output_channels",0) or 0)>0)
        if 0 <= di < len(devices): base["default_input"]=_safe(devices[di].get("name",""),160)
        if 0 <= do < len(devices): base["default_output"]=_safe(devices[do].get("name",""),160)
        base.update({"input_devices":inputs,"output_devices":outputs,"source":"sounddevice"})
    except Exception:
        pass
    return base


def _display_name(rt=None):
    return _safe(getattr(rt,"p0851_display_gpu","") or "",180)


def _compute_hint(rt=None):
    return _safe(getattr(rt,"p0851_compute_gpu","") or "",180)


def _topology(display, compute):
    dl=(display or "").lower(); cl=(compute or "").lower()
    if display and compute and display.lower()!=compute.lower():
        if "intel" in dl and ("nvidia" in cl or "geforce" in cl): return "intel-display+nvidia-compute", True
        return "separate-display-compute", True
    if compute: return "single-compute-adapter", False
    if display: return "display-only", False
    return "unknown", False


def select_profile(snapshot):
    """Pure deterministic profile selector. It recommends; it never applies settings."""
    cpu=snapshot.get("cpu") or {}; mem=snapshot.get("memory") or {}; gpu=snapshot.get("compute_gpu") or {}
    cores=int(cpu.get("logical_cores") or 0); ram=float(mem.get("total_gib") or 0); vram_mib=float(gpu.get("dedicated_vram_mib") or 0); vram=vram_mib/1024.0
    reasons=[]
    if cores: reasons.append(f"{cores} threads CPU")
    if ram: reasons.append(f"{ram:.0f} Gio RAM")
    if vram: reasons.append(f"{vram:.1f} Gio VRAM dédiée")
    if ram>=24 and cores>=12 and vram>=8:
        pid,label="performance","PERFORMANCE"
        visual="Qualité élevée · budget 60–72 FPS selon écran"
        voice="XTTS CUDA prioritaire sous garde Resource Guardian"
        local_ai="Modèles locaux moyens autorisables selon pression mémoire"
    elif ram>=12 and cores>=6 and vram>=4:
        pid,label="balanced","BALANCED"
        visual="Qualité équilibrée · budget 48–60 FPS"
        voice="XTTS CUDA conditionnel + fallback Piper"
        local_ai="Hybride cloud/local · modèles locaux compacts"
    else:
        pid,label="efficient","EFFICIENT"
        visual="Qualité allégée · budget 30–45 FPS"
        voice="Piper/local léger prioritaire · XTTS seulement si éligible"
        local_ai="Cloud/hybride prioritaire · petit modèle local si disponible"
    return {
        "id":pid,"label":label,"reasons":reasons,
        "recommendations":{"visual":visual,"voice":voice,"local_ai":local_ai},
        "applies_changes":False,
        "selection":"deterministic-static-capacity-v1",
    }



def _cpu_load_percent():
    """Short read-only sample used only when the Hardware Profile is requested."""
    try:
        import psutil  # type: ignore
        return round(float(psutil.cpu_percent(interval=0.08)), 1)
    except Exception:
        return None


def _storage_info():
    root = (os.environ.get("SystemDrive", "C:") + "\\") if os.name == "nt" else "/"
    try:
        import psutil  # type: ignore
        d=psutil.disk_usage(root)
        return {"root":root,"total_bytes":int(d.total),"used_bytes":int(d.used),"free_bytes":int(d.free),"total_gb":round(d.total/1_000_000_000,1),"used_gb":round(d.used/1_000_000_000,1),"used_percent":round(float(d.percent),1),"source":"psutil"}
    except Exception:
        try:
            d=shutil.disk_usage(root)
            used=d.total-d.free
            return {"root":root,"total_bytes":int(d.total),"used_bytes":int(used),"free_bytes":int(d.free),"total_gb":round(d.total/1_000_000_000,1),"used_gb":round(used/1_000_000_000,1),"used_percent":round((used/d.total)*100,1) if d.total else None,"source":"shutil"}
        except Exception:
            return {"root":root,"total_bytes":None,"used_bytes":None,"free_bytes":None,"total_gb":None,"used_gb":None,"used_percent":None,"source":"unavailable"}

def _network_info(sample_seconds=0.12):
    try:
        import psutil  # type: ignore
        a=psutil.net_io_counters(); t0=time.monotonic(); time.sleep(max(0.05,min(0.25,float(sample_seconds)))); b=psutil.net_io_counters(); dt=max(0.001,time.monotonic()-t0)
        down=max(0,int(b.bytes_recv)-int(a.bytes_recv))*8.0/dt/1_000_000.0
        up=max(0,int(b.bytes_sent)-int(a.bytes_sent))*8.0/dt/1_000_000.0
        return {"download_mbps":round(down,2),"upload_mbps":round(up,2),"source":"psutil-sample"}
    except Exception:
        return {"download_mbps":None,"upload_mbps":None,"source":"unavailable"}

def _system_state(memory, compute_gpu):
    storage=_storage_info(); network=_network_info()
    used=compute_gpu.get("used_vram_mib") if isinstance(compute_gpu,dict) else None
    total=compute_gpu.get("dedicated_vram_mib") if isinstance(compute_gpu,dict) else None
    return {
        "cpu_percent":_cpu_load_percent(),
        "ram_used_gib":round(float(memory.get("total_gib") or 0)-float(memory.get("available_gib") or 0),2) if memory.get("total_gib") is not None and memory.get("available_gib") is not None else None,
        "ram_total_gib":memory.get("total_gib"),
        "ram_percent":memory.get("used_percent"),
        "vram_used_gib":round(float(used)/1024.0,2) if used is not None else None,
        "vram_total_gib":round(float(total)/1024.0,2) if total is not None else None,
        "vram_percent":round(float(used)/float(total)*100.0,1) if total and used is not None else None,
        "gpu_util_percent":compute_gpu.get("utilization_percent") if isinstance(compute_gpu,dict) else None,
        "temperature_c":compute_gpu.get("temperature_c") if isinstance(compute_gpu,dict) else None,
        "temperature_source":"compute-gpu" if isinstance(compute_gpu,dict) and compute_gpu.get("temperature_c") is not None else "unavailable",
        "storage":storage,
        "network":network,
        "source":"unified-hardware-profile",
    }

def _current_load(memory, compute_gpu):
    ram = memory.get("used_percent") if isinstance(memory, dict) else None
    used = compute_gpu.get("used_vram_mib") if isinstance(compute_gpu, dict) else None
    total = compute_gpu.get("dedicated_vram_mib") if isinstance(compute_gpu, dict) else None
    try:
        vram = round((float(used) / float(total)) * 100.0, 1) if total and used is not None else None
    except Exception:
        vram = None
    return {
        "cpu_percent": _cpu_load_percent(),
        "ram_percent": round(float(ram), 1) if ram is not None else None,
        "vram_percent": vram,
        "source": "profile-snapshot-fallback",
    }

def build_hardware_profile(rt=None, force=False):
    now=time.monotonic()
    if not force and _CACHE.get("data") is not None and now-float(_CACHE.get("at") or 0)<CACHE_SECONDS:
        return json.loads(json.dumps(_CACHE["data"]))
    display=_display_name(rt); compute_hint=_compute_hint(rt)
    snap={
        "cpu":_cpu_info(),
        "memory":_memory_status(),
        "display_gpu":{"name":display or "Détection UI/bridge en attente","source":"bridge-runtime" if display else "pending"},
        "compute_gpu":_pick_compute_gpu(compute_hint),
        "audio":_audio_info(rt),
    }
    topology,separated=_topology(display,snap["compute_gpu"].get("name","") if snap.get("compute_gpu") else "")
    profile=select_profile(snap)
    data={
        "ok":True,"schema":SCHEMA,"generated_at":_dt.datetime.now().astimezone().isoformat(),
        "read_only":True,"applies_changes":False,"inventory":snap,
        "topology":{"kind":topology,"display_compute_separated":separated},
        "current_load":_current_load(snap["memory"],snap["compute_gpu"]),
        "system_state":_system_state(snap["memory"],snap["compute_gpu"]),
        "recommended_profile":profile,
        "contract":{"owner":"python-core-bridge","ui":"consumer-only","network":False,"settings_changed":False},
    }
    _CACHE.update({"at":now,"data":data})
    return json.loads(json.dumps(data))


def self_test():
    cases=[
      ({"cpu":{"logical_cores":4},"memory":{"total_gib":8},"compute_gpu":{"dedicated_vram_mib":0}},"efficient"),
      ({"cpu":{"logical_cores":8},"memory":{"total_gib":16},"compute_gpu":{"dedicated_vram_mib":4096}},"balanced"),
      ({"cpu":{"logical_cores":16},"memory":{"total_gib":32},"compute_gpu":{"dedicated_vram_mib":12288}},"performance"),
    ]
    return all(select_profile(s)["id"]==expected for s,expected in cases)

if __name__ == "__main__":
    print(json.dumps({"self_test":self_test(),"sample":build_hardware_profile(force=True)},ensure_ascii=False,indent=2))
