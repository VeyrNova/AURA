from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "_patch_backups",
    "_github_preflight",
    "vendor",
    "node_modules",
    "tests",
}

# Bundled third-party Python copied into the Chromium QR helper is not part of
# AURA's internal module graph and must not influence repository completeness.
SKIP_PATH_PARTS = {"aura_qr_vendor"}


def iter_python_files():
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if any(part in SKIP_PATH_PARTS for part in rel.parts):
            continue
        yield path


def module_info(path: Path) -> tuple[str, bool]:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    is_package_init = parts[-1] == "__init__"
    if is_package_init:
        parts.pop()
    return ".".join(parts), is_package_init


FILES = list(iter_python_files())
MODULE_INFO = {path: module_info(path) for path in FILES}
MODULES = {name for name, _ in MODULE_INFO.values() if name}
TOP_LEVEL = {name.split(".", 1)[0] for name in MODULES}


def exists_local_module(name: str) -> bool:
    if not name:
        return True
    if name in MODULES:
        return True
    path = ROOT.joinpath(*name.split("."))
    return path.with_suffix(".py").is_file() or (path / "__init__.py").is_file()


def resolve_relative(
    current: str,
    is_package_init: bool,
    level: int,
    target: str | None,
) -> str:
    parts = current.split(".") if current else []
    base = parts[:] if is_package_init else parts[:-1]

    # Python: one leading dot means current package; each additional dot walks
    # one package upward.
    upward = max(0, level - 1)
    if upward:
        base = base[:-upward] if upward <= len(base) else []

    if target:
        base.extend(target.split("."))
    return ".".join(base)


missing: list[tuple[str, int, str]] = []

for path in FILES:
    current, is_package_init = MODULE_INFO[path]
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
                targets = [
                    resolve_relative(
                        current,
                        is_package_init,
                        node.level,
                        node.module,
                    )
                ]
            elif node.module:
                targets = [node.module]

        for target in targets:
            top = target.split(".", 1)[0] if target else ""
            if top not in TOP_LEVEL:
                continue
            if not exists_local_module(target):
                missing.append(
                    (
                        str(path.relative_to(ROOT)).replace("\\", "/"),
                        node.lineno,
                        target,
                    )
                )

missing = sorted(set(missing))

if missing:
    print("[FAIL] Missing internal Python modules:")
    for rel, line, target in missing:
        print(f"  {rel}:{line} -> {target}")
    print(f"[FAIL] unique_missing_modules={len({item[2] for item in missing})}")
    print(f"[FAIL] broken_import_references={len(missing)}")
    sys.exit(1)

print(f"[PASS] scanned_python_files={len(FILES)}")
print("[PASS] missing_internal_modules=0")
print("[PASS] repository import closure is complete")
