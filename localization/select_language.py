from __future__ import annotations
import argparse, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from localization.aura_locale import config_path, load_locale, save_locale

def choose(force=False):
    if config_path().is_file() and not force:
        return load_locale()
    try:
        import tkinter as tk
    except Exception:
        return save_locale("fr-FR")
    result={"locale":None}
    root=tk.Tk()
    root.title("AURA â€” Language / Langue")
    root.geometry("560x330"); root.resizable(False,False); root.configure(bg="#07111f")
    try: root.attributes("-topmost",True)
    except Exception: pass
    tk.Label(root,text="AURA",fg="white",bg="#07111f",font=("Segoe UI",26,"bold")).pack(pady=(28,6))
    tk.Label(root,text="Choisissez votre langue / Choose your language",fg="#c9d8ef",bg="#07111f",font=("Segoe UI",12)).pack(pady=(0,24))
    box=tk.Frame(root,bg="#07111f"); box.pack()
    def setloc(v):
        result["locale"]=save_locale(v); root.destroy()
    common=dict(width=20,height=3,font=("Segoe UI",12,"bold"),relief="flat",cursor="hand2")
    tk.Button(box,text="FR  FranÃ§ais",command=lambda:setloc("fr-FR"),bg="#17345c",fg="white",activebackground="#21477d",activeforeground="white",**common).grid(row=0,column=0,padx=12)
    tk.Button(box,text="EN  English",command=lambda:setloc("en-US"),bg="#17345c",fg="white",activebackground="#21477d",activeforeground="white",**common).grid(row=0,column=1,padx=12)
    tk.Label(root,text="Vous pourrez modifier ce choix plus tard.\nYou can change this later.",fg="#7f96b5",bg="#07111f",font=("Segoe UI",9)).pack(pady=(24,0))
    root.protocol("WM_DELETE_WINDOW",lambda:(save_locale(load_locale()),root.destroy()))
    root.mainloop()
    return result["locale"] or load_locale()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ensure",action="store_true")
    ap.add_argument("--change",action="store_true")
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:
        assert load_locale() in {"fr-FR","en-US"}
        print("[PASS] locale selector self-test")
        return 0
    print(choose(force=a.change))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
