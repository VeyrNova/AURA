"""Persistent XTTS speaker audition ratings for AURA v0.5.3."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from config.settings import settings


@dataclass
class VoiceRating:
    speaker: str
    naturality: int = 0
    warmth: int = 0
    sensuality: int = 0
    preference: int = 0
    favorite: bool = False
    notes: str = ""

    def normalized(self) -> "VoiceRating":
        for field in ("naturality", "warmth", "sensuality", "preference"):
            value = int(getattr(self, field, 0) or 0)
            setattr(self, field, max(0, min(5, value)))
        self.speaker = (self.speaker or "").strip()
        self.notes = (self.notes or "").strip()[:1000]
        self.favorite = bool(self.favorite)
        return self

    @property
    def score(self) -> float:
        values = [self.naturality, self.warmth, self.sensuality, self.preference]
        rated = [v for v in values if v > 0]
        if not rated:
            return 0.0
        # Preference matters a little more when choosing AURA's final voice.
        weighted_sum = (
            self.naturality * 1.0
            + self.warmth * 1.0
            + self.sensuality * 1.0
            + self.preference * 1.5
        )
        weighted_den = (
            (1.0 if self.naturality else 0.0)
            + (1.0 if self.warmth else 0.0)
            + (1.0 if self.sensuality else 0.0)
            + (1.5 if self.preference else 0.0)
        )
        return weighted_sum / weighted_den if weighted_den else 0.0


class VoiceAuditionStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (settings.CONFIG_DIR / "voice_audition.json")

    def load(self) -> dict[str, VoiceRating]:
        if not self.path.is_file():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return {}
            result: dict[str, VoiceRating] = {}
            for speaker, data in raw.items():
                if not isinstance(data, dict):
                    continue
                allowed = VoiceRating.__dataclass_fields__.keys()
                rating = VoiceRating(**{k: v for k, v in data.items() if k in allowed})
                if not rating.speaker:
                    rating.speaker = str(speaker)
                result[rating.speaker] = rating.normalized()
            return result
        except Exception:
            return {}

    def save_all(self, ratings: dict[str, VoiceRating]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            speaker: asdict(rating.normalized())
            for speaker, rating in sorted(ratings.items(), key=lambda item: item[0].casefold())
        }
        temp = self.path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def save_rating(self, rating: VoiceRating) -> None:
        ratings = self.load()
        rating = rating.normalized()
        ratings[rating.speaker] = rating
        self.save_all(ratings)

    def export_csv(self, destination: Path | None = None) -> Path:
        ratings = list(self.load().values())
        ratings.sort(key=lambda r: (r.favorite, r.score, r.preference, r.naturality), reverse=True)
        destination = destination or (settings.BASE_DIR / "exports" / "xtts_voice_ranking.csv")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow([
                "speaker",
                "score",
                "favorite",
                "naturality",
                "warmth",
                "sensuality",
                "preference",
                "notes",
            ])
            for rating in ratings:
                writer.writerow([
                    rating.speaker,
                    f"{rating.score:.2f}",
                    "yes" if rating.favorite else "no",
                    rating.naturality,
                    rating.warmth,
                    rating.sensuality,
                    rating.preference,
                    rating.notes,
                ])
        return destination
