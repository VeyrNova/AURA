from __future__ import annotations
import json, os, sys, urllib.request
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1];session=root.parent/'runtime'/'rc4_2_session.json'
    if not session.is_file():print('[INFO] Aucune session AURA RC4.2 active.');return 0
    try:d=json.loads(session.read_text(encoding='utf-8'));port=int(d['port']);token=str(d['token']);url=f'http://127.0.0.1:{port}/api/shutdown?token={token}';req=urllib.request.Request(url,data=b'stop',method='POST');urllib.request.urlopen(req,timeout=3).read();print('[OK] Arret propre demande au Runtime AURA RC4.2.');return 0
    except Exception as e:print('[ERREUR] Session RC4.2 inaccessible:',e);return 1
if __name__=='__main__':raise SystemExit(main())
