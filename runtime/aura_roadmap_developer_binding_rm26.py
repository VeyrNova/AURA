from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_ROOT = Path(r"C:\AURA GPT version")


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _roadmap(root: Path) -> Dict[str, Any]:
    path = root / "data" / "roadmap" / "aura_master_roadmap_v2.json"
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _schedule(root: Path) -> Dict[str, Any]:
    path = root / "data" / "roadmap" / "aura_roadmap_schedule_state.json"
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _active_milestone(doc: Dict[str, Any], milestone_id: str) -> Optional[Dict[str, Any]]:
    wanted = str(milestone_id or "").strip().upper()
    for row in doc.get("milestones", []):
        if str(row.get("id") or "").strip().upper() != wanted:
            continue
        life = row.get("lifecycle") or {}
        if any(life.get(k) for k in ("archived", "deleted", "cancelled")):
            return None
        return row
    return None


def roadmap_metadata_for_developer_task(
    task: str,
    *,
    root: Path | str = DEFAULT_ROOT,
) -> Optional[Dict[str, Any]]:
    """
    Bind an AURA Developer proposal to a Roadmap milestone only when the task
    contains explicit Roadmap scope.

    Accepted explicit scopes:
    - a milestone id such as RM26;
    - "roadmap" together with "prochaine étape/action", which resolves the
      current schedule next_action.

    Ordinary coding requests receive no Roadmap metadata and cannot auto-certify.
    """
    root = Path(root)
    raw = str(task or "")
    folded = _fold(raw)
    doc = _roadmap(root)

    explicit = re.search(r"\b(RM\d+[A-Z0-9._-]*)\b", raw, flags=re.I)
    milestone_id = explicit.group(1).upper() if explicit else ""

    if not milestone_id:
        roadmap_scope = "roadmap" in folded
        next_scope = (
            "prochaine etape" in folded
            or "prochaine action" in folded
            or "etape suivante" in folded
        )
        if roadmap_scope and next_scope:
            state = _schedule(root)
            milestone_id = str(
                (state.get("next_action") or {}).get("id") or ""
            ).strip().upper()

    if not milestone_id:
        return None

    row = _active_milestone(doc, milestone_id)
    if row is None:
        return None

    return {
        "roadmap_auto_certify": True,
        "roadmap_milestone_id": milestone_id,
        "roadmap_source": "aura-developer-general-live-rm26",
        "roadmap_title": str(row.get("title") or ""),
    }
