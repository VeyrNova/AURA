from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from runtime.aura_obsidian_creative_studio_v140 import (
    ObsidianCreativeStudio,
    ObsidianStudioError,
)

SCHEMA = "aura.longform-revision.v141"


def _words(text: str) -> int:
    return len(re.findall(r"\b[\w\u00c0-\u024f'-]+\b", str(text or ""), flags=re.UNICODE))


def _chapter_number(title: str, path: str) -> int | None:
    for value in (str(title or ""), Path(path).stem):
        m = re.search(r"\b(?:chapter|chapitre)?\s*0*(\d{1,4})\b", value, flags=re.I)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
    return None


def _excerpt(text: str, limit: int = 900) -> str:
    plain = re.sub(r"\s+", " ", str(text or "")).strip()
    return plain[: max(120, min(int(limit), 3000))]


class LongFormRevisionStudio:
    def __init__(self, vault_path: str | Path) -> None:
        self.obsidian = ObsidianCreativeStudio(vault_path)
        self.vault = self.obsidian.vault
        self.obsidian.build_index()
        self.notes = list(self.obsidian.notes)
        self._by_path = {n.relative_path.casefold(): n for n in self.notes}
        self._by_stem = {}
        for note in self.notes:
            self._by_stem.setdefault(Path(note.relative_path).stem.casefold(), []).append(note)
            self._by_stem.setdefault(note.title.casefold(), []).append(note)
            for alias in note.aliases:
                self._by_stem.setdefault(alias.casefold(), []).append(note)

    def _chapters(self):
        rows = [n for n in self.notes if n.note_type == "chapter"]
        rows.sort(
            key=lambda n: (
                _chapter_number(n.title, n.relative_path) is None,
                _chapter_number(n.title, n.relative_path) or 10**9,
                n.relative_path.casefold(),
            )
        )
        return rows

    def _typed_links(self, note) -> dict[str, list[str]]:
        out = {
            "characters": [],
            "locations": [],
            "world": [],
            "scenes": [],
            "continuity": [],
            "other": [],
        }
        mapping = {
            "character": "characters",
            "location": "locations",
            "world": "world",
            "scene": "scenes",
            "continuity": "continuity",
        }
        for link in note.wikilinks:
            candidates = self._by_stem.get(Path(link).stem.casefold()) or []
            if not candidates:
                out["other"].append(link)
                continue
            target = candidates[0]
            out[mapping.get(target.note_type, "other")].append(target.title)
        for key in out:
            out[key] = sorted(set(out[key]), key=str.casefold)
        return out

    def manuscript_outline(self) -> dict[str, Any]:
        chapters = self._chapters()
        rows = []
        total_words = 0
        for index, note in enumerate(chapters):
            wc = _words(note.body)
            total_words += wc
            rows.append({
                "index": index + 1,
                "chapter_number": _chapter_number(note.title, note.relative_path),
                "title": note.title,
                "relative_path": note.relative_path,
                "word_count": wc,
                "headings": list(note.headings),
                "references": self._typed_links(note),
            })
        return {
            "schema": SCHEMA,
            "kind": "manuscript_outline",
            "vault": str(self.vault),
            "chapter_count": len(rows),
            "total_words": total_words,
            "chapters": rows,
            "read_only": True,
        }

    def chapter_context(self, relative_path: str, *, radius: int = 1) -> dict[str, Any]:
        chapters = self._chapters()
        key = str(relative_path or "").replace("\\", "/").casefold()
        pos = None
        for i, note in enumerate(chapters):
            if note.relative_path.casefold() == key:
                pos = i
                break
        if pos is None:
            raise ObsidianStudioError(f"chapter not found: {relative_path}")

        radius = max(0, min(int(radius), 3))
        start = max(0, pos - radius)
        end = min(len(chapters), pos + radius + 1)
        rows = []
        for i in range(start, end):
            note = chapters[i]
            role = "current" if i == pos else ("previous" if i < pos else "next")
            rows.append({
                "role": role,
                "title": note.title,
                "relative_path": note.relative_path,
                "word_count": _words(note.body),
                "excerpt": _excerpt(note.body),
                "references": self._typed_links(note),
            })
        return {
            "schema": SCHEMA,
            "kind": "chapter_context",
            "target": chapters[pos].relative_path,
            "radius": radius,
            "chapters": rows,
            "read_only": True,
        }

    def continuity_audit(self) -> dict[str, Any]:
        chapters = self._chapters()
        issues = []

        title_map = {}
        for note in self.notes:
            title_map.setdefault(note.title.casefold(), []).append(note.relative_path)
        for title_key, paths in sorted(title_map.items()):
            if title_key and len(paths) > 1:
                issues.append({
                    "severity": "warning",
                    "code": "duplicate_title",
                    "title": self._by_path[paths[0].casefold()].title if paths[0].casefold() in self._by_path else title_key,
                    "paths": paths,
                })

        unresolved = []
        for note in self.notes:
            for link in note.wikilinks:
                if Path(link).stem.casefold() not in self._by_stem:
                    unresolved.append({"from": note.relative_path, "link": link})
        for row in unresolved[:500]:
            issues.append({
                "severity": "warning",
                "code": "unresolved_wikilink",
                **row,
            })

        numbered = []
        for note in chapters:
            num = _chapter_number(note.title, note.relative_path)
            if num is not None:
                numbered.append((num, note.relative_path))
        if len(numbered) >= 2:
            nums = sorted(set(n for n, _ in numbered))
            for expected in range(nums[0], nums[-1] + 1):
                if expected not in nums:
                    issues.append({
                        "severity": "info",
                        "code": "chapter_sequence_gap",
                        "chapter_number": expected,
                    })

        return {
            "schema": SCHEMA,
            "kind": "continuity_audit",
            "vault": str(self.vault),
            "chapter_count": len(chapters),
            "note_count": len(self.notes),
            "issue_count": len(issues),
            "issues": issues,
            "read_only": True,
        }

    def revision_brief(self, relative_path: str) -> dict[str, Any]:
        context = self.chapter_context(relative_path, radius=1)
        current = next(x for x in context["chapters"] if x["role"] == "current")
        audit = self.continuity_audit()

        related_issues = []
        target = str(relative_path or "").casefold()
        for issue in audit["issues"]:
            if str(issue.get("from") or "").casefold() == target:
                related_issues.append(issue)
            elif any(str(x).casefold() == target for x in (issue.get("paths") or [])):
                related_issues.append(issue)

        return {
            "schema": SCHEMA,
            "kind": "revision_brief",
            "target": relative_path,
            "title": current["title"],
            "word_count": current["word_count"],
            "references": current["references"],
            "context": context["chapters"],
            "related_issues": related_issues,
            "checks": {
                "has_previous_context": any(x["role"] == "previous" for x in context["chapters"]),
                "has_next_context": any(x["role"] == "next" for x in context["chapters"]),
                "has_character_references": bool(current["references"]["characters"]),
                "has_location_references": bool(current["references"]["locations"]),
            },
            "read_only": True,
        }

    def context_search_pack(self, query: str, *, limit: int = 8) -> dict[str, Any]:
        found = self.obsidian.search_context(query, limit=max(1, min(int(limit), 20)))
        rows = []
        for item in found.get("results") or []:
            rel = str(item.get("relative_path") or "")
            row = dict(item)
            if str(item.get("note_type") or "") == "chapter":
                try:
                    row["chapter_context"] = self.chapter_context(rel, radius=1)["chapters"]
                except Exception:
                    row["chapter_context"] = []
            rows.append(row)
        return {
            "schema": SCHEMA,
            "kind": "context_search_pack",
            "query": str(query or ""),
            "count": len(rows),
            "results": rows,
            "read_only": True,
        }


def capability_snapshot() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capabilities": [
            "longform.manuscript_outline",
            "longform.chapter_context",
            "longform.continuity_audit",
            "longform.revision_brief",
            "longform.context_search_pack",
        ],
        "mutating_capabilities": [],
        "note_write": False,
        "note_delete": False,
        "read_only": True,
    }

# AURA_O141_R3_REVISION_INTELLIGENCE


def _o141_r3_unresolved_for_note(self, note):
    return sorted({
        link
        for link in note.wikilinks
        if Path(link).stem.casefold() not in self._by_stem
    }, key=str.casefold)


def _o141_r3_note_by_path(self, relative_path):
    key = str(relative_path or "").replace("\\", "/").casefold()
    note = self._by_path.get(key)
    if note is None:
        raise ObsidianStudioError(f"note not found: {relative_path}")
    return note


def _o141_r3_transition(self, from_relative_path, to_relative_path):
    left = _o141_r3_note_by_path(self, from_relative_path)
    right = _o141_r3_note_by_path(self, to_relative_path)
    if left.note_type != "chapter" or right.note_type != "chapter":
        raise ObsidianStudioError("chapter transition requires chapter notes")

    a = self._typed_links(left)
    b = self._typed_links(right)

    def delta(key):
        av = set(a.get(key) or [])
        bv = set(b.get(key) or [])
        return {
            "shared": sorted(av & bv, key=str.casefold),
            "introduced": sorted(bv - av, key=str.casefold),
            "dropped": sorted(av - bv, key=str.casefold),
        }

    return {
        "schema": SCHEMA,
        "kind": "chapter_transition",
        "from": {
            "title": left.title,
            "relative_path": left.relative_path,
            "word_count": _words(left.body),
        },
        "to": {
            "title": right.title,
            "relative_path": right.relative_path,
            "word_count": _words(right.body),
        },
        "word_count_delta": _words(right.body) - _words(left.body),
        "characters": delta("characters"),
        "locations": delta("locations"),
        "world": delta("world"),
        "unresolved_from": _o141_r3_unresolved_for_note(self, left),
        "unresolved_to": _o141_r3_unresolved_for_note(self, right),
        "read_only": True,
    }


def _o141_r3_chapter_revision_report(self, relative_path):
    context = self.chapter_context(relative_path, radius=1)
    current_row = next(x for x in context["chapters"] if x["role"] == "current")
    note = _o141_r3_note_by_path(self, relative_path)
    chapters = self._chapters()
    pos = next(i for i, x in enumerate(chapters) if x.relative_path == note.relative_path)

    transition_in = (
        self.chapter_transition(chapters[pos - 1].relative_path, note.relative_path)
        if pos > 0 else None
    )
    transition_out = (
        self.chapter_transition(note.relative_path, chapters[pos + 1].relative_path)
        if pos + 1 < len(chapters) else None
    )

    body = str(note.body or "")
    paragraphs = [x.strip() for x in re.split(r"\n\s*\n", body) if x.strip()]
    sentences = [
        x.strip()
        for x in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", body).strip())
        if x.strip()
    ]
    word_count = _words(body)
    sentence_words = [_words(x) for x in sentences] or [0]

    audit = self.continuity_audit()
    related = []
    for issue in audit.get("issues") or []:
        if str(issue.get("from") or "").casefold() == note.relative_path.casefold():
            related.append(issue)
        elif any(
            str(x).casefold() == note.relative_path.casefold()
            for x in (issue.get("paths") or [])
        ):
            related.append(issue)

    return {
        "schema": SCHEMA,
        "kind": "chapter_revision_report",
        "target": note.relative_path,
        "title": note.title,
        "metrics": {
            "word_count": word_count,
            "paragraph_count": len(paragraphs),
            "sentence_count": len(sentences),
            "average_sentence_words": round(sum(sentence_words) / max(1, len(sentence_words)), 1),
        },
        "references": current_row["references"],
        "unresolved_links": _o141_r3_unresolved_for_note(self, note),
        "context": context["chapters"],
        "transition_in": transition_in,
        "transition_out": transition_out,
        "related_issues": related,
        "read_only": True,
    }


def _o141_r3_manuscript_revision_report(self):
    outline = self.manuscript_outline()
    audit = self.continuity_audit()
    chapters = self._chapters()
    transitions = [
        self.chapter_transition(chapters[i].relative_path, chapters[i + 1].relative_path)
        for i in range(max(0, len(chapters) - 1))
    ]

    by_code = {}
    by_severity = {}
    for issue in audit.get("issues") or []:
        code = str(issue.get("code") or "unknown")
        severity = str(issue.get("severity") or "info")
        by_code[code] = by_code.get(code, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1

    chapter_rows = []
    for row in outline.get("chapters") or []:
        rel = str(row.get("relative_path") or "")
        note = _o141_r3_note_by_path(self, rel)
        chapter_rows.append({
            "title": row.get("title"),
            "relative_path": rel,
            "word_count": row.get("word_count"),
            "character_count": len((row.get("references") or {}).get("characters") or []),
            "location_count": len((row.get("references") or {}).get("locations") or []),
            "unresolved_link_count": len(_o141_r3_unresolved_for_note(self, note)),
        })

    return {
        "schema": SCHEMA,
        "kind": "manuscript_revision_report",
        "vault": str(self.vault),
        "chapter_count": outline.get("chapter_count", 0),
        "total_words": outline.get("total_words", 0),
        "continuity_issue_count": audit.get("issue_count", 0),
        "issues_by_code": dict(sorted(by_code.items())),
        "issues_by_severity": dict(sorted(by_severity.items())),
        "transitions": transitions,
        "chapters": chapter_rows,
        "read_only": True,
    }


LongFormRevisionStudio.chapter_transition = _o141_r3_transition
LongFormRevisionStudio.chapter_revision_report = _o141_r3_chapter_revision_report
LongFormRevisionStudio.manuscript_revision_report = _o141_r3_manuscript_revision_report
