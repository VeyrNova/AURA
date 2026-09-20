from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(
    os.environ.get("AURA_ROOT")
    or Path(__file__).resolve().parents[1]
).resolve()

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION


TEXT_SUFFIXES = {
    ".html", ".htm", ".js", ".mjs", ".cjs",
    ".css", ".json", ".txt",
}

SKIP_PARTS = {
    ".git", "venv", ".venv", "__pycache__",
    "_patch_backups", "_dev", "vendor",
    "node_modules", "dist-info",
}

MARKERS = (
    b"Project UI Asset Refresh",
    b"INTERACTIVE",
)

VERSION_RE = re.compile(
    rb"v(\d+)\.(\d+)\.(\d+)"
)


def _ui_roots() -> tuple[Path, ...]:
    candidates = [
        ROOT / "ui",
    ]

    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(
            Path(local) / "AURA" / "ui"
        )

    roaming = os.environ.get("APPDATA")
    if roaming:
        candidates.append(
            Path(roaming) / "AURA" / "ui"
        )

    unique = []
    seen = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if resolved.is_dir():
            unique.append(resolved)
    return tuple(unique)


def _iter_files():
    for base in _ui_roots():
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel_parts = {
                part.lower()
                for part in path.parts
            }
            if rel_parts & SKIP_PARTS:
                continue
            if (
                path.suffix.lower()
                not in TEXT_SUFFIXES
            ):
                continue
            try:
                if path.stat().st_size > 25_000_000:
                    continue
            except OSError:
                continue
            yield path


def _marker_windows(data: bytes):
    for marker in MARKERS:
        start = 0
        while True:
            idx = data.find(marker, start)
            if idx < 0:
                break
            left = max(0, idx - 320)
            right = min(
                len(data),
                idx + len(marker) + 320,
            )
            yield marker, left, right
            start = idx + len(marker)


def inspect():
    canonical = (
        "v" + str(AURA_VERSION).strip()
    ).encode("ascii")

    roots = [
        str(path)
        for path in _ui_roots()
    ]
    files_scanned = 0
    marker_hits = []
    stale_hits = []

    for path in _iter_files():
        files_scanned += 1
        try:
            data = path.read_bytes()
        except OSError:
            continue

        for marker, left, right in _marker_windows(data):
            window = data[left:right]
            versions = [
                match.group(0)
                for match in VERSION_RE.finditer(window)
            ]
            if not versions:
                continue

            decoded_versions = [
                item.decode("ascii", "replace")
                for item in versions
            ]
            hit = {
                "path": str(path),
                "marker": marker.decode(
                    "utf-8",
                    "replace",
                ),
                "versions": decoded_versions,
            }
            marker_hits.append(hit)

            for version in versions:
                if version != canonical:
                    stale_hits.append(
                        {
                            **hit,
                            "stale": version.decode(
                                "ascii",
                                "replace",
                            ),
                            "expected": canonical.decode(
                                "ascii",
                            ),
                        }
                    )

    return {
        "canonical_version": str(
            AURA_VERSION
        ),
        "display_version": (
            "v" + str(AURA_VERSION)
        ),
        "ui_roots": roots,
        "files_scanned": files_scanned,
        "marker_hits": marker_hits,
        "stale_hits": stale_hits,
        "pass": (
            len(roots) > 0
            and len(marker_hits) >= 2
            and not stale_hits
        ),
    }


def apply():
    canonical = (
        "v" + str(AURA_VERSION).strip()
    ).encode("ascii")

    changes = []
    for path in _iter_files():
        try:
            original = path.read_bytes()
        except OSError:
            continue

        data = original
        spans = []
        for marker, left, right in _marker_windows(data):
            window = data[left:right]
            for match in VERSION_RE.finditer(window):
                absolute_start = (
                    left + match.start()
                )
                absolute_end = (
                    left + match.end()
                )
                spans.append(
                    (
                        absolute_start,
                        absolute_end,
                        marker,
                        match.group(0),
                    )
                )

        # Replace from the end so offsets remain stable.
        replacements = []
        for (
            absolute_start,
            absolute_end,
            marker,
            version,
        ) in sorted(
            spans,
            key=lambda item: item[0],
            reverse=True,
        ):
            if version == canonical:
                continue
            data = (
                data[:absolute_start]
                + canonical
                + data[absolute_end:]
            )
            replacements.append(
                {
                    "marker": marker.decode(
                        "utf-8",
                        "replace",
                    ),
                    "from": version.decode(
                        "ascii",
                        "replace",
                    ),
                    "to": canonical.decode(
                        "ascii",
                    ),
                }
            )

        if data != original:
            path.write_bytes(data)
            changes.append(
                {
                    "path": str(path),
                    "replacements": list(
                        reversed(replacements)
                    ),
                }
            )

    result = inspect()
    result["changes"] = changes
    result["files_changed"] = len(changes)
    result["replacements"] = sum(
        len(item["replacements"])
        for item in changes
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
    )
    parser.add_argument(
        "--check",
        action="store_true",
    )
    parser.add_argument(
        "--json",
        action="store_true",
    )
    args = parser.parse_args()

    result = apply() if args.apply else inspect()

    if args.json:
        print(
            json.dumps(
                result,
                ensure_ascii=False,
            )
        )
    else:
        print(
            "display="
            + result["display_version"]
        )
        print(
            "roots="
            + str(len(result["ui_roots"]))
        )
        print(
            "markers="
            + str(len(result["marker_hits"]))
        )
        print(
            "stale="
            + str(len(result["stale_hits"]))
        )
        print(
            "pass="
            + str(result["pass"])
        )

    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
