from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_VERSION = ROOT / "core" / "version.py"
UI_RELEASE = "0.7.2.2-rc4.2"
DEPLOYED_UI = Path(os.environ.get("LOCALAPPDATA", "")) / "AURA" / "ui" / ("v" + UI_RELEASE)

# Only historical milestone-style labels. Generic semver such as three.js
# package versions must never be classified as an AURA product label.
LEGACY_MILESTONE_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:P\d+(?:\.\d+){2,6}|RC\d+(?:\.\d+){0,3})(?![A-Za-z0-9_])",
    re.I,
)

CURRENT_AURA_VERSION_RE = re.compile(
    r"(?<![A-Za-z0-9_])v?0\.\d+(?:\.\d+){1,3}(?![A-Za-z0-9_])",
    re.I,
)

RENDER_HINTS = (
    "innerhtml", "textcontent", "innertext", "insertadjacenthtml",
    "<div", "<span", "<small", "<header", "<footer", "<section",
    "<em", "<i>", "<b>", "<p>", "<title", "settext(", "setwindowtitle(",
    "template", "markup", "subtitle", "label",
)

AURA_LABEL_HINTS = (
    "aura", "system live", "desktop intelligence", "hardware profile",
    "project ui", "authorized project intelligence", "interactive",
    "etape", "etape", "stage", "release", "runtime v",
)

TECHNICAL_LINE_HINTS = (
    "server_version", "protocol_version", "aura_ui_host", "logging.getlogger",
    "_aura_rc", "session_file", "rc4_2_session", "schema", "migration",
    "baseline", "certificate", "historical", "compatibility", "manifest",
    "http/", "threejs-", "three.js", "node_modules",
)

def current_version():
    src = CORE_VERSION.read_text(encoding="utf-8-sig", errors="replace")
    m = re.search(r'(?m)^\s*AURA_VERSION\s*=\s*["\']([^"\']+)["\']', src)
    if not m:
        raise RuntimeError("AURA_VERSION not found")
    return m.group(1)

def is_minified_bundle(path):
    name = path.name.lower()
    if re.fullmatch(r"index-[a-z0-9_-]+\.js", name):
        return True
    try:
        if path.stat().st_size > 700000:
            sample = path.read_text(encoding="utf-8-sig", errors="replace")[:10000]
            lines = sample.splitlines()
            if lines and max(len(x) for x in lines) > 5000:
                return True
    except Exception:
        pass
    return False

def candidate_files():
    out = set()

    for p in ROOT.glob("aura-*.js"):
        if p.is_file():
            out.add(p)
    if (ROOT / "index.html").is_file():
        out.add(ROOT / "index.html")

    for base in (ROOT / "src",):
        if base.is_dir():
            for ext in ("*.js", "*.html", "*.htm"):
                out.update(p for p in base.rglob(ext) if p.is_file())

    if DEPLOYED_UI.is_dir():
        for p in (DEPLOYED_UI / "index.html", DEPLOYED_UI / "dist" / "index.html"):
            if p.is_file():
                out.add(p)
        for base in (DEPLOYED_UI / "src", DEPLOYED_UI / "dist" / "assets"):
            if base.is_dir():
                for ext in ("*.js", "*.html", "*.htm"):
                    for p in base.rglob(ext):
                        if p.is_file() and not is_minified_bundle(p):
                            out.add(p)

    return sorted(out)

def is_render_line(line):
    stripped = line.lstrip()
    if stripped.startswith(("//", "/*", "*", "#")):
        return False
    low = line.lower()
    if any(x in low for x in TECHNICAL_LINE_HINTS):
        return False
    return any(x in low for x in RENDER_HINTS) and any(x in low for x in AURA_LABEL_HINTS)

def replace_line(line, display_version):
    if not is_render_line(line):
        return line, 0

    count = 0

    def legacy_repl(match):
        nonlocal count
        count += 1
        return display_version

    out = LEGACY_MILESTONE_RE.sub(legacy_repl, line)

    # Existing AURA product semver is replaced only on strongly AURA-labelled
    # render lines. This cannot capture third-party package versions.
    low = line.lower()
    if any(x in low for x in ("aura", "project ui", "system live", "hardware profile", "runtime v", "release")):
        def semver_repl(match):
            nonlocal count
            token = match.group(0)
            if token == display_version:
                return token
            count += 1
            return display_version
        out = CURRENT_AURA_VERSION_RE.sub(semver_repl, out)

    return out, count

def preview():
    display = "v" + current_version()
    changes = []
    total = 0

    for path in candidate_files():
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue

        new_lines = []
        replacements = 0
        for line in text.splitlines(keepends=True):
            new_line, count = replace_line(line, display)
            new_lines.append(new_line)
            replacements += count

        if replacements:
            new_text = "".join(new_lines)
            if new_text != text:
                changes.append({
                    "path": str(path),
                    "replacements": replacements,
                    "text": new_text,
                })
                total += replacements

    return display, changes, total

def stale_hits():
    display = "v" + current_version()
    hits = []

    for path in candidate_files():
        try:
            lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except Exception:
            continue

        for line_no, line in enumerate(lines, 1):
            if not is_render_line(line):
                continue

            for match in LEGACY_MILESTONE_RE.finditer(line):
                hits.append({
                    "path": str(path),
                    "line": line_no,
                    "token": match.group(0),
                    "context": line.strip()[:300],
                })

            low = line.lower()
            if any(x in low for x in ("aura", "project ui", "system live", "hardware profile", "runtime v", "release")):
                for match in CURRENT_AURA_VERSION_RE.finditer(line):
                    token = match.group(0)
                    if token != display:
                        hits.append({
                            "path": str(path),
                            "line": line_no,
                            "token": token,
                            "context": line.strip()[:300],
                        })

    return hits

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    display, changes, total = preview()

    if args.apply:
        for item in changes:
            Path(item["path"]).write_text(item["text"], encoding="utf-8", newline="")

    hits = stale_hits() if args.check or args.apply else []
    result = {
        "display_version": display,
        "candidate_files": len(candidate_files()),
        "files_to_change": len(changes),
        "replacements": total,
        "stale_hits": hits,
        "pass": not hits if args.check or args.apply else True,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print("[INFO] display_version=" + display)
        print("[INFO] candidate_files=" + str(result["candidate_files"]))
        print("[INFO] files_to_change=" + str(result["files_to_change"]))
        print("[INFO] replacements=" + str(total))
        if hits:
            for hit in hits[:50]:
                print("[FAIL] stale AURA visible version " + hit["path"] + ":" + str(hit["line"]) + " " + hit["token"])
        else:
            print("[PASS] AURA user-visible product version surfaces synchronized")

    return 0 if result["pass"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
