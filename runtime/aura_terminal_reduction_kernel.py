
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
import hashlib
import json
import os
import re
import time

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
PROGRESS_RE = re.compile(r"^\s*(?:\d{1,3}%|[\[\]#=>.\-]{8,}|.*\b(?:download(?:ing)?|upload(?:ing)?|building|compiling|installing)\b.*\d{1,3}%.*)$", re.I)
SIGNAL_RE = re.compile(r"\b(error|failed|failure|fatal|exception|traceback|warning|warn|assert|panic|denied|not found)\b", re.I)
PATH_RE = re.compile(r"(?P<path>(?:[A-Za-z]:\\|/)[^\s:'\"]+)")
SECRETISH_RE = re.compile(r"(?i)\b(api[_-]?key|token|secret|password|authorization)\b\s*[:=]\s*\S+")

@dataclass(frozen=True)
class ReductionResult:
    command: str
    mode: str
    raw_bytes: int
    reduced_bytes: int
    estimated_raw_tokens: int
    estimated_reduced_tokens: int
    savings_percent: float
    raw_sha256: str
    output: str
    signal_lines_preserved: int
    filtered_lines: int

    def receipt(self) -> dict:
        d = asdict(self)
        d.pop("output", None)
        return d

def estimate_tokens(text: str) -> int:
    return 0 if not text else max(1, (len(text.encode("utf-8")) + 3) // 4)

def _sanitize(text: str) -> str:
    text = ANSI_RE.sub("", text).replace("\r\n", "\n").replace("\r", "\n")
    return SECRETISH_RE.sub(lambda m: m.group(1) + "=<redacted>", text)

def _dedupe(lines: list[str]) -> tuple[list[str], int]:
    out=[]; filtered=0; prev=None; count=0
    for line in lines:
        if line == prev:
            count += 1; filtered += 1; continue
        if count:
            out.append(f"[AURA TRK] previous line repeated {count}x")
            count=0
        out.append(line); prev=line
    if count:
        out.append(f"[AURA TRK] previous line repeated {count}x")
    return out, filtered

def reduce_terminal_output(command: str, raw_output: str, *, min_bytes: int = 1200, max_lines: int = 160) -> ReductionResult:
    clean=_sanitize(raw_output)
    raw_bytes=len(clean.encode("utf-8"))
    raw_hash=hashlib.sha256(clean.encode("utf-8")).hexdigest()
    lines=clean.splitlines()

    if raw_bytes < min_bytes or SIGNAL_RE.search(clean) and len(lines) <= 80:
        output=clean
        return ReductionResult(command,"passthrough_safe",raw_bytes,raw_bytes,estimate_tokens(clean),estimate_tokens(clean),0.0,raw_hash,output,sum(bool(SIGNAL_RE.search(x)) for x in lines),0)

    kept=[]; filtered=0; signal_count=0; progress_seen=0
    for line in lines:
        if SIGNAL_RE.search(line):
            kept.append(line); signal_count += 1; continue
        if PROGRESS_RE.match(line):
            progress_seen += 1; filtered += 1; continue
        if not line.strip():
            if kept and kept[-1] == "":
                filtered += 1; continue
        kept.append(line.rstrip())

    kept, dup_filtered = _dedupe(kept); filtered += dup_filtered
    if progress_seen:
        kept.insert(0, f"[AURA TRK] collapsed {progress_seen} progress/noise lines")

    if len(kept) > max_lines:
        signal_indexes=[i for i,x in enumerate(kept) if SIGNAL_RE.search(x)]
        head=kept[:50]; tail=kept[-50:]
        middle_signals=[kept[i] for i in signal_indexes if i >= 50 and i < len(kept)-50][:50]
        omitted=max(0,len(kept)-len(head)-len(tail)-len(middle_signals))
        kept=head + ([f"[AURA TRK] ... {omitted} low-signal lines omitted ..."] if omitted else []) + middle_signals + tail
        filtered += omitted

    output="\n".join(kept)
    if clean.endswith("\n") and output:
        output += "\n"
    reduced_bytes=len(output.encode("utf-8"))
    savings=0.0 if raw_bytes==0 else max(0.0,(raw_bytes-reduced_bytes)*100.0/raw_bytes)
    return ReductionResult(command,"conservative",raw_bytes,reduced_bytes,estimate_tokens(clean),estimate_tokens(output),round(savings,2),raw_hash,output,signal_count,filtered)

class SavingsLedger:
    def __init__(self, path: Path):
        self.path=Path(path)

    def append(self, result: ReductionResult, *, exit_code: int | None=None) -> None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        item={"ts":int(time.time()),**result.receipt(),"exit_code":exit_code}
        with self.path.open("a",encoding="utf-8") as f:
            f.write(json.dumps(item,ensure_ascii=False,separators=(",",":"))+"\n")

    def summary(self) -> dict:
        total_raw=total_reduced=commands=0
        if self.path.is_file():
            for line in self.path.read_text(encoding="utf-8",errors="ignore").splitlines():
                try: item=json.loads(line)
                except Exception: continue
                total_raw += int(item.get("raw_bytes") or 0)
                total_reduced += int(item.get("reduced_bytes") or 0)
                commands += 1
        savings=0.0 if total_raw==0 else (total_raw-total_reduced)*100.0/total_raw
        return {"schema":"aura.trk.savings.v1","commands":commands,"raw_bytes":total_raw,"reduced_bytes":total_reduced,"output_byte_reduction_percent":round(savings,2),"estimated_tokens_saved":max(0,(total_raw-total_reduced)//4)}

def default_savings_summary() -> dict:
    root=Path(os.environ.get("AURA_ROOT") or Path(__file__).resolve().parents[1]).resolve()
    return SavingsLedger(root/"runtime"/"developer_fabric"/"trk"/"savings.jsonl").summary()
