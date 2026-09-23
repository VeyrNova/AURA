# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT_JSON = HERE / "AURA_PATCH_BACKUPS_DEEP_AUDIT_RESULT.json"
RESULT_TXT = HERE / "AURA_PATCH_BACKUPS_DEEP_AUDIT_RESULT.txt"

AURA_ROOT = Path(r"C:\AURA GPT version")
ROOT = AURA_ROOT / "_patch_backups"

# Safety contract: this script is strictly read-only.
READ_ONLY = True

# Recent backups are conservatively retained.
KEEP_RECENT_DAYS = 3
KEEP_NEWEST_GLOBAL = 3

def fmt_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:.2f} {u}"
        f /= 1024.0
    return f"{n} B"

def safe_stat(path: Path):
    try:
        return path.stat()
    except Exception:
        return None

def file_sha256(path: Path, chunk=1024 * 1024) -> str | None:
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            while True:
                b = f.read(chunk)
                if not b:
                    break
                h.update(b)
        return h.hexdigest()
    except Exception:
        return None

def scan_backup(folder: Path):
    files = []
    total = 0
    errors = 0
    newest = 0.0
    oldest = None

    stack = [folder]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        st = entry.stat(follow_symlinks=False)
                        mt = st.st_mtime
                        newest = max(newest, mt)
                        oldest = mt if oldest is None else min(oldest, mt)

                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            p = Path(entry.path)
                            rel = p.relative_to(folder).as_posix()
                            size = st.st_size
                            total += size
                            files.append({
                                "path": str(p),
                                "relative": rel,
                                "bytes": size,
                                "mtime": mt,
                                "sha256": None,
                            })
                    except Exception:
                        errors += 1
        except Exception:
            errors += 1

    return {
        "folder": str(folder),
        "name": folder.name,
        "bytes": total,
        "human": fmt_bytes(total),
        "files_count": len(files),
        "errors": errors,
        "newest_mtime": newest or None,
        "oldest_mtime": oldest,
        "files": files,
    }

def family_key(name: str) -> str:
    # Remove timestamps such as _20260815_073950 / -20260815-073950.
    s = re.sub(r"[_-]20\d{6}[_-]?\d{6}$", "", name, flags=re.I)
    s = re.sub(r"[_-]\d{8}[_-]\d{6}$", "", s, flags=re.I)
    # Normalize common version punctuation without collapsing distinct versions.
    return s.casefold()

def iso_ts(ts):
    if not ts:
        return None
    try:
        return dt.datetime.fromtimestamp(ts).isoformat(timespec="seconds")
    except Exception:
        return None

def age_days(ts, now_ts):
    if not ts:
        return None
    return max(0.0, (now_ts - ts) / 86400.0)

def folder_signature(file_rows):
    # Signature based on relative path + exact size + content sha256.
    h = hashlib.sha256()
    for r in sorted(file_rows, key=lambda x: x["relative"].casefold()):
        h.update(r["relative"].encode("utf-8", "surrogatepass"))
        h.update(b"\0")
        h.update(str(r["bytes"]).encode("ascii"))
        h.update(b"\0")
        h.update((r["sha256"] or "ERROR").encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()

def disk_space():
    try:
        d = shutil.disk_usage(str(AURA_ROOT))
        return {
            "total_bytes": d.total,
            "used_bytes": d.used,
            "free_bytes": d.free,
            "total": fmt_bytes(d.total),
            "used": fmt_bytes(d.used),
            "free": fmt_bytes(d.free),
            "free_percent": round(d.free / d.total * 100.0, 2) if d.total else None,
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}

def main():
    started = dt.datetime.now()
    now_ts = started.timestamp()

    result = {
        "schema": "aura.patch-backups-deep-audit.v1",
        "phase": "AURA _patch_backups Deep Audit — READ ONLY",
        "read_only": True,
        "deletions_performed": 0,
        "files_modified": 0,
        "aura_root": str(AURA_ROOT),
        "backup_root": str(ROOT),
        "started_at": started.isoformat(timespec="seconds"),
        "errors": [],
    }

    if not ROOT.exists():
        result["errors"].append("_patch_backups directory does not exist.")
        result["pass"] = False
        RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("[FAIL] _patch_backups introuvable.")
        return 2

    children = []
    try:
        top = [p for p in ROOT.iterdir() if p.is_dir()]
    except Exception as exc:
        result["errors"].append(f"ListError: {type(exc).__name__}: {exc}")
        result["pass"] = False
        RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 2

    # First pass: metadata + file sizes.
    for i, folder in enumerate(sorted(top, key=lambda p: p.name.casefold()), 1):
        print(f"[SCAN {i}/{len(top)}] {folder.name}")
        row = scan_backup(folder)
        row["family"] = family_key(folder.name)
        row["newest_iso"] = iso_ts(row["newest_mtime"])
        row["oldest_iso"] = iso_ts(row["oldest_mtime"])
        row["age_days"] = round(age_days(row["newest_mtime"], now_ts), 2) if row["newest_mtime"] else None
        children.append(row)

    # Build candidate hash groups by file size. Only hash sizes occurring in 2+ files.
    size_locations = defaultdict(list)
    for bi, b in enumerate(children):
        for fi, f in enumerate(b["files"]):
            size_locations[f["bytes"]].append((bi, fi))

    candidate_pairs = []
    for size, locs in size_locations.items():
        if len(locs) >= 2:
            candidate_pairs.extend(locs)

    # Avoid hashing the same file twice.
    unique_targets = sorted(set(candidate_pairs))
    print(f"[INFO] Hashing {len(unique_targets)} files with duplicate-size candidates...")
    for idx, (bi, fi) in enumerate(unique_targets, 1):
        f = children[bi]["files"][fi]
        f["sha256"] = file_sha256(Path(f["path"]))
        if idx % 200 == 0:
            print(f"  hashed {idx}/{len(unique_targets)}")

    # Files that were unique by size don't need content hash for cross-backup duplicate detection.
    # Hash them too only for folder exact signature, but only if folder can possibly match by file count+total bytes.
    shape_groups = defaultdict(list)
    for bi, b in enumerate(children):
        shape_groups[(b["files_count"], b["bytes"])].append(bi)

    folders_needing_full_hash = set()
    for shape, ids in shape_groups.items():
        if len(ids) >= 2:
            folders_needing_full_hash.update(ids)

    for bi in sorted(folders_needing_full_hash):
        for f in children[bi]["files"]:
            if f["sha256"] is None:
                f["sha256"] = file_sha256(Path(f["path"]))

    # Duplicate file analysis across different backups.
    hash_groups = defaultdict(list)
    for bi, b in enumerate(children):
        for f in b["files"]:
            if f["sha256"]:
                hash_groups[(f["bytes"], f["sha256"])].append((bi, f["relative"]))

    duplicated_bytes_by_backup = [0] * len(children)
    unique_bytes_by_backup = [0] * len(children)
    global_duplicate_payload = 0

    for key, locs in hash_groups.items():
        size, sha = key
        backup_ids = sorted(set(bi for bi, rel in locs))
        if len(backup_ids) >= 2:
            global_duplicate_payload += size * (len(backup_ids) - 1)
            for bi in backup_ids:
                duplicated_bytes_by_backup[bi] += size

    # Treat unhashed or non-duplicated files as unique for conservative estimate.
    for bi, b in enumerate(children):
        unique_bytes_by_backup[bi] = max(0, b["bytes"] - duplicated_bytes_by_backup[bi])
        b["duplicate_bytes"] = duplicated_bytes_by_backup[bi]
        b["duplicate_human"] = fmt_bytes(duplicated_bytes_by_backup[bi])
        b["unique_bytes"] = unique_bytes_by_backup[bi]
        b["unique_human"] = fmt_bytes(unique_bytes_by_backup[bi])
        b["duplicate_ratio"] = round((duplicated_bytes_by_backup[bi] / b["bytes"]), 4) if b["bytes"] else 0.0

    # Exact duplicate folder signatures, where full hashes are available.
    exact_groups = defaultdict(list)
    for bi in folders_needing_full_hash:
        b = children[bi]
        if all(f["sha256"] is not None for f in b["files"]):
            sig = folder_signature(b["files"])
            b["folder_signature"] = sig
            exact_groups[sig].append(bi)

    exact_duplicate_sets = []
    for sig, ids in exact_groups.items():
        if len(ids) >= 2:
            ids_sorted = sorted(ids, key=lambda i: children[i]["newest_mtime"] or 0, reverse=True)
            exact_duplicate_sets.append({
                "signature": sig,
                "backups": [children[i]["name"] for i in ids_sorted],
                "bytes_each": children[ids_sorted[0]]["bytes"],
                "human_each": children[ids_sorted[0]]["human"],
                "recoverable_if_keep_one_bytes": children[ids_sorted[0]]["bytes"] * (len(ids_sorted) - 1),
                "recoverable_if_keep_one": fmt_bytes(children[ids_sorted[0]]["bytes"] * (len(ids_sorted) - 1)),
            })

    # Conservative KEEP policy.
    ordered_newest = sorted(range(len(children)), key=lambda i: children[i]["newest_mtime"] or 0, reverse=True)
    keep_ids = set(ordered_newest[:KEEP_NEWEST_GLOBAL])

    families = defaultdict(list)
    for i, b in enumerate(children):
        families[b["family"]].append(i)
    for fam, ids in families.items():
        newest_id = max(ids, key=lambda i: children[i]["newest_mtime"] or 0)
        keep_ids.add(newest_id)

    for i, b in enumerate(children):
        if b["age_days"] is not None and b["age_days"] <= KEEP_RECENT_DAYS:
            keep_ids.add(i)

    # Exact duplicates: keep newest, mark older duplicate copies as SAFE_OLD_CANDIDATE unless already protected by KEEP.
    exact_old_ids = set()
    for group in exact_duplicate_sets:
        ids = [next(i for i,b in enumerate(children) if b["name"] == name) for name in group["backups"]]
        for old_id in ids[1:]:
            if old_id not in keep_ids:
                exact_old_ids.add(old_id)

    # High-duplicate conservative candidates.
    for i, b in enumerate(children):
        reasons = []
        if i in keep_ids:
            category = "KEEP"
            if i in ordered_newest[:KEEP_NEWEST_GLOBAL]:
                reasons.append("Among newest global backups")
            fam_ids = families[b["family"]]
            newest_fam = max(fam_ids, key=lambda x: children[x]["newest_mtime"] or 0)
            if i == newest_fam:
                reasons.append("Newest backup in its family")
            if b["age_days"] is not None and b["age_days"] <= KEEP_RECENT_DAYS:
                reasons.append(f"Recent backup <= {KEEP_RECENT_DAYS} days")
        elif i in exact_old_ids:
            category = "SAFE_OLD_CANDIDATE"
            reasons.append("Exact duplicate of a newer backup")
        elif b["duplicate_ratio"] >= 0.98 and b["unique_bytes"] <= 1024 * 1024:
            category = "SAFE_OLD_CANDIDATE"
            reasons.append(">=98% duplicated bytes and <=1 MB unique payload")
        else:
            category = "REVIEW"
            if b["duplicate_ratio"] >= 0.90:
                reasons.append("High duplicate ratio, but still has unique content")
            else:
                reasons.append("Contains materially unique content or no exact duplicate proof")

        b["classification"] = category
        b["classification_reasons"] = reasons

    # Remove per-file absolute paths from final report? Keep compact file summaries only.
    # Create duplicate-heavy file summaries while preserving enough evidence.
    for b in children:
        b["largest_files"] = [
            {
                "relative": f["relative"],
                "bytes": f["bytes"],
                "human": fmt_bytes(f["bytes"]),
            }
            for f in sorted(b["files"], key=lambda x: x["bytes"], reverse=True)[:15]
        ]
        del b["files"]

    total_bytes = sum(b["bytes"] for b in children)
    safe_bytes = sum(b["bytes"] for b in children if b["classification"] == "SAFE_OLD_CANDIDATE")
    review_bytes = sum(b["bytes"] for b in children if b["classification"] == "REVIEW")
    keep_bytes = sum(b["bytes"] for b in children if b["classification"] == "KEEP")

    # Top candidates sorted by size.
    candidates = sorted(
        [b for b in children if b["classification"] == "SAFE_OLD_CANDIDATE"],
        key=lambda b: b["bytes"],
        reverse=True,
    )
    review = sorted(
        [b for b in children if b["classification"] == "REVIEW"],
        key=lambda b: b["bytes"],
        reverse=True,
    )
    keep = sorted(
        [b for b in children if b["classification"] == "KEEP"],
        key=lambda b: b["newest_mtime"] or 0,
        reverse=True,
    )

    result.update({
        "disk": disk_space(),
        "top_level_backup_count": len(children),
        "total": {"bytes": total_bytes, "human": fmt_bytes(total_bytes)},
        "classification_totals": {
            "KEEP": {"count": len(keep), "bytes": keep_bytes, "human": fmt_bytes(keep_bytes)},
            "SAFE_OLD_CANDIDATE": {"count": len(candidates), "bytes": safe_bytes, "human": fmt_bytes(safe_bytes)},
            "REVIEW": {"count": len(review), "bytes": review_bytes, "human": fmt_bytes(review_bytes)},
        },
        "duplicate_analysis": {
            "global_duplicate_payload_bytes_conservative": global_duplicate_payload,
            "global_duplicate_payload_conservative": fmt_bytes(global_duplicate_payload),
            "exact_duplicate_sets": exact_duplicate_sets,
            "exact_duplicate_set_count": len(exact_duplicate_sets),
        },
        "backups": sorted(children, key=lambda b: b["bytes"], reverse=True),
        "safe_old_candidates": candidates,
        "review_candidates": review,
        "keep_candidates": keep,
        "policy": {
            "keep_recent_days": KEEP_RECENT_DAYS,
            "keep_newest_global": KEEP_NEWEST_GLOBAL,
            "keep_newest_per_family": True,
            "safe_candidate_exact_duplicate": True,
            "safe_candidate_high_duplicate_rule": ">=98% duplicate bytes AND <=1 MB unique bytes",
            "important": "SAFE_OLD_CANDIDATE is an audit recommendation only. This script performs no deletion.",
        },
        "finished_at": dt.datetime.now().isoformat(timespec="seconds"),
        "pass": True,
    })

    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("=" * 110)
    lines.append("AURA _PATCH_BACKUPS DEEP AUDIT — READ ONLY")
    lines.append("=" * 110)
    lines.append("")
    lines.append(f"Root               : {ROOT}")
    lines.append(f"Backup folders     : {len(children)}")
    lines.append(f"Total size         : {fmt_bytes(total_bytes)}")
    lines.append(f"Disk free          : {result['disk'].get('free','n/a')} ({result['disk'].get('free_percent','n/a')}%)")
    lines.append("")
    lines.append(f"KEEP               : {len(keep):>3} folders / {fmt_bytes(keep_bytes)}")
    lines.append(f"SAFE OLD CANDIDATE : {len(candidates):>3} folders / {fmt_bytes(safe_bytes)}")
    lines.append(f"REVIEW             : {len(review):>3} folders / {fmt_bytes(review_bytes)}")
    lines.append(f"Duplicate payload* : {fmt_bytes(global_duplicate_payload)}")
    lines.append("* Conservative cross-backup duplicate estimate; not automatically deletable.")
    lines.append("")

    lines.append("-" * 110)
    lines.append("LARGEST SAFE_OLD_CANDIDATE")
    lines.append("-" * 110)
    if not candidates:
        lines.append("(none)")
    for b in candidates[:30]:
        lines.append(
            f"{b['human']:>12}  dup={b['duplicate_ratio']*100:6.2f}%  unique={b['unique_human']:>10}  "
            f"age={str(b['age_days']):>6}d  {b['name']}"
        )
        lines.append("              " + "; ".join(b["classification_reasons"]))

    lines.append("")
    lines.append("-" * 110)
    lines.append("LARGEST REVIEW")
    lines.append("-" * 110)
    if not review:
        lines.append("(none)")
    for b in review[:30]:
        lines.append(
            f"{b['human']:>12}  dup={b['duplicate_ratio']*100:6.2f}%  unique={b['unique_human']:>10}  "
            f"age={str(b['age_days']):>6}d  {b['name']}"
        )

    lines.append("")
    lines.append("-" * 110)
    lines.append("KEEP")
    lines.append("-" * 110)
    if not keep:
        lines.append("(none)")
    for b in keep[:50]:
        lines.append(f"{b['human']:>12}  {b['newest_iso'] or 'n/a':19}  {b['name']}")
        lines.append("              " + "; ".join(b["classification_reasons"]))

    lines.append("")
    lines.append("=" * 110)
    lines.append("AUCUNE SUPPRESSION N'A ETE EFFECTUEE.")
    lines.append("=" * 110)

    RESULT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("")
    print("JSON :", RESULT_JSON)
    print("TXT  :", RESULT_TXT)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
