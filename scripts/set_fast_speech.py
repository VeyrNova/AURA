"""Enable/disable AURA Fast Speech by updating only FAST_SPEECH_ENABLED in .env."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"


def set_value(enabled: bool) -> None:
    key = "FAST_SPEECH_ENABLED"
    value = "true" if enabled else "false"
    lines = ENV.read_text(encoding="utf-8", errors="replace").splitlines() if ENV.is_file() else []
    out = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and stripped.split("=", 1)[0].strip().casefold() == key.casefold():
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")
    ENV.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"[PASS] {key}={value}")
    print("Redémarre AURA pour appliquer ce réglage.")


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1].lower() not in {"on", "off"}:
        print("Usage: set_fast_speech.py on|off")
        return 2
    set_value(sys.argv[1].lower() == "on")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
