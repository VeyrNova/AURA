"""Source-checkout launcher; standard library only, no process spawning.

Use Python -I -S -B to exclude site initialization and bytecode generation.
"""


def main() -> int:
    from pathlib import Path
    import sys

    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project / "src"))
    from aura_native.__main__ import main as run_selfcheck

    return run_selfcheck(project_root=project)


if __name__ == "__main__":
    raise SystemExit(main())
