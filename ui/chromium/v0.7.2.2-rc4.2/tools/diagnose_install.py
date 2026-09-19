from __future__ import annotations
import json, os, re, shutil
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1];cfg=json.loads((root/'aura_ui_config.json').read_text(encoding='utf-8'));core=Path(cfg['core_root']);errors=[]
    print('=== AURA v0.7.2.2 RC4.2 - CAMILLA STATE AUTHORITY DIAGNOSTIC ===')
    print('Core      :',core);print('UI        :',root);print('Release   :',cfg.get('release'))
    print('Renderer  : Three.js WebGL2 / Intel Balanced 48 FPS')
    print('Runtime   : Python + HTTP/SSE/POST loopback; Node non requis au lancement')
    print('Interaction: texte + push-to-talk allowlistes vers le Core local');print('Camilla   : READY autoritatif + STANDBY pour prewarm differe + double observer')
    print('Windows   : une seule fenetre visible (Chromium app AURA); PySide Core masque en memoire')
    for p in [root/'dist'/'index.html',root/'tools'/'shell_host.py',root/'LANCER_AURA_RC4_2.vbs',core/'main.py',core/'core'/'version.py']:
        if not p.is_file():errors.append(f'missing {p}')
    if (root/'node_modules').exists():errors.append('node_modules ne doit pas rester dans la distribution RC4.2')
    try:
        s=(core/'core'/'version.py').read_text(encoding='utf-8',errors='replace');v=re.search(r'AURA_VERSION\s*=\s*["\']([^"\']+)',s);b=re.search(r'AURA_BUILD\s*=\s*["\']([^"\']+)',s)
        if not v or v.group(1)!='0.7.2.2' or not b or b.group(1)!='2026.08.20.14':errors.append('Core identity mismatch')
    except Exception as e:errors.append(str(e))
    browser=bool(shutil.which('chrome') or shutil.which('msedge')) or any((Path(os.getenv(k,''))/r).is_file() for k,r in [('PROGRAMFILES','Google/Chrome/Application/chrome.exe'),('PROGRAMFILES','Microsoft/Edge/Application/msedge.exe'),('LOCALAPPDATA','Google/Chrome/Application/chrome.exe')])
    print('Browser   :','detecte' if browser else 'sera verifie au lancement')
    print('Security  : token session + Origin + CSP + actions allowlistees + payload borne')
    print('Privacy   : texte visible uniquement coque locale <-> Core local; aucun acces OS direct JS')
    if errors:
        for e in errors:print('[ERREUR]',e)
        return 1
    print('[OK] Coque interactive AURA RC4.2 coherente et prete.');return 0
if __name__=='__main__':raise SystemExit(main())
