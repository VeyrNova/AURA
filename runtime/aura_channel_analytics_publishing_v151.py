from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

SCHEMA = "aura.channel-analytics-publishing.v151"


class PublishingWorkflowError(RuntimeError):
    pass


def _f(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _i(value: Any) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return 0


def _median(values: Iterable[float]) -> float:
    rows = [float(v) for v in values]
    return float(statistics.median(rows)) if rows else 0.0


def _parse_dt(value: Any) -> datetime | None:
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


class ChannelAnalyticsPublishingWorkflows:
    def __init__(self, videos: Iterable[Mapping[str, Any]]) -> None:
        self.videos = [dict(v) for v in videos if isinstance(v, Mapping)]

    def _normalized(self) -> list[dict[str, Any]]:
        rows = []
        for row in self.videos:
            views = _i(row.get("views"))
            observation_days = max(1.0, _f(row.get("observation_days") or 1))
            duration = max(0.0, _f(row.get("duration_seconds")))
            avd = max(0.0, _f(row.get("average_view_duration_seconds")))
            retention = _f(row.get("average_view_percentage"))
            if retention <= 0 and duration > 0:
                retention = 100.0 * avd / duration

            engagement = 100.0 * (
                (_i(row.get("likes")) + _i(row.get("comments")))
                / max(1, views)
            )
            sub_conv = 100.0 * (
                _i(row.get("subscribers_gained")) / max(1, views)
            )
            fmt = str(row.get("format") or "video").strip().casefold()
            if fmt not in {"short", "video"}:
                fmt = "video"

            dt = _parse_dt(row.get("published_at"))
            rows.append({
                "video_id": str(row.get("video_id") or ""),
                "title": str(row.get("title") or ""),
                "format": fmt,
                "views": views,
                "views_per_day": views / observation_days,
                "retention_percent": retention,
                "engagement_percent": engagement,
                "subscriber_conversion_percent": sub_conv,
                "published_at": str(row.get("published_at") or ""),
                "weekday_utc": dt.strftime("%A") if dt else None,
                "hour_utc": dt.hour if dt else None,
            })
        return rows

    def compare_formats(self) -> dict[str, Any]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in self._normalized():
            groups[row["format"]].append(row)

        formats = {}
        for fmt in ("short", "video"):
            rows = groups.get(fmt, [])
            formats[fmt] = {
                "sample_size": len(rows),
                "median_views": round(_median(x["views"] for x in rows), 2),
                "median_views_per_day": round(
                    _median(x["views_per_day"] for x in rows), 2
                ),
                "median_retention_percent": round(
                    _median(x["retention_percent"] for x in rows), 2
                ),
                "median_engagement_percent": round(
                    _median(x["engagement_percent"] for x in rows), 3
                ),
                "median_subscriber_conversion_percent": round(
                    _median(
                        x["subscriber_conversion_percent"]
                        for x in rows
                    ),
                    4,
                ),
            }

        short = formats["short"]
        video = formats["video"]
        if short["sample_size"] and video["sample_size"]:
            reach_winner = (
                "short"
                if short["median_views_per_day"] >= video["median_views_per_day"]
                else "video"
            )
            retention_winner = (
                "short"
                if short["median_retention_percent"] >= video["median_retention_percent"]
                else "video"
            )
        else:
            reach_winner = "insufficient_data"
            retention_winner = "insufficient_data"

        return {
            "schema": SCHEMA,
            "kind": "format_comparison",
            "formats": formats,
            "reach_winner": reach_winner,
            "retention_winner": retention_winner,
            "read_only": True,
        }

    def publishing_windows(self) -> dict[str, Any]:
        rows = self._normalized()
        buckets: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if row["weekday_utc"] is not None and row["hour_utc"] is not None:
                buckets[(row["weekday_utc"], row["hour_utc"])].append(row)

        windows = []
        for (weekday, hour), bucket in buckets.items():
            windows.append({
                "weekday_utc": weekday,
                "hour_utc": hour,
                "sample_size": len(bucket),
                "median_views_per_day": round(
                    _median(x["views_per_day"] for x in bucket), 2
                ),
                "median_retention_percent": round(
                    _median(x["retention_percent"] for x in bucket), 2
                ),
            })

        windows.sort(
            key=lambda x: (
                -x["median_views_per_day"],
                -x["median_retention_percent"],
                x["weekday_utc"],
                x["hour_utc"],
            )
        )

        return {
            "schema": SCHEMA,
            "kind": "publishing_windows",
            "count": len(windows),
            "windows": windows,
            "note": "UTC-derived historical signal; not a causal guarantee.",
            "read_only": True,
        }

    def recommendation_matrix(self) -> dict[str, Any]:
        comparison = self.compare_formats()
        formats = comparison["formats"]

        rows = []
        for fmt in ("short", "video"):
            f = formats[fmt]
            rows.append({
                "format": fmt,
                "sample_size": f["sample_size"],
                "reach_score": round(f["median_views_per_day"], 2),
                "retention_score": round(f["median_retention_percent"], 2),
                "engagement_score": round(f["median_engagement_percent"], 3),
                "subscriber_conversion_score": round(
                    f["median_subscriber_conversion_percent"], 4
                ),
            })

        return {
            "schema": SCHEMA,
            "kind": "recommendation_matrix",
            "formats": rows,
            "recommended_for_reach": comparison["reach_winner"],
            "recommended_for_retention": comparison["retention_winner"],
            "read_only": True,
        }

    def editorial_mix(self, *, uploads_per_week: int = 3) -> dict[str, Any]:
        uploads_per_week = max(1, min(int(uploads_per_week), 14))
        comparison = self.compare_formats()
        short = comparison["formats"]["short"]
        video = comparison["formats"]["video"]

        if not short["sample_size"] and not video["sample_size"]:
            short_slots = uploads_per_week
        elif not video["sample_size"]:
            short_slots = uploads_per_week
        elif not short["sample_size"]:
            short_slots = 0
        else:
            short_signal = max(0.01, short["median_views_per_day"])
            video_signal = max(0.01, video["median_views_per_day"])
            share = short_signal / (short_signal + video_signal)
            short_slots = round(uploads_per_week * share)
            if uploads_per_week >= 2:
                short_slots = max(1, min(short_slots, uploads_per_week - 1))

        video_slots = uploads_per_week - short_slots

        return {
            "schema": SCHEMA,
            "kind": "editorial_mix",
            "uploads_per_week": uploads_per_week,
            "short_slots": short_slots,
            "long_form_slots": video_slots,
            "basis": "median historical views/day with diversity floor",
            "read_only": True,
        }

    def create_publishing_workflow(
        self,
        *,
        title: str,
        format: str,
        description: str = "",
        scheduled_for: str | None = None,
    ) -> dict[str, Any]:
        title = str(title or "").strip()
        fmt = str(format or "").strip().casefold()
        description = str(description or "").strip()

        errors = []
        if not title:
            errors.append("title_required")
        if fmt not in {"short", "video"}:
            errors.append("format_must_be_short_or_video")
        if scheduled_for and _parse_dt(scheduled_for) is None:
            errors.append("scheduled_for_invalid")

        ready = not errors
        state = "approval_required" if ready else "draft_invalid"

        return {
            "schema": SCHEMA,
            "kind": "publishing_workflow",
            "state": state,
            "ready_for_review": ready,
            "requires_explicit_confirmation": True,
            "external_mutation_performed": False,
            "youtube_upload_performed": False,
            "youtube_edit_performed": False,
            "youtube_delete_performed": False,
            "youtube_comment_reply_performed": False,
            "draft": {
                "title": title,
                "format": fmt,
                "description": description,
                "scheduled_for": scheduled_for,
            },
            "validation_errors": errors,
            "gates": [
                "metadata_review",
                "asset_review",
                "copyright_review",
                "explicit_user_confirmation",
                "provider_write_capability_required",
                "canonical_action_receipt_required",
            ],
        }


def capability_snapshot() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "read_only_analytics": [
            "channel.compare_formats",
            "channel.publishing_windows",
            "channel.recommendation_matrix",
            "channel.editorial_mix",
        ],
        "controlled_workflow_planning": [
            "publishing.create_workflow_plan",
        ],
        "external_mutating_capabilities": [],
        "youtube_upload": False,
        "youtube_edit": False,
        "youtube_delete": False,
        "youtube_comment_reply": False,
        "explicit_confirmation_required_for_future_publish": True,
        "canonical_receipt_required_for_future_publish": True,
    }
