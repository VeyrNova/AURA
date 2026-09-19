from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

SCHEMA = "aura.youtube-studio-copilot.v150"


class YouTubeCopilotError(RuntimeError):
    pass


def _f(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _i(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return default


def _safe_div(a: float, b: float) -> float:
    return (a / b) if b else 0.0


def _median(values: Iterable[float]) -> float:
    rows = [float(x) for x in values if math.isfinite(float(x))]
    return float(statistics.median(rows)) if rows else 0.0


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class VideoRecord:
    video_id: str
    title: str
    published_at: str
    views: int
    likes: int = 0
    comments: int = 0
    subscribers_gained: int = 0
    impressions: int = 0
    ctr_percent: float = 0.0
    average_view_duration_seconds: float = 0.0
    duration_seconds: float = 0.0
    tags: tuple[str, ...] = ()
    format: str = "video"

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "VideoRecord":
        tags = row.get("tags") or ()
        if isinstance(tags, str):
            tags = tuple(x.strip() for x in tags.split(",") if x.strip())
        elif isinstance(tags, (list, tuple, set)):
            tags = tuple(str(x).strip() for x in tags if str(x).strip())
        else:
            tags = ()
        return cls(
            video_id=str(row.get("video_id") or row.get("id") or "").strip(),
            title=str(row.get("title") or "").strip(),
            published_at=str(row.get("published_at") or row.get("published") or "").strip(),
            views=_i(row.get("views")),
            likes=_i(row.get("likes")),
            comments=_i(row.get("comments")),
            subscribers_gained=_i(row.get("subscribers_gained")),
            impressions=_i(row.get("impressions")),
            ctr_percent=max(0.0, _f(row.get("ctr_percent") or row.get("ctr"))),
            average_view_duration_seconds=max(
                0.0,
                _f(
                    row.get("average_view_duration_seconds")
                    or row.get("avg_view_duration_seconds")
                ),
            ),
            duration_seconds=max(0.0, _f(row.get("duration_seconds"))),
            tags=tags,
            format=str(row.get("format") or "video").strip().casefold(),
        )

    def normalized(self, *, now: datetime | None = None) -> dict[str, Any]:
        dt = _parse_dt(self.published_at)
        now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        age_days = max(
            1.0,
            ((now_utc - dt).total_seconds() / 86400.0) if dt else 1.0,
        )
        retention = (
            100.0
            * _safe_div(
                self.average_view_duration_seconds,
                self.duration_seconds,
            )
            if self.duration_seconds > 0
            else 0.0
        )
        engagement = 100.0 * _safe_div(
            self.likes + self.comments,
            max(1, self.views),
        )
        subscriber_conversion = 100.0 * _safe_div(
            self.subscribers_gained,
            max(1, self.views),
        )
        return {
            "video_id": self.video_id,
            "title": self.title,
            "published_at": self.published_at,
            "age_days": round(age_days, 2),
            "views": self.views,
            "views_per_day": round(self.views / age_days, 3),
            "likes": self.likes,
            "comments": self.comments,
            "engagement_percent": round(engagement, 3),
            "subscribers_gained": self.subscribers_gained,
            "subscriber_conversion_percent": round(subscriber_conversion, 4),
            "impressions": self.impressions,
            "ctr_percent": round(self.ctr_percent, 3),
            "average_view_duration_seconds": round(
                self.average_view_duration_seconds, 2
            ),
            "duration_seconds": round(self.duration_seconds, 2),
            "retention_percent": round(max(0.0, min(retention, 200.0)), 3),
            "tags": list(self.tags),
            "format": self.format,
        }


class YouTubeStudioCopilot:
    def __init__(
        self,
        videos: Iterable[VideoRecord | Mapping[str, Any]],
        *,
        channel_name: str = "",
        now: datetime | None = None,
    ) -> None:
        self.channel_name = str(channel_name or "").strip()
        self.now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        self.videos = [
            x if isinstance(x, VideoRecord) else VideoRecord.from_mapping(x)
            for x in videos
        ]

    def _rows(self) -> list[dict[str, Any]]:
        return [v.normalized(now=self.now) for v in self.videos]

    def benchmarks(self) -> dict[str, Any]:
        rows = self._rows()
        return {
            "schema": SCHEMA,
            "kind": "benchmarks",
            "channel_name": self.channel_name,
            "video_count": len(rows),
            "median_views": round(_median(x["views"] for x in rows), 3),
            "median_views_per_day": round(
                _median(x["views_per_day"] for x in rows), 3
            ),
            "median_ctr_percent": round(
                _median(x["ctr_percent"] for x in rows if x["impressions"] > 0),
                3,
            ),
            "median_retention_percent": round(
                _median(
                    x["retention_percent"]
                    for x in rows
                    if x["duration_seconds"] > 0
                ),
                3,
            ),
            "median_engagement_percent": round(
                _median(x["engagement_percent"] for x in rows),
                3,
            ),
            "read_only": True,
        }

    def scorecards(self) -> list[dict[str, Any]]:
        rows = self._rows()
        bench = self.benchmarks()

        def ratio(value: float, base: float) -> float:
            if base <= 0:
                return 1.0 if value > 0 else 0.0
            return max(0.0, min(value / base, 3.0))

        out = []
        for row in rows:
            components = {
                "view_velocity": ratio(
                    row["views_per_day"],
                    bench["median_views_per_day"],
                ),
                "ctr": ratio(row["ctr_percent"], bench["median_ctr_percent"]),
                "retention": ratio(
                    row["retention_percent"],
                    bench["median_retention_percent"],
                ),
                "engagement": ratio(
                    row["engagement_percent"],
                    bench["median_engagement_percent"],
                ),
            }
            score = 100.0 * (
                0.35 * components["view_velocity"]
                + 0.25 * components["ctr"]
                + 0.25 * components["retention"]
                + 0.15 * components["engagement"]
            ) / 3.0
            out.append({
                **row,
                "score": round(max(0.0, min(score, 100.0)), 2),
                "score_components": {
                    k: round(v, 3) for k, v in components.items()
                },
            })
        out.sort(
            key=lambda x: (-x["score"], -x["views_per_day"], x["title"].casefold())
        )
        return out

    def opportunity_board(self) -> dict[str, Any]:
        bench = self.benchmarks()
        rows = self.scorecards()
        items = []
        for row in rows:
            ctr = row["ctr_percent"]
            retention = row["retention_percent"]
            velocity = row["views_per_day"]
            impressions = row["impressions"]

            if (
                ctr >= bench["median_ctr_percent"]
                and retention >= bench["median_retention_percent"]
                and velocity >= bench["median_views_per_day"]
            ):
                action = "double_down"
                reason = "CTR, retention et vitesse de vues au-dessus des medianes."
            elif (
                impressions > 0
                and bench["median_ctr_percent"] > 0
                and ctr < bench["median_ctr_percent"]
            ):
                action = "packaging"
                reason = "Impressions presentes mais CTR sous la mediane: titre/miniature a tester."
            elif (
                ctr >= bench["median_ctr_percent"]
                and retention < bench["median_retention_percent"]
            ):
                action = "hook_retention"
                reason = "Le packaging attire mais la retention sous-performe."
            elif (
                ctr >= bench["median_ctr_percent"]
                and retention >= bench["median_retention_percent"]
                and velocity < bench["median_views_per_day"]
            ):
                action = "distribution"
                reason = "Signaux qualite solides mais vitesse de vues faible."
            else:
                action = "monitor"
                reason = "Aucun signal dominant par rapport aux medianes."

            items.append({
                "video_id": row["video_id"],
                "title": row["title"],
                "score": row["score"],
                "action": action,
                "reason": reason,
                "metrics": {
                    "views_per_day": row["views_per_day"],
                    "ctr_percent": ctr,
                    "retention_percent": retention,
                    "engagement_percent": row["engagement_percent"],
                },
            })
        return {
            "schema": SCHEMA,
            "kind": "opportunity_board",
            "channel_name": self.channel_name,
            "benchmarks": bench,
            "count": len(items),
            "items": items,
            "read_only": True,
        }

    def publishing_cadence(self) -> dict[str, Any]:
        dated = []
        for v in self.videos:
            dt = _parse_dt(v.published_at)
            if dt:
                dated.append((dt, v.title))
        dated.sort()
        gaps = [
            (dated[i][0] - dated[i - 1][0]).total_seconds() / 86400.0
            for i in range(1, len(dated))
        ]
        return {
            "schema": SCHEMA,
            "kind": "publishing_cadence",
            "channel_name": self.channel_name,
            "dated_video_count": len(dated),
            "median_gap_days": round(_median(gaps), 2),
            "average_gap_days": round(
                (sum(gaps) / len(gaps)) if gaps else 0.0,
                2,
            ),
            "min_gap_days": round(min(gaps), 2) if gaps else 0.0,
            "max_gap_days": round(max(gaps), 2) if gaps else 0.0,
            "read_only": True,
        }

    def next_upload_brief(self) -> dict[str, Any]:
        board = self.opportunity_board()
        scored = self.scorecards()
        tag_scores: dict[str, list[float]] = {}
        for row in scored:
            for tag in row.get("tags") or []:
                tag_scores.setdefault(str(tag).casefold(), []).append(row["score"])
        ranked_tags = sorted(
            (
                {
                    "tag": tag,
                    "mean_score": round(sum(vals) / len(vals), 2),
                    "sample_size": len(vals),
                }
                for tag, vals in tag_scores.items()
            ),
            key=lambda x: (-x["mean_score"], -x["sample_size"], x["tag"]),
        )
        top = scored[:3]
        return {
            "schema": SCHEMA,
            "kind": "next_upload_brief",
            "channel_name": self.channel_name,
            "top_reference_videos": [
                {
                    "video_id": x["video_id"],
                    "title": x["title"],
                    "score": x["score"],
                }
                for x in top
            ],
            "priority_topics": ranked_tags[:8],
            "recommended_focus": (
                "Repliquer les sujets/angles des meilleures videos sans copier le titre."
                if top
                else "Pas assez de donnees pour recommander un angle."
            ),
            "packaging_watch": [
                x["title"]
                for x in board["items"]
                if x["action"] == "packaging"
            ][:5],
            "retention_watch": [
                x["title"]
                for x in board["items"]
                if x["action"] == "hook_retention"
            ][:5],
            "cadence": self.publishing_cadence(),
            "read_only": True,
        }

    def channel_snapshot(self) -> dict[str, Any]:
        rows = self.scorecards()
        return {
            "schema": SCHEMA,
            "kind": "channel_snapshot",
            "channel_name": self.channel_name,
            "video_count": len(rows),
            "total_views": sum(x["views"] for x in rows),
            "total_likes": sum(x["likes"] for x in rows),
            "total_comments": sum(x["comments"] for x in rows),
            "total_subscribers_gained": sum(
                x["subscribers_gained"] for x in rows
            ),
            "benchmarks": self.benchmarks(),
            "top_videos": rows[:10],
            "read_only": True,
        }


def capability_snapshot() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capabilities": [
            "youtube.channel_snapshot",
            "youtube.benchmarks",
            "youtube.scorecards",
            "youtube.opportunity_board",
            "youtube.publishing_cadence",
            "youtube.next_upload_brief",
        ],
        "mutating_capabilities": [],
        "upload_video": False,
        "edit_video": False,
        "delete_video": False,
        "reply_comment": False,
        "read_only": True,
        "explainable_scoring": True,
    }
