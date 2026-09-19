from __future__ import annotations
import json, os
from pathlib import Path

SUPPORTED=("fr-FR","en-US")

def config_path():
    base=os.environ.get("APPDATA") or str(Path.home()/"AppData"/"Roaming")
    return Path(base)/"AURA"/"config"/"locale.json"

def normalize(value):
    raw=str(value or "").strip().replace("_","-").lower()
    return "en-US" if raw.startswith("en") else "fr-FR"

def load_locale(default="fr-FR"):
    p=config_path()
    if not p.is_file():
        return normalize(default)
    try:
        return normalize(json.loads(p.read_text(encoding="utf-8")).get("locale"))
    except Exception:
        return normalize(default)

def save_locale(value):
    loc=normalize(value)
    p=config_path(); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({
        "schema":"aura.locale.v1",
        "locale":loc,
        "ui_language":loc,
        "conversation_language":loc
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(tmp,p)
    return loc

def runtime_environment(value=None):
    loc=normalize(value or load_locale())
    en=loc=="en-US"
    return {
        "AURA_LOCALE":loc,
        "STT_LANGUAGE":"en" if en else "fr",
        "AURA_TTS_LANGUAGE":"en" if en else "fr",
        "AURA_RESPONSE_LANGUAGE":"English" if en else "French",
    }

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--get",action="store_true")
    ap.add_argument("--set",choices=SUPPORTED)
    ap.add_argument("--env",action="store_true")
    a=ap.parse_args()
    if a.set: save_locale(a.set)
    loc=load_locale()
    if a.env:
        for k,v in runtime_environment(loc).items(): print(f"{k}={v}")
    else:
        print(loc)
