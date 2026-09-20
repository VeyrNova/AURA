from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "_patch_backups",
    "_github_preflight", "vendor", "node_modules", "tests", "payload",
}
SKIP_PATH_PARTS = {"aura_qr_vendor"}

PRIVATE_USER_PATH = re.compile(
    r"""(?ix)
    \b[A-Z]:
    (?:\\\\|/)
    Users
    (?:\\\\|/)
    [^\\\\/\r\n"' ]+
    """
)

REFERENCE_ROOT = re.compile(
    r"""(?ix)
    \bC:
    (?:\\\\|/)
    AURA[ ]GPT[ ]version
    """
)


def iter_python_files():
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if any(part in SKIP_PATH_PARTS for part in rel.parts):
            continue
        yield path


violations: list[tuple[str, int, str]] = []

for path in iter_python_files():
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    text = path.read_text(encoding="utf-8", errors="ignore")
    for lineno, line in enumerate(text.splitlines(), 1):
        if PRIVATE_USER_PATH.search(line):
            violations.append((rel, lineno, "hard-coded Windows user-profile path"))
        if REFERENCE_ROOT.search(line):
            violations.append((rel, lineno, "hard-coded maintainer AURA source root"))

if violations:
    print("[FAIL] Non-portable maintainer-specific paths found in production source:")
    for rel, line, reason in sorted(set(violations)):
        print(f"  {rel}:{line} -> {reason}")
    print(f"[FAIL] portability_violations={len(set(violations))}")
    sys.exit(1)

print("[PASS] maintainer-specific production paths=0")
print("[PASS] production source portability gate")
