from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = Path(os.environ.get("LOCALAPPDATA", "")) / "AURA" / "ui" / ("v" + "0.7.2.2-rc4.2")
REPORT = ROOT / "ci" / "reports" / "metadata_invariant_v0872.json"

EXPECTED_VERSION = "0.8.7.2"
EXPECTED_UI = "0.7.2.2-rc4.2"
EXPECTED_CORE_BRIDGE = "fcd86f20d9df178848c6a27a8e9fc4044b9794f72226658f437020e8e1df171c"
EXPECTED_SHELL = "94fae7315347d56cfa99895914528eec132021378e65085c9d923fb655ebd9be"
EXPECTED_WATCHER = "6db2f772f781f7322a3cab6bb82d8af2b7e1f1ea8856c3d7abdfb2545b71a365"

checks = []
def add(name, ok, detail=""):
    checks.append({"name": name, "pass": bool(ok), "detail": str(detail)})
    print(("[PASS] " if ok else "[FAIL] ") + name + ((" - " + str(detail)) if detail != "" else ""))

def text(path):
    return path.read_text(encoding="utf-8-sig")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

core_version = ROOT / "core" / "version.py"
settings = ROOT / "config" / "settings.py"
core_bridge = ROOT / "services" / "core_bridge.py"
shell = UI_ROOT / "tools" / "shell_host.py"
package = UI_ROOT / "package.json"
watchers = [
    UI_ROOT / "src" / "aura-p081-event-watchers.js",
    UI_ROOT / "src" / "assets" / "aura-p081-event-watchers.js",
    UI_ROOT / "dist" / "assets" / "aura-p081-event-watchers.js",
]

for p in [core_version, settings, core_bridge, shell, package, *watchers]:
    add("present " + p.name, p.is_file(), p)

if all(c["pass"] for c in checks):
    cv = text(core_version)
    m = re.search(r'(?m)^\s*AURA_VERSION\s*=\s*["\']([^"\']+)["\']', cv)
    add("canonical product version", bool(m) and m.group(1) == EXPECTED_VERSION, m.group(1) if m else None)

    st = text(settings)
    add("APP_VERSION derives from AURA_VERSION", bool(re.search(r"(?m)^\s*APP_VERSION\s*(?::[^=]+)?=\s*AURA_VERSION\s*$", st)), "derived")
    add("no static APP_VERSION literal", not bool(re.search(r'(?m)^\s*APP_VERSION\s*(?::[^=]+)?=\s*["\']', st)), "no duplicate")

    authority_hits = []
    for dirname in ["aura","agent","config","core","grounding","memory","runtime","security","services","tools","ui","voice"]:
        base = ROOT / dirname
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            if p == core_version or "__pycache__" in p.parts or "_dev" in p.parts:
                continue
            try:
                src = text(p)
            except Exception:
                continue
            if re.search(r"(?m)^\s*AURA_VERSION\s*(?::[^=]+)?=", src):
                authority_hits.append(p.relative_to(ROOT).as_posix())
    add("no second product version authority", len(authority_hits) == 0, authority_hits)

    add("core_bridge unchanged", sha(core_bridge) == EXPECTED_CORE_BRIDGE, sha(core_bridge))
    sh = text(shell)
    add("shell boundary unchanged", sha(shell) == EXPECTED_SHELL, sha(shell))
    add("shell derives metadata from core.version", "from core.version import AURA_BUILD,AURA_RELEASE_CHANNEL,AURA_RELEASE_DATE,AURA_VERSION" in sh, "derived")
    add("metadata schema preserved", "aura.runtime-metadata.v1" in sh, "schema")
    add("UI release derives from RELEASE", "'ui':{'release':RELEASE}" in sh, "UI-owned")

    package_version = json.loads(text(package)).get("version")
    add("UI release independent", package_version == EXPECTED_UI, package_version)

    hashes = [sha(p) for p in watchers]
    add("UI watcher mirrors identical", len(set(hashes)) == 1, hashes)
    add("UI watcher certified hash", hashes[0] == EXPECTED_WATCHER, hashes[0])
    w = text(watchers[0])
    add("UI reads runtime_metadata", "d.runtime_metadata" in w, "consumer")
    add("UI emits metadata event", "aura:runtime-metadata" in w, "event")
    add("UI has no product version literal", EXPECTED_VERSION not in w, "no hardcode")

passed = sum(1 for c in checks if c["pass"])
failed = len(checks) - passed
result = {
    "schema": "aura.ci.metadata-invariant.v0872.v1",
    "pass": failed == 0,
    "checks_total": len(checks),
    "checks_passed": passed,
    "checks_failed": failed,
    "checks": checks,
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
print("METADATA INVARIANT V0872: PASS" if result["pass"] else "METADATA INVARIANT V0872: FAIL")
raise SystemExit(0 if result["pass"] else 2)
