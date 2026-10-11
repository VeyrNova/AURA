from __future__ import annotations

import re

_LINK = re.compile(r"!?(\[([^\]]+)\]\([^)]*\))")
_HEADING = re.compile(r"^\s{0,3}#{1,6}(?=\s+)(?:\s+)")
_BULLET = re.compile(r"^\s*[-+*]\s+(?=\S)")
_QUOTE = re.compile(r"^\s*>\s?")
_RULE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")


def prepare_text_for_speech(text: str) -> str:
    """Remove presentation-only Markdown while preserving user words."""
    lines = []
    fenced = False
    for raw in str(text or "").splitlines():
        line = raw
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if _RULE.match(line):
            continue
        line = _HEADING.sub("", line)
        line = _BULLET.sub("", line)
        line = _QUOTE.sub("", line)
        line = _LINK.sub(lambda m: m.group(2) or "", line)
        line = re.sub(r"`([^`]*)`", r"\1", line)
        # Paired emphasis markers only; semantic C#, #hashtag and operators
        # remain untouched.
        line = re.sub(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", r"\2", line)
        line = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", line)
        line = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"\1", line)
        line = re.sub(r"<[^>]+>", "", line)
        lines.append(line.strip())
    return re.sub(r"[ \t]+", " ", "\n".join(lines)).strip()
