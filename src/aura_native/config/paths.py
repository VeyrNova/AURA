"""Resolve a development profile without discovering external installations.

Resolution is read-only. It is not a filesystem security boundary: future
writers must enforce their own containment and handle filesystem races.
"""

from dataclasses import dataclass
from pathlib import Path


class PathConfigurationError(ValueError):
    """A required path is missing or overlaps application resources."""


@dataclass(frozen=True)
class RuntimePaths:
    project_root: Path
    resources_dir: Path
    state_dir: Path
    config_dir: Path
    data_dir: Path
    cache_dir: Path
    logs_dir: Path
    models_dir: Path

    @classmethod
    def resolve(cls, state_dir: str | Path, *, project_root: Path) -> "RuntimePaths":
        if not isinstance(state_dir, (str, Path)) or not str(state_dir).strip():
            raise PathConfigurationError("state_dir must be explicitly provided")
        # No expandvars/expanduser: environment and user-profile discovery are
        # deliberately absent. Relative paths are relative to the project.
        raw = Path(state_dir)
        if "~" in raw.parts or "%" in str(raw) or "$" in str(raw):
            raise PathConfigurationError("use an explicit path, without environment placeholders")
        if raw.drive and not raw.is_absolute():
            raise PathConfigurationError("drive-relative paths are ambiguous")
        if raw.root and not raw.is_absolute():
            raise PathConfigurationError("root-relative paths are ambiguous")
        try:
            project = Path(project_root).resolve(strict=True)
            if not project.is_dir():
                raise PathConfigurationError("project_root must be a directory")
            state = (raw if raw.is_absolute() else project / raw).resolve(strict=False)
            if state == Path(state.anchor) or project.is_relative_to(state):
                raise PathConfigurationError("state_dir cannot contain the project or be a filesystem root")
            for name in ("src", "app", "tools", "docs", ".venv", ".runtime"):
                protected = (project / name).resolve(strict=False)
                if state.is_relative_to(protected) or protected.is_relative_to(state):
                    raise PathConfigurationError("state_dir overlaps protected application resources")
            if state.exists() and not state.is_dir():
                raise PathConfigurationError("state_dir points to a file")
            children = {}
            for name in ("config", "data", "cache", "logs", "models"):
                child = (state / name).resolve(strict=False)
                if not child.is_relative_to(state):
                    raise PathConfigurationError("a state subdirectory resolves outside state_dir")
                if child.exists() and not child.is_dir():
                    raise PathConfigurationError("a state subdirectory points to a file")
                children[name + "_dir"] = child
        except (OSError, RuntimeError) as exc:
            raise PathConfigurationError("paths could not be resolved; no fallback was attempted") from exc
        return cls(project, project / "app", state, **children)

    def as_dict(self) -> dict[str, str]:
        return {name: str(getattr(self, name)) for name in self.__dataclass_fields__}

