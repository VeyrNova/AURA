from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "ci" / "ui_source_manifest_v0865.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load():
    return json.loads(MANIFEST.read_text(encoding="utf-8-sig"))

def check(manifest):
    failures = []
    for item in manifest["assets"]:
        expected = item["sha256"].lower()
        canonical = Path(item["canonical_source"])
        runtime = Path(item["runtime_dist"])
        paths = [canonical, runtime] + [Path(p) for p in item.get("source_mirrors", [])]
        seen = set()
        for path in paths:
            key = str(path.resolve()).lower() if path.exists() else str(path).lower()
            if key in seen:
                continue
            seen.add(key)
            if not path.is_file():
                failures.append("missing:" + str(path))
                continue
            actual = sha(path)
            if actual != expected:
                failures.append("hash:" + str(path) + ":" + actual + "!=" + expected)
    return failures

def stage(manifest, output: Path):
    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for item in manifest["assets"]:
        source = Path(item["canonical_source"])
        target = assets / item["name"]
        shutil.copy2(source, target)
        if sha(target) != item["sha256"].lower():
            raise RuntimeError("staged hash mismatch: " + item["name"])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--stage")
    args = parser.parse_args()

    manifest = load()
    failures = check(manifest)
    if failures:
        for failure in failures:
            print("[FAIL] " + failure)
        raise SystemExit(2)

    if args.check:
        print("[PASS] ui_source_manifest_v0865")

    if args.stage:
        output = Path(args.stage).resolve()
        stage(manifest, output)
        print("[PASS] staged " + str(len(manifest["assets"])) + " assets -> " + str(output))

    raise SystemExit(0)

if __name__ == "__main__":
    main()
