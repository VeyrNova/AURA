from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import persist_local_env_value, valid_cloud_api_token


def _clean_key(value: str) -> str:
    key = str(value or "").strip().strip('"').strip("'")
    # Avoid accidental copy of a full shell assignment.
    if "=" in key and key.upper().startswith("GEMINI_API_KEY="):
        key = key.split("=", 1)[1].strip().strip('"').strip("'")
    return key


def _clipboard_key() -> str:
    """Read the Windows clipboard without printing its contents."""
    if os.name != "nt":
        return ""
    commands = [
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-Clipboard -Raw"],
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", "Get-Clipboard -Raw"],
    ]
    for command in commands:
        try:
            proc = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                check=False,
            )
            if proc.returncode == 0:
                key = _clean_key(proc.stdout)
                if key:
                    return key
        except Exception:
            continue
    return ""


def _gui_key() -> str:
    """Secure GUI entry so Ctrl+V works even when the console blocks paste."""
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception:
        return ""

    result = {"key": ""}
    root = tk.Tk()
    root.title("AURA — Configuration Gemini")
    root.geometry("570x260")
    root.resizable(False, False)
    try:
        root.configure(bg="#050713")
    except Exception:
        pass

    title = tk.Label(
        root,
        text="AURA · DOCUMENT BRAIN / GEMINI",
        font=("Segoe UI", 14, "bold"),
        fg="#c7a5ff",
        bg="#050713",
    )
    title.pack(pady=(22, 5))

    info = tk.Label(
        root,
        text=(
            "Colle ta clé API Gemini dans le champ ci-dessous.\n"
            "Elle reste masquée et sera enregistrée uniquement dans le fichier .env local."
        ),
        font=("Segoe UI", 9),
        fg="#9ba7c6",
        bg="#050713",
        justify="center",
    )
    info.pack(pady=(0, 10))

    entry = tk.Entry(
        root,
        show="•",
        width=58,
        font=("Consolas", 11),
        bg="#0a1022",
        fg="#d9edff",
        insertbackground="#76e7ff",
        relief="flat",
    )
    entry.pack(ipady=7, padx=30)
    entry.focus_set()

    buttons = tk.Frame(root, bg="#050713")
    buttons.pack(pady=16)

    def accept_entry() -> None:
        key = _clean_key(entry.get())
        if not valid_cloud_api_token(key):
            messagebox.showerror(
                "Clé invalide",
                "La clé est vide, trop courte ou son format paraît invalide.",
                parent=root,
            )
            return
        result["key"] = key
        root.destroy()

    def use_clipboard() -> None:
        key = _clipboard_key()
        if not valid_cloud_api_token(key):
            messagebox.showerror(
                "Presse-papiers",
                "Aucune clé Gemini valide n'a été trouvée dans le presse-papiers.\n\n"
                "Copie d'abord la clé depuis Google AI Studio puis réessaie.",
                parent=root,
            )
            return
        result["key"] = key
        root.destroy()

    clipboard_button = tk.Button(
        buttons,
        text="UTILISER LE PRESSE-PAPIERS",
        command=use_clipboard,
        font=("Segoe UI", 9, "bold"),
        bg="#17113b",
        fg="#c7a5ff",
        activebackground="#251a55",
        activeforeground="#ffffff",
        relief="flat",
        padx=14,
        pady=7,
    )
    clipboard_button.pack(side="left", padx=6)

    save_button = tk.Button(
        buttons,
        text="ENREGISTRER",
        command=accept_entry,
        font=("Segoe UI", 9, "bold"),
        bg="#0b2d3b",
        fg="#76e7ff",
        activebackground="#10465a",
        activeforeground="#ffffff",
        relief="flat",
        padx=20,
        pady=7,
    )
    save_button.pack(side="left", padx=6)

    entry.bind("<Return>", lambda _event: accept_entry())
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    return _clean_key(result["key"])


def _console_clipboard_flow() -> str:
    print()
    print("Mode console de secours")
    print("1. Copie ta GEMINI_API_KEY dans le presse-papiers Windows.")
    print("2. Appuie simplement sur Entrée ici. La clé ne sera pas affichée.")
    try:
        input("Entrée pour lire le presse-papiers... ")
    except EOFError:
        pass
    return _clipboard_key()


def main() -> int:
    print("============================================================")
    print(" AURA — CONFIGURATION GEMINI 26.8.3")
    print("============================================================")
    print("La clé n'est jamais affichée dans cette console ni dans les journaux.")
    print("Une fenêtre graphique va s'ouvrir pour permettre Ctrl+V.")

    key = _gui_key()
    if not key:
        key = _console_clipboard_flow()

    if not valid_cloud_api_token(key):
        print()
        print("[ERREUR] Aucune clé Gemini valide n'a été fournie.")
        print("Conseil : copie la clé complète, copiée depuis Google AI Studio, puis relance ce script.")
        return 2

    path = persist_local_env_value("AURA_RUNTIME_MODE", "hybrid")
    persist_local_env_value("GEMINI_ENABLED", "true", env_path=path)
    persist_local_env_value("DOCUMENT_CLOUD_ENABLED", "true", env_path=path)
    persist_local_env_value("DOCUMENT_ANALYSIS_PROVIDER", "auto", env_path=path)
    persist_local_env_value("GEMINI_API_KEY", key, env_path=path)

    print()
    print(f"[OK] Configuration enregistrée dans : {path}")
    print("[OK] AURA_RUNTIME_MODE=hybrid")
    print("[OK] GEMINI_ENABLED=true")
    print("[OK] DOCUMENT_CLOUD_ENABLED=true")
    print("[OK] DOCUMENT_ANALYSIS_PROVIDER=auto")
    print("[OK] GEMINI_API_KEY enregistrée (valeur masquée)")
    print()
    print("Redémarre complètement AURA.")
    print("Au prochain démarrage, le journal doit indiquer gemini=True si la clé est chargée.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
