from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Mapping, Optional

AURA_PATHS_SCHEMA = "aura.paths.v1"
AURA_PATHS_PATCH = "P0.8.5.2.1"


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "portable"}


def _resolve(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False)
    except Exception:
        return path.expanduser().absolute()


def _has_core_markers(path: Path) -> bool:
    return (path / "core" / "version.py").is_file() and (path / "VERSION").is_file()


def discover_core_root(
    start: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Optional[Path]:
    """Discover AURA Core without relying on a machine-specific literal path."""
    e = dict(os.environ if env is None else env)

    explicit = e.get("AURA_ROOT")
    if explicit:
        p = _resolve(Path(explicit))
        if _has_core_markers(p):
            return p

    seeds = []
    if start is not None:
        seeds.append(_resolve(Path(start)))
    try:
        seeds.append(_resolve(Path.cwd()))
    except Exception:
        pass
    try:
        seeds.append(_resolve(Path(__file__).parent))
    except Exception:
        pass
    if getattr(sys, "frozen", False):
        try:
            seeds.append(_resolve(Path(sys.executable).parent))
        except Exception:
            pass

    seen = set()
    for seed in seeds:
        p = seed if seed.is_dir() else seed.parent
        for candidate in (p, *p.parents):
            key = str(candidate).casefold()
            if key in seen:
                continue
            seen.add(key)
            if _has_core_markers(candidate):
                return candidate
    return None


def _default_local_appdata(env: Mapping[str, str]) -> Path:
    raw = env.get("LOCALAPPDATA")
    if raw:
        return _resolve(Path(raw))
    if os.name == "nt":
        return _resolve(Path.home() / "AppData" / "Local")
    return _resolve(Path.home() / ".local" / "share")


def _default_roaming_appdata(env: Mapping[str, str]) -> Path:
    raw = env.get("APPDATA")
    if raw:
        return _resolve(Path(raw))
    if os.name == "nt":
        return _resolve(Path.home() / "AppData" / "Roaming")
    return _resolve(Path.home() / ".config")


class AuraPaths:
    """Central path resolver. P0.8.5.2.1 is resolution-only: it does not move data."""

    def __init__(
        self,
        *,
        core_root: Path,
        deployment_mode: str,
        local_appdata: Path,
        roaming_appdata: Path,
        ui_root: Path,
        data_root: Path,
        config_root: Path,
        models_root: Path,
        cache_root: Path,
        logs_root: Path,
        database_root: Path,
        database_file: Path,
        temp_root: Path,
    ) -> None:
        self.core_root = core_root
        self.deployment_mode = deployment_mode
        self.local_appdata = local_appdata
        self.roaming_appdata = roaming_appdata
        self.ui_root = ui_root
        self.data_root = data_root
        self.config_root = config_root
        self.models_root = models_root
        self.cache_root = cache_root
        self.logs_root = logs_root
        self.database_root = database_root
        self.database_file = database_file
        self.temp_root = temp_root

    @classmethod
    def resolve(
        cls,
        *,
        core_root: Optional[Path] = None,
        start: Optional[Path] = None,
        env: Optional[Mapping[str, str]] = None,
        local_appdata: Optional[Path] = None,
        roaming_appdata: Optional[Path] = None,
    ) -> "AuraPaths":
        e = dict(os.environ if env is None else env)

        core = _resolve(Path(core_root)) if core_root else discover_core_root(start=start, env=e)
        if core is None:
            raise RuntimeError(
                "AURA Core introuvable. Définissez AURA_ROOT ou exécutez depuis l'installation AURA."
            )

        local = _resolve(Path(local_appdata)) if local_appdata else _default_local_appdata(e)
        roaming = _resolve(Path(roaming_appdata)) if roaming_appdata else _default_roaming_appdata(e)

        mode_raw = (e.get("AURA_DEPLOYMENT_MODE") or "").strip().lower()
        if mode_raw in {"portable", "installed", "development"}:
            mode = mode_raw
        elif _truthy(e.get("AURA_PORTABLE")) or (core / "portable.flag").is_file():
            mode = "portable"
        else:
            mode = "installed"

        aura_local = local / "AURA"
        aura_roaming = roaming / "AURA"

        if mode == "portable":
            default_ui = core / "ui"
            default_data = core / "data"
            default_config = core / "config"
            default_models = core / "models"
            default_cache = core / "cache"
            default_logs = core / "logs"
            default_temp = core / "runtime" / "tmp"
        else:
            default_ui = aura_local / "ui"
            default_data = aura_local / "data"
            default_config = aura_roaming / "config"
            default_models = aura_local / "models"
            default_cache = aura_local / "cache"
            default_logs = aura_local / "logs"
            default_temp = aura_local / "runtime" / "tmp"

        ui = None
        if e.get("AURA_UI_ROOT"):
            ui = _resolve(Path(e["AURA_UI_ROOT"]))
        else:
            current = aura_local / "ui" / "current.json"
            if current.is_file():
                try:
                    payload = json.loads(current.read_text(encoding="utf-8"))
                    raw = payload.get("ui_root")
                    if raw:
                        ui = _resolve(Path(raw))
                except Exception:
                    ui = None
        if ui is None:
            ui = _resolve(default_ui)

        data = _resolve(Path(e.get("AURA_DATA_ROOT") or default_data))
        config = _resolve(Path(e.get("AURA_CONFIG_ROOT") or default_config))
        models = _resolve(Path(e.get("AURA_MODELS_ROOT") or default_models))
        cache = _resolve(Path(e.get("AURA_CACHE_ROOT") or default_cache))
        logs = _resolve(Path(e.get("AURA_LOGS_ROOT") or default_logs))
        db_root = _resolve(Path(e.get("AURA_DATABASE_ROOT") or (data / "database")))
        db_file = _resolve(Path(e.get("AURA_DB_PATH") or (db_root / "aura.db")))
        temp = _resolve(Path(e.get("AURA_TEMP_ROOT") or default_temp))

        return cls(
            core_root=core,
            deployment_mode=mode,
            local_appdata=local,
            roaming_appdata=roaming,
            ui_root=ui,
            data_root=data,
            config_root=config,
            models_root=models,
            cache_root=cache,
            logs_root=logs,
            database_root=db_root,
            database_file=db_file,
            temp_root=temp,
        )

    @property
    def legacy_database_file(self) -> Path:
        return self.core_root / "database" / "aura.db"

    @property
    def legacy_models_root(self) -> Path:
        return self.core_root / "models"

    @property
    def legacy_logs_root(self) -> Path:
        return self.core_root / "logs"

    def as_dict(self) -> dict:
        return {
            "schema": AURA_PATHS_SCHEMA,
            "patch": AURA_PATHS_PATCH,
            "deployment_mode": self.deployment_mode,
            "core_root": str(self.core_root),
            "ui_root": str(self.ui_root),
            "data_root": str(self.data_root),
            "config_root": str(self.config_root),
            "models_root": str(self.models_root),
            "cache_root": str(self.cache_root),
            "logs_root": str(self.logs_root),
            "database_root": str(self.database_root),
            "database_file": str(self.database_file),
            "temp_root": str(self.temp_root),
        }

    def migration_plan(self) -> dict:
        """Read-only description of future migrations. Performs no file operation."""
        candidates = [
            ("database", self.legacy_database_file, self.database_file),
            ("models", self.legacy_models_root, self.models_root),
            ("logs", self.legacy_logs_root, self.logs_root),
        ]
        items = []
        for kind, source, target in candidates:
            try:
                exists = source.exists()
            except Exception:
                exists = False
            items.append(
                {
                    "kind": kind,
                    "source": str(source),
                    "target": str(target),
                    "source_exists": bool(exists),
                    "same_location": _resolve(source) == _resolve(target),
                    "action": "NONE_P08521_READ_ONLY",
                }
            )
        return {
            "schema": "aura.paths.migration-plan.v1",
            "read_only": True,
            "items": items,
        }

    def validate(self) -> list[str]:
        issues = []
        all_paths = {
            "core_root": self.core_root,
            "ui_root": self.ui_root,
            "data_root": self.data_root,
            "config_root": self.config_root,
            "models_root": self.models_root,
            "cache_root": self.cache_root,
            "logs_root": self.logs_root,
            "database_root": self.database_root,
            "database_file": self.database_file,
            "temp_root": self.temp_root,
        }
        for name, p in all_paths.items():
            if not p.is_absolute():
                issues.append(f"{name}:not_absolute")

        if self.deployment_mode not in {"portable", "installed", "development"}:
            issues.append("deployment_mode:invalid")

        if self.deployment_mode == "installed":
            for name in ("data_root", "config_root", "cache_root", "logs_root", "database_root", "temp_root"):
                p = all_paths[name]
                try:
                    p.relative_to(self.core_root)
                    issues.append(f"{name}:inside_core")
                except ValueError:
                    pass

        return issues


def resolve_paths(**kwargs) -> AuraPaths:
    return AuraPaths.resolve(**kwargs)
