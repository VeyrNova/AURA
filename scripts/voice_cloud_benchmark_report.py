"""Read-only cloud TTS benchmark report for AURA v0.7.1.3.5.3.

Parses existing AURA logs only; it never calls a provider and therefore spends
no API credits. Useful after auditioning the same short sentence several times.
"""
from __future__ import annotations

import argparse
import re
import statistics
from dataclasses import dataclass
from pathlib import Path

GRADIUM_RE = re.compile(
    r"Gradium TTS transport=(?P<transport>\w+).*?first_audio=(?P<ttfa>\d+(?:\.\d+)?)s.*?total=(?P<total>\d+(?:\.\d+)?)s"
)
GRADIUM_WS_RE = re.compile(
    r"Gradium TTS transport=websocket.*?first_audio=(?P<ttfa>\d+(?:\.\d+)?)s.*?total=(?P<total>\d+(?:\.\d+)?)s"
)
ELEVEN_RE = re.compile(
    r"ElevenLabs TTS .*?ttfa=(?P<ttfa>\d+(?:\.\d+)?)s total=(?P<total>\d+(?:\.\d+)?)s"
)


@dataclass(frozen=True)
class Sample:
    provider: str
    transport: str
    ttfa: float
    total: float


def parse_samples(text: str) -> list[Sample]:
    samples: list[Sample] = []
    for line in text.splitlines():
        if "Gradium TTS transport=" in line:
            match = GRADIUM_RE.search(line) or GRADIUM_WS_RE.search(line)
            if match:
                transport_match = re.search(r"transport=(\w+)", line)
                samples.append(Sample("Gradium", transport_match.group(1) if transport_match else "?", float(match.group("ttfa")), float(match.group("total"))))
        elif "ElevenLabs TTS " in line:
            match = ELEVEN_RE.search(line)
            if match:
                samples.append(Sample("ElevenLabs", "stream", float(match.group("ttfa")), float(match.group("total"))))
    return samples


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * pct)))
    return ordered[idx]


def report(samples: list[Sample]) -> str:
    groups: dict[tuple[str, str], list[Sample]] = {}
    for sample in samples:
        groups.setdefault((sample.provider, sample.transport), []).append(sample)
    lines = ["AURA CLOUD VOICE BENCHMARK (lecture seule)", "=" * 66]
    if not groups:
        lines.append("Aucune métrique Gradium/ElevenLabs trouvée dans le journal.")
        return "\n".join(lines)
    lines.append(f"{'Provider':<14} {'Transport':<12} {'N':>3} {'TTFA med':>10} {'TTFA p95':>10} {'Total med':>11}")
    for (provider, transport), rows in sorted(groups.items()):
        ttfa = [r.ttfa for r in rows]
        total = [r.total for r in rows]
        lines.append(f"{provider:<14} {transport:<12} {len(rows):>3} {statistics.median(ttfa):>9.3f}s {percentile(ttfa, .95):>9.3f}s {statistics.median(total):>10.3f}s")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", nargs="?", default=str(Path(__file__).resolve().parents[1] / "logs" / "aura.log"))
    args = parser.parse_args()
    path = Path(args.log)
    if not path.exists():
        print(f"Journal introuvable: {path}")
        return 2
    print(report(parse_samples(path.read_text(encoding="utf-8", errors="replace"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
