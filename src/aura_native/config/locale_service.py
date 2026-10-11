"""Native UI language preference; no speech or provider configuration."""
import json
import os
from pathlib import Path


class LocaleService:
    supported = frozenset({"fr-FR", "en-US"})

    def __init__(self, config_dir: Path):
        self.path = Path(config_dir) / "ui_locale.json"
        self.locale = "fr-FR"
        if self.path.is_file():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                value = data.get("locale") if isinstance(data, dict) else None
                if isinstance(value, str) and value in self.supported:
                    self.locale = value
            except (OSError, ValueError):
                # An unreadable preference must not prevent UI startup.
                pass

    def set_locale(self, value: str) -> bool:
        if not isinstance(value, str) or value not in self.supported:
            return False
        if value == self.locale:
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({"locale": value}), encoding="utf-8")
        os.replace(temporary, self.path)
        self.locale = value
        return True
