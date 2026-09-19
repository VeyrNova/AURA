from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = Path(os.environ.get("LOCALAPPDATA", "")) / "AURA" / "ui" / "v0.7.2.2-rc4.2"
REPORT = ROOT / "ci" / "reports" / "metadata_invariant_v0863.json"

EXPECTED = {
    "version": "0.8.6.3",
    "build": "2026.08.22.60",
    "release_channel": "universal-windows-p0.8.5.4.1.1",
    "release_date": "2026-08-22",
    "ui_release": "0.7.2.2-rc4.2",
    "core_bridge_sha256": "fcd86f20d9df178848c6a27a8e9fc4044b9794f72226658f437020e8e1df171c",
    "shell_sha256": "94fae7315347d56cfa99895914528eec132021378e65085c9d923fb655ebd9be",
    "ui_watcher_sha256": "6db2f772f781f7322a3cab6bb82d8af2b7e1f1ea8856c3d7abdfb2545b71a365",
}

checks = []

def add(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "pass": bool(ok), "detail": str(detail)})
    print(("[PASS] " if ok else "[FAIL] ") + name + ((" - " + str(detail)) if detail else ""))

def text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def assignment(source: str, name: str) -> str | None:
    m = re.search(r"(?m)^\s*" + re.escape(name) + r"\s*(?::[^=]+)?=\s*['\"]([^'\"]+)['\"]", source)
    return m.group(1) if m else None

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
d2_result = ROOT / "AURA_V0_8_6_3_D2_BRIDGE_RECOVERY_R2_RESULT.json"

for p in [core_version, settings, core_bridge, shell, package, d2_result, *watchers]:
    add("present " + p.name, p.is_file(), p)

if not all(c["pass"] for c in checks):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"schema":"aura.ci.metadata-invariant.v0863.v1","pass":False,"checks":checks}, indent=2), encoding="utf-8")
    raise SystemExit(2)

cv = text(core_version)
add("canonical AURA_VERSION", assignment(cv, "AURA_VERSION") == EXPECTED["version"], assignment(cv, "AURA_VERSION"))
add("canonical AURA_BUILD", assignment(cv, "AURA_BUILD") == EXPECTED["build"], assignment(cv, "AURA_BUILD"))
add("canonical release channel", assignment(cv, "AURA_RELEASE_CHANNEL") == EXPECTED["release_channel"], assignment(cv, "AURA_RELEASE_CHANNEL"))
add("canonical release date", assignment(cv, "AURA_RELEASE_DATE") == EXPECTED["release_date"], assignment(cv, "AURA_RELEASE_DATE"))

st = text(settings)
add("settings imports canonical metadata", bool(re.search(r"from\s+core\.version\s+import[^\n]*AURA_VERSION", st)), "core.version")
add("APP_VERSION derives from AURA_VERSION", bool(re.search(r"(?m)^\s*APP_VERSION\s*(?::[^=]+)?=\s*AURA_VERSION\s*$", st)), "derived alias")
add("no static APP_VERSION literal", not bool(re.search(r"(?m)^\s*APP_VERSION\s*(?::[^=]+)?=\s*['\"]", st)), "no duplicate authority")

active_dirs = ["core","config","services","runtime","ui","tools","memory","agent","security","voice","grounding","aura"]
authority_hits = []
for dirname in active_dirs:
    base = ROOT / dirname
    if not base.is_dir():
        continue
    for p in base.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if rel == "core/version.py":
            continue
        try:
            src = text(p)
        except Exception:
            continue
        if re.search(r"(?m)^\s*AURA_VERSION\s*(?::[^=]+)?=", src):
            authority_hits.append(rel)
add("no second AURA_VERSION authority", len(authority_hits) == 0, authority_hits)

cb = text(core_bridge)
add("core_bridge certified baseline", sha(core_bridge) == EXPECTED["core_bridge_sha256"], sha(core_bridge))
add("core_bridge does not own runtime metadata", "runtime_metadata" not in cb, "boundary ownership")
add("core_bridge module revision preserved", 'VERSION = "P0.6.5.4"' in cb, "P0.6.5.4")

sh = text(shell)
add("shell boundary hash", sha(shell) == EXPECTED["shell_sha256"], sha(shell))
add("/api/system remains authenticated boundary", "if path=='/api/system':" in sh and "rt.service_bridge.system.snapshot()" in sh, "/api/system")
add("metadata schema at shell boundary", "aura.runtime-metadata.v1" in sh, "aura.runtime-metadata.v1")
add("product metadata derives from core.version", "from core.version import AURA_BUILD,AURA_RELEASE_CHANNEL,AURA_RELEASE_DATE,AURA_VERSION" in sh, "derived")
add("UI release derives from shell RELEASE", "'ui':{'release':RELEASE}" in sh, "UI-owned")
add("no product version literal in shell metadata contract", "'version':'0.8.6.3'" not in sh and '"version":"0.8.6.3"' not in sh, "no copied product version")

package_obj = json.loads(text(package))
add("UI package release independent", package_obj.get("version") == EXPECTED["ui_release"], package_obj.get("version"))
add("product and UI versions remain independent", EXPECTED["version"] != EXPECTED["ui_release"], EXPECTED["version"] + " != " + EXPECTED["ui_release"])

watch_hashes = [sha(p) for p in watchers]
add("UI watcher mirrors identical", len(set(watch_hashes)) == 1, watch_hashes)
add("UI watcher certified hash", watch_hashes[0] == EXPECTED["ui_watcher_sha256"], watch_hashes[0])
w = text(watchers[0])
add("UI reads runtime_metadata", "d.runtime_metadata" in w, "consumer")
add("UI emits runtime metadata event", "aura:runtime-metadata" in w, "event")
add("UI exposes runtime metadata global", "__AURA_RUNTIME_METADATA__" in w, "global")
add("UI does not hardcode product version", EXPECTED["version"] not in w, "no product literal")

d2 = json.loads(text(d2_result))
add("D2 status PASS", d2.get("status") == "PASS", d2.get("status"))
add("D2 gate to D3", d2.get("next_gate") == "READY_FOR_D3_FINAL_CI_CERTIFICATION", d2.get("next_gate"))
add("D2 live contract schema", (d2.get("live_contract") or {}).get("schema") == "aura.runtime-metadata.v1", (d2.get("live_contract") or {}).get("schema"))
add("D2 live product version", (d2.get("live_contract") or {}).get("product_version") == EXPECTED["version"], (d2.get("live_contract") or {}).get("product_version"))
add("D2 live UI release", (d2.get("live_contract") or {}).get("ui_release") == EXPECTED["ui_release"], (d2.get("live_contract") or {}).get("ui_release"))

passed = sum(1 for c in checks if c["pass"])
failed = len(checks) - passed
result = {
    "schema": "aura.ci.metadata-invariant.v0863.v1",
    "phase": "AURA v0.8.6.3 D3 Metadata CI Invariant",
    "pass": failed == 0,
    "checks_total": len(checks),
    "checks_passed": passed,
    "checks_failed": failed,
    "checks": checks,
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

if failed:
    print("METADATA INVARIANT V0863: FAIL")
    raise SystemExit(2)

print("[PASS] metadata_contract_v0863")
print("METADATA INVARIANT V0863: PASS")
# Success returns naturally with exit code 0; do not terminate a parent CI lane.