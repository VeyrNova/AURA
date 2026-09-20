from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "_patch_backups",
    "_github_preflight", "vendor", "node_modules", "tests",
}

def iter_python_files():
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        yield path

def module_name(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)

FILES = list(iter_python_files())
MODULES = {module_name(p) for p in FILES if module_name(p)}
PACKAGES = {m for m in MODULES if (ROOT / Path(*m.split(".")) / "__init__.py").is_file()}
TOP_LEVEL = {m.split(".", 1)[0] for m in MODULES}

def exists_local_module(name: str) -> bool:
    if not name:
        return True
    if name in MODULES or name in PACKAGES:
        return True
    p = ROOT.joinpath(*name.split("."))
    return p.with_suffix(".py").is_file() or (p / "__init__.py").is_file()

def resolve_relative(current: str, level: int, target: str | None) -> str:
    parts = current.split(".")
    # For a normal module, remove its leaf before applying relative level.
    base = parts[:-1]
    if level > 1:
        remove = level - 1
        base = base[:-remove] if remove <= len(base) else []
    if target:
        base.extend(target.split("."))
    return ".".join(base)

missing: list[tuple[str, int, str]] = []

for path in FILES:
    current = module_name(path)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        print(f"[FAIL] AST parse: {path.relative_to(ROOT)}: {exc}")
        sys.exit(2)

    for node in ast.walk(tree):
        targets: list[str] = []
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                targets = [resolve_relative(current, node.level, node.module)]
            elif node.module:
                targets = [node.module]

        for target in targets:
            top = target.split(".", 1)[0] if target else ""
            if top not in TOP_LEVEL:
                continue
            if not exists_local_module(target):
                missing.append((str(path.relative_to(ROOT)).replace("\\", "/"), node.lineno, target))

if missing:
    print("[FAIL] Missing internal Python modules:")
    for rel, line, target in sorted(set(missing)):
        print(f"  {rel}:{line} -> {target}")
    print(f"[FAIL] unique_missing_modules={len({m[2] for m in missing})}")
    print(f"[FAIL] broken_import_references={len(set(missing))}")
    sys.exit(1)

print(f"[PASS] scanned_python_files={len(FILES)}")
print("[PASS] missing_internal_modules=0")
print("[PASS] repository import closure is complete")
