from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

SCHEMA = "aura.music-media-center.v180"


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _cf(value: Any) -> str:
    return _text(value).casefold()


def _num(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


@dataclass(frozen=True)
class MediaItem:
    media_id: str
    title: str
    artist: str
    media_type: str
    genre: str = ""
    album: str = ""
    duration_seconds: float = 0.0
    rating: float = 0.0
    play_count: int = 0
    path: str = ""

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "MediaItem":
        media_id = _text(row.get("media_id") or row.get("id"))
        title = _text(row.get("title"))
        artist = _text(row.get("artist") or row.get("creator"))
        media_type = _cf(row.get("media_type") or row.get("type") or "audio")
        if not media_id or not title:
            raise ValueError("media_id and title are required")
        if media_type not in {"audio", "video"}:
            raise ValueError("media_type must be audio or video")
        return cls(
            media_id=media_id,
            title=title,
            artist=artist,
            media_type=media_type,
            genre=_text(row.get("genre")),
            album=_text(row.get("album")),
            duration_seconds=max(0.0, _num(row.get("duration_seconds"))),
            rating=max(0.0, min(5.0, _num(row.get("rating")))),
            play_count=max(0, int(_num(row.get("play_count")))),
            path=_text(row.get("path")),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "media_id": self.media_id,
            "title": self.title,
            "artist": self.artist,
            "media_type": self.media_type,
            "genre": self.genre,
            "album": self.album,
            "duration_seconds": round(self.duration_seconds, 3),
            "rating": round(self.rating, 2),
            "play_count": self.play_count,
            "path": self.path,
        }


class MusicMediaCenter:
    def __init__(self, items: Iterable[Mapping[str, Any]]) -> None:
        self.items = [MediaItem.from_mapping(x) for x in items]

    def catalog_summary(self) -> dict[str, Any]:
        audio = [x for x in self.items if x.media_type == "audio"]
        video = [x for x in self.items if x.media_type == "video"]
        artists = {_cf(x.artist) for x in self.items if x.artist}
        genres = {_cf(x.genre) for x in self.items if x.genre}
        return {
            "schema": SCHEMA,
            "kind": "catalog_summary",
            "total": len(self.items),
            "audio": len(audio),
            "video": len(video),
            "artists": len(artists),
            "genres": len(genres),
            "read_only": True,
        }

    def search(
        self,
        query: str = "",
        *,
        media_type: str | None = None,
        genre: str | None = None,
        artist: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        q = _cf(query)
        mt = _cf(media_type) if media_type else ""
        g = _cf(genre) if genre else ""
        a = _cf(artist) if artist else ""
        limit = max(1, min(int(limit), 100))

        rows = []
        for item in self.items:
            hay = " ".join(
                _cf(x)
                for x in (
                    item.title,
                    item.artist,
                    item.album,
                    item.genre,
                )
            )
            if q and q not in hay:
                continue
            if mt and item.media_type != mt:
                continue
            if g and g not in _cf(item.genre):
                continue
            if a and a not in _cf(item.artist):
                continue
            rows.append(item)

        rows.sort(
            key=lambda x: (
                -x.rating,
                -x.play_count,
                _cf(x.artist),
                _cf(x.title),
            )
        )
        return {
            "schema": SCHEMA,
            "kind": "catalog_search",
            "count": min(len(rows), limit),
            "items": [x.as_dict() for x in rows[:limit]],
            "read_only": True,
        }

    def smart_queue(
        self,
        *,
        mood: str = "",
        genre: str = "",
        media_type: str = "audio",
        max_items: int = 10,
    ) -> dict[str, Any]:
        mood_key = _cf(mood)
        genre_key = _cf(genre)
        media_type = _cf(media_type or "audio")
        max_items = max(1, min(int(max_items), 50))

        scored = []
        for item in self.items:
            if item.media_type != media_type:
                continue
            score = 0.0
            reasons = []

            if genre_key and genre_key in _cf(item.genre):
                score += 30.0
                reasons.append("genre_match")

            hay = _cf(
                " ".join(
                    (item.title, item.artist, item.album, item.genre)
                )
            )
            if mood_key and mood_key in hay:
                score += 25.0
                reasons.append("mood_text_match")

            score += item.rating * 8.0
            if item.rating:
                reasons.append("rating")

            score += min(item.play_count, 50) * 0.4
            if item.play_count:
                reasons.append("history")

            scored.append((score, item, reasons))

        scored.sort(
            key=lambda x: (
                -x[0],
                -x[1].rating,
                _cf(x[1].title),
            )
        )

        return {
            "schema": SCHEMA,
            "kind": "smart_queue",
            "count": min(len(scored), max_items),
            "items": [
                {
                    **item.as_dict(),
                    "queue_score": round(score, 2),
                    "reasons": reasons,
                }
                for score, item, reasons in scored[:max_items]
            ],
            "explainable": True,
            "player_mutation_performed": False,
        }

    def playlist_proposal(
        self,
        name: str,
        *,
        query: str = "",
        genre: str = "",
        max_items: int = 20,
    ) -> dict[str, Any]:
        name = _text(name)
        if not name:
            raise ValueError("playlist name required")
        result = self.search(
            query,
            genre=genre or None,
            limit=max_items,
        )
        return {
            "schema": SCHEMA,
            "kind": "playlist_proposal",
            "name": name,
            "count": result["count"],
            "items": result["items"],
            "requires_explicit_confirmation": True,
            "external_playlist_write_performed": False,
            "filesystem_mutation_performed": False,
        }

    def playback_intent(
        self,
        media_id: str,
        *,
        action: str = "play",
    ) -> dict[str, Any]:
        action = _cf(action)
        if action not in {"play", "pause", "resume", "stop"}:
            raise ValueError("unsupported playback action")

        match = next(
            (x for x in self.items if x.media_id == str(media_id)),
            None,
        )
        if action == "play" and match is None:
            raise KeyError(media_id)

        return {
            "schema": SCHEMA,
            "kind": "playback_intent",
            "action": action,
            "media": match.as_dict() if match else None,
            "state": "approval_required",
            "requires_explicit_confirmation": True,
            "player_mutation_performed": False,
            "external_account_mutation_performed": False,
        }


def capability_snapshot() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "catalog_summary": True,
        "catalog_search": True,
        "smart_queue": True,
        "playlist_proposal": True,
        "playback_intent_plan": True,
        "real_player_control": False,
        "filesystem_delete": False,
        "filesystem_move": False,
        "filesystem_rename": False,
        "external_playlist_write": False,
        "external_account_mutation": False,
        "explicit_confirmation_required_for_future_player_mutation": True,
    }
