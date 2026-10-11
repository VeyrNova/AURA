"""Read-only foundation diagnostic. This does not start the AURA application."""

import argparse
import json
from pathlib import Path
import sys

from aura_native import __version__
from aura_native.bootstrap.composition import compose_runtime


def main(argv: list[str] | None = None, *, project_root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description="AURA Native: minimal foundation self-check (lot 1)")
    parser.add_argument("--self-check", action="store_true", required=True)
    parser.add_argument("--state-dir", required=True, help="Explicit state location; no directories are created")
    parser.add_argument("--project-root", type=Path, help="Explicit project/resource root (required outside source checkout)")
    args = parser.parse_args(argv)
    root = args.project_root if args.project_root is not None else project_root
    if root is None:
        # This is our own source tree, not a search for an AURA installation.
        source_file = Path(__file__).resolve()
        candidate = source_file.parents[2]
        if source_file.parent.parent.name != "src" or not (candidate / "pyproject.toml").is_file():
            print(json.dumps({"ok": False, "error": "project_root_required"}))
            return 2
        root = candidate
    try:
        runtime = compose_runtime(project_root=root, state_dir=args.state_dir)
        transitions = [runtime.state.value]
        runtime.start()
        transitions.append(runtime.state.value)
        runtime.stop()
        transitions.append(runtime.state.value)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": "invalid_configuration", "detail": str(exc)}))
        return 2
    modules = [
        {"name": name, "origin": getattr(module, "__file__", None)}
        for name, module in sorted(sys.modules.items()) if module is not None
    ]
    print(json.dumps({
        "schema_version": 1,
        "ok": True,
        "scope": "minimal_foundation_only",
        "application_ready": False,
        "version": __version__,
        "python": sys.version.split()[0],
        "profile": runtime.settings.profile,
        "lifecycle": transitions,
        "paths": runtime.paths.as_dict(),
        "capabilities": [
            {"name": c.name, "state": c.state.value, "reason": c.reason} for c in runtime.capabilities
        ],
        "modules": modules,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

