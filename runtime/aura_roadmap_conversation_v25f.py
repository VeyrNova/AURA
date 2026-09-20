from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.aura_roadmap_http_bridge_v25e import RoadmapHttpBridgeV25E

SCHEMA = "aura.roadmap.conversation.v25f1.v1"
DEFAULT_ROOT = Path(__file__).resolve().parents[1]
CONFIRM_TTL_SECONDS = 600

STATUS_WORDS = {
    "planifie": "planned", "planifiee": "planned", "prevu": "planned", "prevue": "planned",
    "en cours": "in_progress", "encours": "in_progress",
    "bloque": "blocked", "bloquee": "blocked",
    "termine": "done", "terminee": "done", "fini": "done", "finie": "done",
}


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _fmt_date(value: Any) -> str:
    raw = str(value or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", raw)
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else (raw or "—")


def _milestone_id(text: str) -> Optional[str]:
    m = re.search(r"\b([A-Z]{1,8}\d+[A-Z0-9._-]*)\b", str(text or ""), flags=re.I)
    return m.group(1).upper() if m else None


def _active(m: Dict[str, Any]) -> bool:
    life = m.get("lifecycle") or {}
    return not (life.get("archived") or life.get("deleted") or life.get("cancelled"))


def _pending_path(root: Path) -> Path:
    return root / "runtime" / "roadmap_conversation_pending_v25f.json"


def _load_pending(root: Path) -> Dict[str, Any]:
    path = _pending_path(root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        created = datetime.fromisoformat(str(data.get("created_at")))
        age = (datetime.now().astimezone() - created).total_seconds()
        if age > CONFIRM_TTL_SECONDS:
            path.unlink(missing_ok=True)
            return {}
        return data if isinstance(data, dict) else {}
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        return {}


def _save_pending(root: Path, operation: Dict[str, Any], summary: str) -> str:
    path = _pending_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    code = f"RF{int(datetime.now().timestamp() * 1000) % 10000:04d}"
    payload = {
        "schema": SCHEMA,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "code": code,
        "operation": operation,
        "summary": summary,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return code


def _clear_pending(root: Path) -> None:
    try:
        _pending_path(root).unlink(missing_ok=True)
    except Exception:
        pass


def _response(text: str, *, handled: bool = True, intent: str = "", ui_action: str = "", mutation: Any = None) -> Dict[str, Any]:
    return {
        "ok": True,
        "handled": handled,
        "schema": SCHEMA,
        "intent": intent,
        "response": str(text),
        "ui_action": ui_action or None,
        "mutation": mutation,
    }


def _candidate(text: str) -> bool:
    f = _fold(text)
    return bool(
        re.search(r"\broadmap\b", f)
        or re.search(r"\brm\d", f)
        or "projet aura" in f
        or ("baseline" in f and "projet" in f)
        or "prochaine etape" in f
        or "avancement du projet" in f
        or "progression du projet" in f
        or "fin estimee" in f
        or "jours d'avance" in f
        or "jours de retard" in f
        or "etapes bloquees" in f
        or "etape bloquee" in f
        or "phase du projet" in f
    )


def _find_milestone(snapshot: Dict[str, Any], mid: str) -> Optional[Dict[str, Any]]:
    wanted = str(mid or "").upper()
    for row in (snapshot.get("roadmap") or {}).get("milestones", []):
        if str(row.get("id") or "").upper() == wanted:
            return row
    return None


def _shift_date(raw: Any, days: int) -> Optional[str]:
    value = str(raw or "").strip()
    if not value:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(.*)$", value)
    if not m:
        return value
    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3))) + timedelta(days=days)
    return d.isoformat() + (m.group(4) or "")


def _next_child_id(snapshot: Dict[str, Any], anchor: str) -> str:
    existing = {str(x.get("id") or "").upper() for x in (snapshot.get("roadmap") or {}).get("milestones", [])}
    base = re.sub(r"[^A-Z0-9._-]", "", str(anchor or "USR").upper())[:32] or "USR"
    for i in range(1, 100):
        candidate = f"{base}-A{i}"
        if candidate not in existing:
            return candidate
    return f"USR-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def _project_summary(snapshot: Dict[str, Any]) -> str:
    schedule = snapshot.get("schedule") or {}
    p = schedule.get("project") or {}
    last_action = schedule.get("last_action") or {}
    next_action = schedule.get("next_action") or {}
    variance = p.get("schedule_variance_days")
    if isinstance(variance, (int, float)):
        planning = (
            f"{variance:g} jours d'avance" if variance > 0 else
            f"{abs(variance):g} jours de retard" if variance < 0 else
            "dans les temps"
        )
    else:
        planning = "planning non calculé"
    return (
        f"Le projet AURA est à {p.get('actual_total_progress_percent')}% d'avancement. "
        f"Fin estimée : {_fmt_date(p.get('forecast_finish'))}, cible baseline : {_fmt_date(p.get('baseline_finish'))}, "
        f"soit {planning}. Confiance : {p.get('confidence_percent')}%. "
        f"Dernière action : {last_action.get('id','—')} — {last_action.get('title','—')}. "
        f"Prochaine action : {next_action.get('id','—')} — {next_action.get('title','—')}."
    )


def handle_roadmap_conversation_v25f(text: str, *, root: Path | str = DEFAULT_ROOT) -> Dict[str, Any]:
    root = Path(root)
    raw = str(text or "").strip()
    folded = _fold(raw)
    if not raw or not _candidate(raw):
        return _response("", handled=False)

    bridge = RoadmapHttpBridgeV25E(root=root)
    snapshot = bridge.snapshot()

    # Baseline is read-only from conversational control.
    if "baseline" in folded and re.search(r"\b(change|changer|modifie|modifier|decale|decaler|supprime|supprimer|edite|editer)\b", folded):
        return _response(
            "La baseline historique est verrouillée. Je peux modifier le forecast ou le réel, mais pas la baseline.",
            intent="ROADMAP_BASELINE_DENIED",
        )

    # Confirm / cancel destructive operations.
    confirm = re.search(r"\bconfirme\s+roadmap\s+(rf\d{4})\b", folded, flags=re.I)
    if confirm:
        pending = _load_pending(root)
        if not pending or str(pending.get("code") or "").upper() != confirm.group(1).upper():
            return _response("Aucune confirmation Roadmap valide ne correspond à ce code.", intent="ROADMAP_CONFIRM_INVALID")
        result = bridge.mutate({
            **dict(pending.get("operation") or {}),
            "actor": "roadmap-conversation-v25f",
            "reason": "Confirmation conversationnelle Roadmap",
        })
        _clear_pending(root)
        return _response(
            f"Confirmation reçue. {pending.get('summary','La modification')} a été appliquée.",
            intent="ROADMAP_CONFIRM",
            mutation=result.get("mutation"),
        )

    if re.search(r"\bannule\s+(?:la\s+)?confirmation\s+roadmap\b|\bannule\s+roadmap\b", folded):
        _clear_pending(root)
        return _response("Confirmation Roadmap annulée.", intent="ROADMAP_CONFIRM_CANCEL")

    # Open UI.
    if re.search(r"\b(ouvre|affiche|montre)\s+(?:la\s+)?roadmap\b", folded):
        return _response("J'ouvre la Roadmap AURA.", intent="ROADMAP_OPEN", ui_action="open_roadmap")

    # Read-only intents.
    if (
        "ou en est" in folded
        or "etat du projet" in folded
        or "statut du projet" in folded
        or "progression du projet" in folded
        or "avancement du projet" in folded
        or folded in {"roadmap", "roadmap aura"}
    ):
        return _response(_project_summary(snapshot), intent="ROADMAP_STATUS")

    if "prochaine etape" in folded or "prochaine action" in folded:
        nxt = (snapshot.get("schedule") or {}).get("next_action") or {}
        return _response(f"La prochaine étape est {nxt.get('id','—')} — {nxt.get('title','—')}.", intent="ROADMAP_NEXT")

    if "fin estimee" in folded or "date de fin" in folded or "quand sera fini" in folded:
        p = (snapshot.get("schedule") or {}).get("project") or {}
        return _response(
            f"La fin estimée du projet est le {_fmt_date(p.get('forecast_finish'))}. "
            f"La cible baseline est le {_fmt_date(p.get('baseline_finish'))}.",
            intent="ROADMAP_FINISH",
        )

    if "avance" in folded or "retard" in folded or "planning" in folded:
        p = (snapshot.get("schedule") or {}).get("project") or {}
        variance = p.get("schedule_variance_days")
        if isinstance(variance, (int, float)):
            label = (
                f"{variance:g} jours d'avance" if variance > 0 else
                f"{abs(variance):g} jours de retard" if variance < 0 else "dans les temps"
            )
        else:
            label = "non calculé"
        return _response(
            f"Le projet est {label}. Fin estimée : {_fmt_date(p.get('forecast_finish'))}. "
            f"Confiance : {p.get('confidence_percent')}%.",
            intent="ROADMAP_SCHEDULE",
        )

    if "bloque" in folded or "bloquee" in folded:
        blocked = [
            m for m in (snapshot.get("roadmap") or {}).get("milestones", [])
            if _active(m) and str((m.get("forecast") or {}).get("status") or "") == "blocked"
        ]
        if not blocked:
            return _response("Aucune étape active n'est actuellement bloquée.", intent="ROADMAP_BLOCKED")
        rows = "; ".join(f"{m.get('id')} — {m.get('title')}" for m in blocked[:12])
        return _response(f"Étapes bloquées : {rows}.", intent="ROADMAP_BLOCKED")

    phase_match = re.search(r"\b(?:montre|affiche|liste)\s+(?:la\s+)?phase\s+(.+)$", folded)
    if phase_match:
        requested = phase_match.group(1).strip(" .")
        phases = snapshot.get("phases") or []
        phase = next((p for p in phases if _fold(p) == requested), None)
        if phase is None:
            phase = next((p for p in phases if requested in _fold(p)), None)
        if not phase:
            return _response(f"Je ne trouve pas de phase correspondant à « {requested} ».", intent="ROADMAP_PHASE")
        rows = [
            m for m in (snapshot.get("roadmap") or {}).get("milestones", [])
            if _active(m) and _fold(m.get("phase")) == _fold(phase)
        ]
        text_rows = "; ".join(
            f"{m.get('id')} — {m.get('title')} ({(m.get('forecast') or {}).get('status')})"
            for m in rows[:15]
        ) or "aucune étape active"
        return _response(f"Phase {phase} : {text_rows}.", intent="ROADMAP_PHASE")

    if "historique" in folded and "roadmap" in folded:
        revs = snapshot.get("revisions") or []
        if not revs:
            return _response("L'historique Roadmap est vide.", intent="ROADMAP_HISTORY")
        rows = "; ".join(
            f"{r.get('revision_id')} · {r.get('operation')} · {r.get('reason','')}"
            for r in revs[:5]
        )
        return _response(f"Dernières révisions : {rows}.", intent="ROADMAP_HISTORY")

    mid = _milestone_id(raw)

    # Destructive milestone operations require explicit confirmation.
    if mid and re.search(r"\barchive\b|\barchiver\b", folded):
        if not _find_milestone(snapshot, mid):
            return _response(f"Étape {mid} introuvable.", intent="ROADMAP_ARCHIVE")
        code = _save_pending(root, {"operation": "archive_milestone", "milestone_id": mid}, f"L'archivage de {mid}")
        return _response(
            f"Cette action archive {mid}. Pour confirmer, dis : « confirme roadmap {code} ».",
            intent="ROADMAP_ARCHIVE_CONFIRM",
        )

    if mid and re.search(r"\bsupprime\b|\bsupprimer\b", folded):
        if not _find_milestone(snapshot, mid):
            return _response(f"Étape {mid} introuvable.", intent="ROADMAP_DELETE")
        code = _save_pending(root, {"operation": "delete_milestone_soft", "milestone_id": mid}, f"La suppression logique de {mid}")
        return _response(
            f"Cette action supprime logiquement {mid}. Pour confirmer, dis : « confirme roadmap {code} ».",
            intent="ROADMAP_DELETE_CONFIRM",
        )

    rev_match = re.search(r"\brestaure(?:r)?\s+(?:la\s+)?revision\s+([A-Za-z0-9_.-]+)", raw, flags=re.I)
    if rev_match:
        rev = rev_match.group(1)
        code = _save_pending(root, {"operation": "restore_revision", "revision_id": rev}, f"La restauration de la révision {rev}")
        return _response(
            f"Restaurer une révision remplace l'état courant de la Roadmap. Pour confirmer, dis : « confirme roadmap {code} ».",
            intent="ROADMAP_RESTORE_REVISION_CONFIRM",
        )

    archive_phase = re.search(r"\barchive(?:r)?\s+(?:la\s+)?phase\s+(.+)$", folded)
    if archive_phase:
        phase_text = archive_phase.group(1).strip(" .")
        phase = next((p for p in (snapshot.get("phases") or []) if _fold(p) == phase_text), None)
        if not phase:
            return _response(f"Phase « {phase_text} » introuvable.", intent="ROADMAP_ARCHIVE_PHASE")
        code = _save_pending(root, {"operation": "archive_phase", "phase": phase}, f"L'archivage de la phase {phase}")
        return _response(
            f"Cette action archive la phase {phase}. Pour confirmer, dis : « confirme roadmap {code} ».",
            intent="ROADMAP_ARCHIVE_PHASE_CONFIRM",
        )

    # Non-destructive milestone updates.
    if mid:
        status_match = re.search(
            r"\b(?:passe|mets?|marque)\s+" + re.escape(mid.lower()) +
            r"\s+(?:(?:en|a)\s+)?(cours|planifiee?|prevue?|bloquee?|terminee?|fini[e]?)\b",
            folded,
        )
        if status_match:
            status_token = status_match.group(1)
            status = "in_progress" if status_token == "cours" else STATUS_WORDS.get(status_token)
            if status:
                result = bridge.mutate({
                    "operation": "update_milestone",
                    "milestone_id": mid,
                    "patch": {"forecast": {"status": status}},
                    "actor": "roadmap-conversation-v25f",
                    "reason": "Mise à jour du statut depuis la conversation",
                })
                label = {"planned": "planifiée", "in_progress": "en cours", "blocked": "bloquée", "done": "terminée"}.get(status, status)
                return _response(
                    f"{mid} est maintenant {label}. Project Active et le planning ont été recalculés.",
                    intent="ROADMAP_UPDATE_STATUS",
                    mutation=result.get("mutation"),
                )

        progress_match = re.search(r"\b(\d{1,3}(?:[.,]\d+)?)\s*%", folded)
        if progress_match and re.search(r"\b(passe|mets?|progression|avancement)\b", folded):
            progress = max(0.0, min(100.0, float(progress_match.group(1).replace(",", "."))))
            patch: Dict[str, Any] = {"forecast": {"progress_percent": progress}}
            current = _find_milestone(snapshot, mid) or {}
            current_status = str((current.get("forecast") or {}).get("status") or "planned")
            if 0 < progress < 100 and current_status == "planned":
                patch["forecast"]["status"] = "in_progress"
            if progress >= 100:
                patch["forecast"]["status"] = "done"
            result = bridge.mutate({
                "operation": "update_milestone",
                "milestone_id": mid,
                "patch": patch,
                "actor": "roadmap-conversation-v25f",
                "reason": "Mise à jour de progression depuis la conversation",
            })
            return _response(
                f"La progression de {mid} est maintenant à {progress:g}%. Project Active a été recalculé.",
                intent="ROADMAP_UPDATE_PROGRESS",
                mutation=result.get("mutation"),
            )

        shift_match = re.search(r"\b(decale|repousse|avance)\b.*?\bde\s+(-?\d+)\s+jours?\b", folded)
        if shift_match:
            current = _find_milestone(snapshot, mid)
            if not current:
                return _response(f"Étape {mid} introuvable.", intent="ROADMAP_SHIFT")
            days = int(shift_match.group(2))
            days = -abs(days) if shift_match.group(1) == "avance" else abs(days)
            forecast = current.get("forecast") or {}
            start = _shift_date(forecast.get("start"), days)
            end = _shift_date(forecast.get("end"), days)
            if not start and not end:
                return _response(f"{mid} n'a pas encore de dates forecast à décaler.", intent="ROADMAP_SHIFT")
            patch = {"forecast": {}}
            if start:
                patch["forecast"]["start"] = start
            if end:
                patch["forecast"]["end"] = end
            result = bridge.mutate({
                "operation": "update_milestone",
                "milestone_id": mid,
                "patch": patch,
                "actor": "roadmap-conversation-v25f",
                "reason": f"Décalage forecast de {days} jours depuis la conversation",
            })
            return _response(
                f"Les dates forecast de {mid} ont été décalées de {days:+d} jours. Le planning projet a été recalculé.",
                intent="ROADMAP_SHIFT",
                mutation=result.get("mutation"),
            )

        if re.search(r"\brestaure(?:r)?\b", folded):
            result = bridge.mutate({
                "operation": "restore_milestone",
                "milestone_id": mid,
                "status": "planned",
                "actor": "roadmap-conversation-v25f",
                "reason": "Restauration depuis la conversation",
            })
            return _response(
                f"{mid} a été restaurée au statut planifié.",
                intent="ROADMAP_RESTORE_MILESTONE",
                mutation=result.get("mutation"),
            )

    # Add milestone relative to an anchor.
    add = re.search(
        r"\bajoute(?:r)?\s+(?:une\s+)?etape\s+(apres|avant)\s+([A-Za-z0-9._-]+)\s+(?:appelee?|nommee?|intitulee?|:)\s*(.+)$",
        raw,
        flags=re.I,
    )
    if add:
        direction, anchor, title = add.group(1).lower(), add.group(2).upper(), add.group(3).strip()
        anchor_row = _find_milestone(snapshot, anchor)
        if not anchor_row:
            return _response(f"Étape d'ancrage {anchor} introuvable.", intent="ROADMAP_ADD")
        new_id = _next_child_id(snapshot, anchor)
        milestone = {
            "id": new_id,
            "phase": anchor_row.get("phase") or "Unassigned",
            "version": "",
            "title": title[:240],
            "description": "Ajoutée depuis le contrôle conversationnel Roadmap.",
            "weight": 1.0,
            "dependencies": [anchor] if direction == "apres" else [],
            "forecast": {"status": "planned", "progress_percent": 0, "start": None, "end": None},
            "actual": {"start": None, "end": None},
        }
        payload = {
            "operation": "add_milestone",
            "milestone": milestone,
            "actor": "roadmap-conversation-v25f",
            "reason": "Ajout depuis la conversation",
        }
        payload["after_id" if direction == "apres" else "before_id"] = anchor
        result = bridge.mutate(payload)
        return _response(
            f"Étape {new_id} — {title} ajoutée {direction} {anchor}. "
            f"Elle hérite de la phase {milestone['phase']} avec un poids initial de 1.",
            intent="ROADMAP_ADD",
            mutation=result.get("mutation"),
        )

    rename = re.search(r"\brenomme(?:r)?\s+(?:la\s+)?phase\s+(.+?)\s+en\s+(.+)$", raw, flags=re.I)
    if rename:
        old_phase = rename.group(1).strip()
        new_phase = rename.group(2).strip()
        result = bridge.mutate({
            "operation": "rename_phase",
            "old_phase": old_phase,
            "new_phase": new_phase,
            "actor": "roadmap-conversation-v25f",
            "reason": "Renommage de phase depuis la conversation",
        })
        return _response(
            f"La phase « {old_phase} » a été renommée « {new_phase} ».",
            intent="ROADMAP_RENAME_PHASE",
            mutation=result.get("mutation"),
        )

    return _response(
        "Je peux lire l'état du projet, la prochaine étape, l'avance ou le retard, les phases et les blocages. "
        "Je peux aussi modifier le statut, la progression ou les dates forecast d'une étape, ajouter une étape, "
        "renommer une phase, et demander confirmation avant archivage, suppression ou restauration de révision.",
        intent="ROADMAP_HELP",
    )
