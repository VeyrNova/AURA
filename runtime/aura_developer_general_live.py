"""AURA ADF-H R7.1 R5 — general explicit-path self-development binding with provider failover.

Phase 1:
- Developer Mode required.
- Explicit target path (or unique existing basename) required.
- Single target file only.
- AURA's existing LLM generates complete final text.
- The LLM never writes directly.
- ADF-F proposal/staging/tests and ADF-G governance are mandatory.
- Exact approval hierarchy is required before write.
- Exact rollback is supported.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import inspect
import json
import os
import re
import shutil
import sys
import time
import unicodedata

from ai.llm_manager import LLMProviderError
from config.settings import settings
from runtime.aura_developer_mode import developer_mode_enabled
from runtime.aura_developer_live_bridge import queue_spoken_summary
from runtime.aura_patch_transaction_engine import propose_edits, validate_in_staging
from runtime.aura_self_development_governance import (
    apply_self_development,
    assess_proposal,
    rollback_self_development,
)
from runtime.aura_developer_coding_fabric_live import generate_edit_via_coding_fabric

ROOT = Path(os.environ.get("AURA_ROOT") or Path(__file__).resolve().parents[1]).resolve()
STATE_PATH = ROOT / "runtime" / "developer_fabric" / "live_selftest_transaction_state.json"

BINDING_ID = "ADF-H-R7.2.11-GENERAL-CODING-FABRIC-BINDING"
MAX_SOURCE_BYTES = 96 * 1024
MAX_GENERATED_CHARS = 220_000

ALLOWED_TEXT_SUFFIXES = {
    ".py", ".json", ".js", ".css", ".html", ".htm", ".md", ".txt",
    ".yaml", ".yml", ".toml", ".ini", ".cfg",
}
SKIP_SEARCH_PARTS = {
    ".git", "__pycache__", "_patch_backups", ".aura_transactions",
    ".aura_audit", "venv", ".venv", "node_modules",
}
CODING_WORDS = (
    "modifi", "change", "corrig", "ajout", "ajoute", "supprim", "retir",
    "cree", "creer", "créer", "cré", "refactor", "implem", "implém",
    "remplace", "replace", "edit", "update", "fix", "add", "remove",
    "create", "rewrite", "patch",
)
APPROVAL_PREFIXES = ("APPLY ", "AUTHORIZE SELF ", "AUTHORIZE RELEASE ")
ROLLBACK_PREFIX = "ROLLBACK SELF "

_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|private[_-]?key)\b\s*[:=]\s*['\"][^'\"]{8,}"),
    re.compile(r"(?i)\b(bearer|authorization)\b\s*[:=]\s*['\"][^'\"]{12,}"),
)

_PATH_RE = re.compile(
    r"""(?ix)
    (?:
        [A-Za-z]:[\\/](?:[^<>:"|?*\r\n]+[\\/])*[^<>:"|?*\r\n]+\.(?:py|json|js|css|html?|md|txt|ya?ml|toml|ini|cfg)
      |
        (?:[A-Za-z0-9_.-]+[\\/])+(?:[A-Za-z0-9_.-]+)\.(?:py|json|js|css|html?|md|txt|ya?ml|toml|ini|cfg)
      |
        (?<![A-Za-z0-9_.-])(?:[A-Za-z0-9_.-]+)\.(?:py|json|js|css|html?|md|txt|ya?ml|toml|ini|cfg)(?![A-Za-z0-9_.-])
    )
    """
)


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(value.casefold().split())


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {
            "schema": "aura.general-self-development-live-state.v1",
            "updated_at": time.time(),
            "binding": BINDING_ID,
            "pending": None,
            "last_receipt": None,
            "last_rollback": None,
        }
    try:
        obj = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = dict(state)
    state["updated_at"] = time.time()
    tmp = STATE_PATH.with_suffix(STATE_PATH.suffix + ".r71r3.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATE_PATH)


def _is_general_state(state: dict[str, Any]) -> bool:
    return str(state.get("binding") or "") == BINDING_ID


def _queue(text: str) -> None:
    queue_spoken_summary(text, root=ROOT)


def _is_coding_intent(text: str) -> bool:
    folded = _fold(text)

    if any(word in folded for word in CODING_WORDS):
        return True

    # ADF-H: natural-language edit commands with an explicit file target.
    # Keep this gated by a path/filename so ordinary conversation does not
    # accidentally become a developer request.
    if _extract_path_candidates(text):
        edit_words = (
            "rends",
            "rend ",
            "modifie",
            "modifier",
            "corrige",
            "corriger",
            "ajoute",
            "ajouter",
            "supprime",
            "supprimer",
            "remplace",
            "remplacer",
            "refactor",
            "implemente",
            "implementer",
            "adapte",
            "adapter",
        )
        if any(word in folded for word in edit_words):
            return True

    return False



def _extract_path_candidates(text: str) -> list[str]:
    out: list[str] = []
    for m in _PATH_RE.finditer(str(text or "")):
        raw = m.group(0).strip().strip("`'\"()[]{}.,;:")
        if raw and raw not in out:
            out.append(raw)
    return out


def _safe_relative_path(raw: str) -> str | None:
    raw = str(raw or "").strip().strip("`'\"")
    if not raw:
        return None

    p = Path(raw)
    if p.is_absolute():
        try:
            rel = p.resolve().relative_to(ROOT)
        except Exception:
            return None
    else:
        rel = Path(raw.replace("\\", "/"))

    rel_text = rel.as_posix().lstrip("./")
    if not rel_text or rel_text.startswith("../") or "/../" in f"/{rel_text}/":
        return None
    return rel_text


def _search_unique_basename(name: str) -> str | None:
    hits = []
    for p in ROOT.rglob(name):
        try:
            rel = p.relative_to(ROOT)
        except Exception:
            continue
        if any(part in SKIP_SEARCH_PARTS for part in rel.parts):
            continue
        if p.is_file():
            hits.append(rel.as_posix())
            if len(hits) > 1:
                return None
    return hits[0] if len(hits) == 1 else None


def _resolve_explicit_target(text: str) -> tuple[str | None, str | None]:
    candidates = _extract_path_candidates(text)
    if not candidates:
        return None, "Aucun fichier cible explicite n'a été détecté."

    ordered = sorted(candidates, key=lambda x: (("/" not in x and "\\" not in x), len(x)))
    raw = ordered[0]
    rel = _safe_relative_path(raw)

    if rel is None:
        return None, "Le chemin demandé sort du dépôt AURA ou n'est pas sûr."

    if "/" not in raw and "\\" not in raw:
        unique = _search_unique_basename(Path(raw).name)
        if unique is None:
            return None, (
                f"Le nom {Path(raw).name} n'est pas unique ou n'existe pas. "
                "Indique le chemin relatif complet dans le dépôt AURA."
            )
        rel = unique

    suffix = Path(rel).suffix.casefold()
    if suffix not in ALLOWED_TEXT_SUFFIXES:
        return None, f"Le type de fichier {suffix or '(sans extension)'} n'est pas autorisé dans R7.1."

    try:
        resolved = (ROOT / rel).resolve()
        resolved.relative_to(ROOT)
    except Exception:
        return None, "Le chemin cible n'est pas contenu dans le dépôt AURA."

    return rel, None


def _read_target(rel: str) -> tuple[bool, str]:
    path = ROOT / rel
    if not path.exists():
        return False, ""
    if not path.is_file():
        raise ValueError("La cible n'est pas un fichier.")
    data = path.read_bytes()
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError(f"Fichier trop volumineux pour R7.1 ({len(data)} octets > {MAX_SOURCE_BYTES}).")
    if b"\x00" in data[:4096]:
        raise ValueError("Fichier binaire refusé.")
    return True, data.decode("utf-8")


def _contains_secret_material(text: str) -> bool:
    return any(p.search(text or "") for p in _SECRET_PATTERNS)


def _profile_for_generation(aura_core: Any, user_text: str) -> dict[str, Any]:
    profile: dict[str, Any] = {}
    fn = getattr(aura_core, "llm_request_profile", None)
    if callable(fn):
        try:
            profile = dict(fn(user_text) or {})
        except TypeError:
            try:
                profile = dict(fn() or {})
            except Exception:
                profile = {}
        except Exception:
            profile = {}

    if not profile:
        fn = getattr(aura_core, "agent_router_profile", None)
        if callable(fn):
            try:
                profile = dict(fn(user_text) or {})
            except Exception:
                profile = {}
    return profile


def _filter_generate_kwargs(generate_fn: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    try:
        sig = inspect.signature(generate_fn)
    except Exception:
        return kwargs
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return kwargs
    return {k: v for k, v in kwargs.items() if k in sig.parameters}


def _parse_generation(raw: str, expected_path: str) -> dict[str, str]:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)

    obj = None
    try:
        obj = json.loads(text)
    except Exception:
        a = text.find("{")
        b = text.rfind("}")
        if a >= 0 and b > a:
            obj = json.loads(text[a:b+1])

    if not isinstance(obj, dict):
        raise ValueError("Le modèle n'a pas renvoyé un objet JSON valide.")

    path = str(obj.get("path") or "").replace("\\", "/").lstrip("./")
    new_text = obj.get("new_text")
    summary = str(obj.get("summary") or "Modification générée par AURA.").strip()

    if path != expected_path:
        raise ValueError(f"Le modèle a tenté de modifier une autre cible: {path!r}.")
    if not isinstance(new_text, str):
        raise ValueError("Le champ JSON new_text est absent ou invalide.")
    if len(new_text) > MAX_GENERATED_CHARS:
        raise ValueError("La sortie générée est trop volumineuse.")
    if _contains_secret_material(new_text):
        raise ValueError("La sortie générée ressemble à un secret ou identifiant sensible et a été refusée.")

    return {"path": path, "new_text": new_text, "summary": summary[:300]}


def _preferred_profile(
    aura_core: Any,
    user_text: str,
    *,
    preferred_provider: str | None = None,
    force_local: bool = False,
) -> dict[str, Any]:
    """Resolve an AURA-owned profile for one explicit provider preference."""
    fn = getattr(aura_core, "llm_request_profile", None)
    if not callable(fn):
        return _profile_for_generation(aura_core, user_text)

    kwargs: dict[str, Any] = {"user_text": user_text}
    if preferred_provider:
        kwargs["preferred_provider"] = str(preferred_provider)
    if force_local:
        kwargs["force_local"] = True

    # Current Runtime-v2 accepts voice_output; older compatible signatures may not.
    try:
        return dict(fn(voice_output=False, **kwargs) or {})
    except TypeError:
        try:
            return dict(fn(**kwargs) or {})
        except TypeError:
            if preferred_provider or force_local:
                return {}
            return _profile_for_generation(aura_core, user_text)
    except Exception:
        return {}


def _prepare_generation_profile(aura_core: Any, profile: dict[str, Any]) -> None:
    prepare = getattr(aura_core, "prepare_for_llm", None)
    if not callable(prepare) or not profile:
        return
    try:
        prepare(profile=profile)
    except TypeError:
        try:
            prepare(profile)
        except Exception:
            pass
    except Exception:
        pass


def _generation_kwargs(generate_fn: Any, profile: dict[str, Any]) -> dict[str, Any]:
    kwargs = {
        "provider": profile.get("provider", "local"),
        "model": profile.get("model"),
        "keep_alive": profile.get("keep_alive"),
        "num_ctx": max(int(profile.get("num_ctx") or 0), 8192),
        "num_predict": max(int(profile.get("num_predict") or 0), 4096),
        "temperature": min(float(profile.get("temperature") or 0.20), 0.20),
        "top_p": min(float(profile.get("top_p") or 0.85), 0.90),
    }
    if profile.get("thinking_level"):
        kwargs["thinking_level"] = profile.get("thinking_level")
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    return _filter_generate_kwargs(generate_fn, kwargs)


def _provider_error_http_code(exc: BaseException) -> int | None:
    match = re.search(r"\b(4\d\d|5\d\d)\b", str(exc or ""))
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _retryable_provider_failure(exc: BaseException) -> bool:
    code = _provider_error_http_code(exc)
    if code is not None:
        return code == 429 or code in {408, 409, 425} or 500 <= code <= 599
    folded = _fold(str(exc or ""))
    return any(token in folded for token in (
        "timeout", "temps a repondre", "connexion", "network",
        "tempor", "indisponible", "connection",
    ))


def _provider_available(manager: Any, provider: str) -> bool:
    fn = getattr(manager, "remote_available", None)
    if not callable(fn):
        return False
    try:
        return bool(fn(provider))
    except TypeError:
        try:
            return bool(fn())
        except Exception:
            return False
    except Exception:
        return False


def _run_generation_attempt(
    aura_core: Any,
    manager: Any,
    generate: Any,
    messages: list[dict[str, str]],
    profile: dict[str, Any],
    rel: str,
    attempts: list[dict[str, Any]],
    phase: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    provider = str(profile.get("provider") or "local").casefold()
    model = profile.get("model")
    _prepare_generation_profile(aura_core, profile)

    try:
        raw = generate(messages, **_generation_kwargs(generate, profile))
        edit = _parse_generation(raw, rel)
        attempts.append({
            "phase": phase,
            "provider": provider,
            "model": model,
            "status": "success",
        })
        return edit, profile
    except LLMProviderError as exc:
        attempts.append({
            "phase": phase,
            "provider": provider,
            "model": model,
            "status": "provider_error",
            "http_code": _provider_error_http_code(exc),
            "error": str(exc)[:500],
        })
        raise


def _aura_record_general_attempt_r7212r5r6(
    *,
    status,
    rel,
    user_text,
    proposal=None,
    validation=None,
    test_commands=None,
    generator=None,
    error=None,
):
    """Persist base-general failure evidence without superseding historical pending."""
    from time import time as _aura_time_r7212r5r6

    old_state = _load_state()
    state = dict(old_state) if isinstance(old_state, dict) else {}
    state["updated_at"] = _aura_time_r7212r5r6()
    state["last_general_attempt"] = {
        "status": str(status or ""),
        "target": str(rel or ""),
        "target_workspace": str(ROOT),
        "user_text": str(user_text or ""),
        "proposal": proposal,
        "validation": validation,
        "test_commands": test_commands,
        "generator": generator,
        "error": str(error) if error is not None else None,
        "evidence_gate": "ADF-H-R7.2.12-R5-R6",
        "pending_created": False,
        "apply_performed": False,
    }
    _save_state(state)

def _generate_edit(
    aura_core: Any,
    user_text: str,
    rel: str,
    existed: bool,
    current_text: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    """R5 R6: Coding Fabric generation with fail-closed base-general evidence."""
    del aura_core
    try:
        return generate_edit_via_coding_fabric(
            user_text,
            rel,
            existed,
            current_text,
            source_root=ROOT,
        )
    except Exception as exc:
        try:
            _aura_record_general_attempt_r7212r5r6(
                status="generation_exception",
                rel=rel,
                user_text=user_text,
                error=f"{type(exc).__name__}: {exc}",
            )
        except Exception:
            pass
        raise




def _test_commands_r7212r4_base(rel: str) -> list[list[str]]:
    suffix = Path(rel).suffix.casefold()
    if suffix == ".py":
        return [[sys.executable, "-m", "py_compile", rel]]
    if suffix == ".json":
        return [[
            sys.executable, "-c",
            "import json,sys; json.load(open(sys.argv[1],encoding='utf-8'))",
            rel,
        ]]
    if suffix == ".js" and shutil.which("node"):
        return [["node", "--check", rel]]
    return []

def _test_commands_r7212r5r6_base(rel: str):
    # R7.2.12 R4 managed-UI staging support.
    normalized = Path(str(rel or "")).as_posix()
    suffix = Path(normalized).suffix.casefold()
    name = Path(normalized).name.casefold()

    # AURA ROADMAP RM26-3F — MARKDOWN STAGING GATE
    # ADF-F requires at least one staging command. Markdown previously returned
    # an empty list, so a successful Coding Fabric edit stopped before pending.
    if suffix == ".md":
        commands = [[
            sys.executable,
            "-c",
            'from pathlib import Path\nimport sys\np=Path(sys.argv[1])\nb=p.read_bytes()\nif not b:\n    raise SystemExit("empty markdown target")\nif b"\\x00" in b[:4096]:\n    raise SystemExit("binary/NUL markdown target denied")\ns=b.decode("utf-8")\nif not s.strip():\n    raise SystemExit("blank markdown target")\nprint("AURA_MARKDOWN_UTF8_ACCEPTANCE_PASS")\n',
            normalized,
        ]]
        if name == "rm26_live_acceptance.md":
            commands.append([
                sys.executable,
                "-c",
                'from pathlib import Path\nimport sys\ns=Path(sys.argv[1]).read_text(encoding="utf-8")\nrequired=["# RM26 LIVE ACCEPTANCE","AURA Developer production hook validated after POST-APPLY PASS."]\nmissing=[x for x in required if x not in s]\nif missing:\n    raise SystemExit("missing RM26 acceptance markers: "+", ".join(missing))\nprint("RM26_LIVE_ACCEPTANCE_SEMANTIC_PASS")\n',
                normalized,
            ])
        return commands

    if suffix in {".js", ".mjs", ".css", ".html", ".json", ".svg"}:
        commands = []

        if suffix in {".js", ".mjs"} and shutil.which("node"):
            commands.append(["node", "--check", normalized])

        if name == "aura_workspace_project_active_v130.js":
            commands.append([
                sys.executable,
                "-c",
                'from pathlib import Path\nimport sys\np=Path(sys.argv[1])\ns=p.read_text(encoding="utf-8")\nf=s.casefold()\nrequired=[\n "aura-project-active-v130__head",\n "pointerdown","pointermove","pointerup","pointercancel","lostpointercapture",\n "setpointercapture","releasepointercapture",\n "sessionstorage.getitem","sessionstorage.setitem","sessionstorage.removeitem",\n "dblclick","clampposition","window.innerwidth","window.innerheight",\n "function isinteractiveornondraggable",\n "iscontenteditable","data-no-drag",\n "prevuserselect","function render(","async function refresh(","function boot("\n]\nmissing=[x for x in required if x not in f]\nif missing:\n    raise SystemExit("missing Project Active markers: "+", ".join(missing))\nif "head.contains(e.target)" not in f:\n    raise SystemExit("header-only drag guard absent")\nif "preventdefault(" in f:\n    raise SystemExit("unexpected preventDefault")\nprint("PROJECT_ACTIVE_JS_STATIC_ACCEPTANCE_PASS")\n',
                normalized,
            ])
        else:
            commands.append([
                sys.executable,
                "-c",
                'from pathlib import Path\nimport sys\np=Path(sys.argv[1])\nb=p.read_bytes()\nif not b:\n    raise SystemExit("empty target")\nif b"\\x00" in b[:4096]:\n    raise SystemExit("binary/NUL target denied")\nb.decode("utf-8")\nprint("AURA_MANAGED_UI_UTF8_ACCEPTANCE_PASS")\n',
                normalized,
            ])
        return commands

    return _test_commands_r7212r4_base(rel)

def _test_commands(rel: str):
    """R5 R6: semantic Project Active gate, exact pre-existing mapping elsewhere."""
    normalized = Path(str(rel or "")).as_posix()

    if Path(normalized).name.casefold() != "aura_workspace_project_active_v130.js":
        return _test_commands_r7212r5r6_base(rel)

    commands = []
    if shutil.which("node"):
        commands.append(["node", "--check", normalized])

    semantic_probe = r"""
from pathlib import Path
import re
import sys

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
f = s.casefold()
missing = []

def req(name, cond):
    if not cond:
        missing.append(name)

req("Project Active header", "aura-project-active-v130__head" in f)

for token in ("pointerdown", "pointermove", "pointerup", "pointercancel", "lostpointercapture"):
    req(token, token in f)

req("setPointerCapture", "setpointercapture" in f)
req("releasePointerCapture", "releasepointercapture" in f)

req(
    "header-only drag start",
    (
        ("closest(" in f and "aura-project-active-v130__head" in f)
        or "head.contains(" in f
        or "header.contains(" in f
    ),
)

for token in ("button", "input", "textarea", "select"):
    req("interactive " + token, token in f)
req("interactive link", ("a[href" in f) or ('"a"' in f) or ("'a'" in f) or ",a," in f or ", a," in f)
req("contenteditable", "contenteditable" in f)
req("role button", ("role=\"button\"" in f) or ("role='button'" in f) or ("role=button" in f))
req("tabindex", "tabindex" in f)

req("sessionStorage get", "sessionstorage.getitem" in f)
req("sessionStorage set", "sessionstorage.setitem" in f)
req("sessionStorage reset", "sessionstorage.removeitem" in f)
req("double-click reset", "dblclick" in f)

req("viewport width", "window.innerwidth" in f)
req("viewport height", "window.innerheight" in f)
req("viewport clamp", "clamp" in f or ("math.min" in f and "math.max" in f))
req("resize recalibration", "resize" in f)

assignments = re.findall(r"userselect\s*=\s*([^;\n]+)", f)
has_none = any(re.search(r"['\"]none['\"]", x) for x in assignments)
has_restore = any(not re.search(r"['\"]none['\"]", x) for x in assignments)
req("selection userSelect references", f.count("userselect") >= 3)
req("selection disabled during drag", has_none)
req("selection restored", has_restore)

req("ROOT_ID preserved", "aura-project-active-v130" in f)
req("render preserved", "function render(" in f)
req("refresh preserved", "async function refresh(" in f)
req("boot preserved", "function boot(" in f)

if missing:
    raise SystemExit("missing Project Active semantic behaviors: " + ", ".join(missing))

print("PROJECT_ACTIVE_JS_SEMANTIC_ACCEPTANCE_PASS")
"""
    commands.append([sys.executable, "-c", semantic_probe, normalized])
    return commands




def _approval_like(text: str) -> bool:
    stripped = str(text or "").strip()
    return stripped.startswith(APPROVAL_PREFIXES) or stripped.startswith(ROLLBACK_PREFIX)


def _handle_pending_approval(text: str, state: dict[str, Any]) -> bool:
    pending = state.get("pending")
    if not isinstance(pending, dict):
        return False

    assessment = pending.get("assessment") or {}
    required = [str(x) for x in (assessment.get("required_approvals") or [])]
    stripped = str(text or "").strip()

    if stripped not in required:
        if _approval_like(stripped):
            _queue("Approbation refusée. Utilise uniquement la phrase exacte affichée dans l'espace développeur.")
            return True
        return False

    received = [str(x) for x in (pending.get("approvals_received") or [])]
    if stripped not in received:
        received.append(stripped)
        pending["approvals_received"] = received

    missing = [p for p in required if p not in received]
    if missing:
        state["pending"] = pending
        _save_state(state)
        _queue("Première autorisation validée. Une autorisation supplémentaire est requise et affichée dans l'espace développeur.")
        return True

    proposal = pending["proposal"]
    validation = pending["validation"]
    commands = pending.get("test_commands") or []
    max_risk = str(assessment.get("max_risk") or "")

    receipt = apply_self_development(
        proposal,
        validation,
        aura_root=ROOT,
        approval_phrase=required[0],
        critical_approval=required[1] if len(required) >= 2 else None,
        release_approval=required[2] if len(required) >= 3 else None,
        release_mode=(max_risk == "constitutional"),
        post_test_commands=commands,
    )

    state["pending"] = None
    state["last_receipt"] = receipt
    state["last_rollback"] = None
    state["binding"] = BINDING_ID
    _save_state(state)
    _queue("Modification AURA appliquée. Les tests post-application sont terminés; le rollback exact est disponible.")
    return True


def _handle_rollback(text: str, state: dict[str, Any]) -> bool:
    receipt = state.get("last_receipt")
    if not isinstance(receipt, dict):
        return False

    stripped = str(text or "").strip()
    expected = str(receipt.get("rollback_phrase") or "")
    if stripped != expected:
        if stripped.startswith(ROLLBACK_PREFIX):
            _queue("Rollback refusé. Utilise uniquement la phrase exacte affichée dans l'espace développeur.")
            return True
        return False

    rollback = rollback_self_development(receipt, approval_phrase=stripped)
    state["pending"] = None
    state["last_receipt"] = None
    state["last_rollback"] = rollback
    state["binding"] = BINDING_ID
    _save_state(state)
    _queue("Rollback AURA terminé. La modification a été annulée.")
    return True


def _prepare_general(aura_core: Any, text: str) -> bool:
    if not _is_coding_intent(text):
        return False

    rel, error = _resolve_explicit_target(text)
    if error:
        if _extract_path_candidates(text):
            _queue(error)
            return True
        return False

    try:
        existed, current_text = _read_target(rel)
        edit, generator = _generate_edit(aura_core, text, rel, existed, current_text)

        if existed and edit["new_text"] == current_text:
            _aura_record_general_attempt_r7212r5r6(
                status="zero_edit",
                rel=rel,
                user_text=text,
                generator=generator,
            )
            _queue("Le modèle n'a proposé aucun changement réel; diagnostic enregistré, aucune transaction créée.")
            return True

        proposal = propose_edits(ROOT, [edit], task=str(text or ""))
        commands = _test_commands(rel)
        validation = validate_in_staging(proposal, commands, timeout_s=120)

        if validation.get("passed") is not True:
            _aura_record_general_attempt_r7212r5r6(
                status="staging_failed",
                rel=rel,
                user_text=text,
                proposal=proposal,
                validation=validation,
                test_commands=commands,
                generator=generator,
            )
            _queue("La proposition a échoué aux tests de staging. Diagnostic enregistré; aucune écriture n'a été effectuée.")
            return True

        assessment = assess_proposal(proposal, ROOT, release_mode=False)

        old_state = _load_state()
        superseded = None
        old_pending = old_state.get("pending") if isinstance(old_state, dict) else None
        if isinstance(old_pending, dict):
            superseded = {
                "transaction_id": (old_pending.get("proposal") or {}).get("transaction_id"),
                "reason": "superseded_by_new_unapproved_proposal",
                "at": time.time(),
            }

        state = {
            "schema": "aura.general-self-development-live-state.v1",
            "binding": BINDING_ID,
            "updated_at": time.time(),
            "pending": {
                "operation": "general_explicit_path",
                "request": str(text or ""),
                "target": rel,
                "proposal": proposal,
                "validation": validation,
                "assessment": assessment,
                "approvals_received": [],
                "test_commands": commands,
                "generator": generator,
                "superseded_pending": superseded,
            },
            "last_receipt": None,
            "last_rollback": None,
        }
        _save_state(state)
        _queue("Modification préparée et testée en staging. Vérifie le diff dans l'espace développeur avant toute application.")
        return True

    except Exception as exc:
        _queue(f"Préparation de la modification refusée: {type(exc).__name__}: {exc}")
        return True


def handle_general_self_development(aura_core: Any, text: str) -> bool:
    if not developer_mode_enabled():
        return False

    state = _load_state()
    if _is_general_state(state):
        if _handle_pending_approval(text, state):
            return True
        if _handle_rollback(text, state):
            return True
        if _approval_like(text):
            _queue("Cette approbation ne correspond à aucune transaction Coding Fabric active.")
            return True

    return _prepare_general(aura_core, text)


def capability_snapshot() -> dict[str, Any]:
    return {
        "schema": "aura.adf-h-r7-1-r5-general-explicit-path-failover-capabilities.v1",
        "binding": BINDING_ID,
        "developer_mode_required": True,
        "general_natural_language": True,
        "explicit_target_required": True,
        "unique_existing_basename_allowed": True,
        "automatic_target_discovery": False,
        "multi_file_generation": False,
        "model_direct_write": False,
        "coding_fabric_generation": True,
        "conversation_llm_generation": False,
        "provider_resilience_owner": "AFG",
        "provider_retry_once_on_transient_failure": False,
        "cloud_failover": "AFG/aura-code",
        "local_fallback_respects_existing_policy": True,
        "provider_attempts_recorded": True,
        "adf_f_propose": True,
        "adf_f_staging": True,
        "adf_g_assessment": True,
        "exact_approval_required": True,
        "rollback_supported": True,
        "secret_input_fail_closed": True,
        "secret_output_fail_closed": True,
        "workspace": str(ROOT),
        "state_path": str(STATE_PATH),
    }

# ---------------------------------------------------------------------------
# AURA ADF-H R7.2.12 R4 - exact managed UI workspace preparation route.
# Explicit filename required. No direct apply.
# ---------------------------------------------------------------------------

_AURA_R7212R4_UI_EXTENSIONS = {".js", ".mjs", ".css", ".html", ".json", ".svg"}


def _aura_managed_ui_root_r7212r4() -> Path | None:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    root = (
        Path(local)
        / "AURA"
        / "ui"
        / "v0.7.2.2-rc4.2"
        / "dist"
    )
    try:
        return root.resolve(strict=True)
    except Exception:
        return None


def _aura_managed_ui_target_r7212r4(text: str):
    ui_root = _aura_managed_ui_root_r7212r4()
    if ui_root is None:
        return None

    raw = str(text or "")

    explicit_raw = re.findall(
        r"(?i)(?<![A-Za-z0-9_.-])((?:[A-Za-z]:)?[\\/]?(?:dist[\\/])?(?:[A-Za-z0-9_.-]+[\\/])+[A-Za-z0-9_.-]+\.(?:js|mjs|css|html|json|svg))",
        raw,
    )

    explicit = []
    explicit_seen = set()
    for item in explicit_raw:
        value = str(item or "").strip().replace("\\", "/")
        key = value.casefold()
        if key in explicit_seen:
            continue
        explicit_seen.add(key)
        explicit.append(value)

    if explicit:
        matches = []
        seen_targets = set()

        for value in explicit:
            if re.match(r"^[A-Za-z]:/", value) or value.startswith("/"):
                continue

            parts = [part for part in value.split("/") if part not in ("", ".")]
            if not parts:
                continue
            if any(part == ".." for part in parts):
                continue
            if parts and parts[0].casefold() == "dist":
                parts = parts[1:]
            if not parts:
                continue

            candidate = ui_root.joinpath(*parts)
            try:
                resolved = candidate.resolve(strict=True)
                relative = resolved.relative_to(ui_root)
            except Exception:
                continue

            if resolved.suffix.casefold() not in _AURA_R7212R4_UI_EXTENSIONS:
                continue

            target_key = str(resolved).casefold()
            if target_key in seen_targets:
                continue
            seen_targets.add(target_key)
            matches.append((resolved, relative))

        if len(matches) != 1:
            return None

        resolved, relative = matches[0]
        return {
            "workspace": ui_root,
            "target": resolved,
            "relative": relative.as_posix(),
        }

    names = re.findall(
        r"(?i)\b([A-Za-z0-9_.-]+\.(?:js|mjs|css|html|json|svg))\b",
        raw,
    )
    unique = []
    seen = set()
    for name in names:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(name)

    matches = []
    for name in unique:
        candidate = ui_root / name
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(ui_root)
        except Exception:
            continue
        if resolved.suffix.casefold() not in _AURA_R7212R4_UI_EXTENSIONS:
            continue
        matches.append(resolved)

    if len(matches) != 1:
        return None

    return {
        "workspace": ui_root,
        "target": matches[0],
        "relative": matches[0].relative_to(ui_root).as_posix(),
    }


def _aura_record_managed_ui_attempt_r7212r5r3(
    *,
    status,
    workspace,
    rel,
    user_text,
    proposal=None,
    validation=None,
    test_commands=None,
    generator=None,
    error=None,
):
    """Persist diagnostic evidence without creating or approving a pending txn."""
    old_state = _load_state()
    state = dict(old_state) if isinstance(old_state, dict) else {}
    state["updated_at"] = time.time()
    state["last_managed_ui_attempt"] = {
        "status": str(status or ""),
        "target": str(rel or ""),
        "target_workspace": str(workspace or ""),
        "user_text": str(user_text or ""),
        "proposal": proposal,
        "validation": validation,
        "test_commands": test_commands,
        "generator": generator,
        "error": str(error) if error is not None else None,
        "managed_workspace": "ui_dist",
        "managed_workspace_gate": "ADF-H-R7.2.12-R4",
        "evidence_gate": "ADF-H-R7.2.12-R5-R3",
        "pending_created": False,
        "apply_performed": False,
    }
    _save_state(state)


def _aura_prepare_managed_ui_r7212r4(aura_core, text: str) -> bool:
    if not developer_mode_enabled(ROOT):
        return False
    if not _is_coding_intent(text):
        return False

    resolved = _aura_managed_ui_target_r7212r4(text)
    if not resolved:
        return False

    workspace = resolved["workspace"]
    target = resolved["target"]
    rel = resolved["relative"]

    proposal = None
    validation = None
    commands = None
    generator = None

    try:
        current_text = target.read_text(encoding="utf-8")

        from runtime.aura_developer_coding_fabric_live import (
            generate_edit_via_coding_fabric,
        )

        edit, generator = generate_edit_via_coding_fabric(
            str(text or ""),
            rel,
            True,
            current_text,
            source_root=workspace,
            timeout_seconds=420.0,
        )

        if edit.get("new_text") == current_text:
            _aura_record_managed_ui_attempt_r7212r5r3(
                status="zero_edit",
                workspace=workspace,
                rel=rel,
                user_text=text,
                generator=generator,
            )
            _queue(
                "Le Coding Fabric n'a proposé aucun changement réel; "
                "diagnostic enregistré, aucune transaction créée."
            )
            return True

        proposal = propose_edits(
            workspace,
            [edit],
            task=str(text or ""),
        )
        commands = _test_commands(rel)
        validation = validate_in_staging(
            proposal,
            commands,
            timeout_s=120,
        )

        if validation.get("passed") is not True:
            _aura_record_managed_ui_attempt_r7212r5r3(
                status="staging_failed",
                workspace=workspace,
                rel=rel,
                user_text=text,
                proposal=proposal,
                validation=validation,
                test_commands=commands,
                generator=generator,
            )
            txn = str(proposal.get("transaction_id") or "sans-id")
            failed = [
                item for item in (validation.get("tests") or [])
                if item.get("passed") is not True
            ]
            detail = ""
            if failed:
                first = failed[0]
                stderr = str(first.get("stderr") or "").strip()
                stdout = str(first.get("stdout") or "").strip()
                detail = stderr or stdout
            if detail:
                detail = detail.replace("\r", " ").replace("\n", " ")[:140]
                _queue(
                    f"Échec staging {txn}: {detail}. "
                    "Diagnostic complet enregistré; aucune écriture."
                )
            else:
                _queue(
                    f"Échec staging {txn}. Diagnostic complet enregistré; "
                    "aucune écriture n'a été effectuée."
                )
            return True

        assessment = assess_proposal(
            proposal,
            ROOT,
            release_mode=False,
        )

        old_state = _load_state()
        superseded = None
        if isinstance(old_state, dict):
            old_pending = old_state.get("pending")
            if isinstance(old_pending, dict):
                superseded = old_pending

        state = dict(old_state) if isinstance(old_state, dict) else {}
        state["binding"] = BINDING_ID
        state["updated_at"] = time.time()
        state["last_managed_ui_attempt"] = {
            "status": "pending_created",
            "target": rel,
            "target_workspace": str(workspace),
            "user_text": str(text or ""),
            "proposal": proposal,
            "validation": validation,
            "test_commands": commands,
            "generator": generator,
            "managed_workspace": "ui_dist",
            "managed_workspace_gate": "ADF-H-R7.2.12-R4",
            "evidence_gate": "ADF-H-R7.2.12-R5-R3",
            "pending_created": True,
            "apply_performed": False,
        }
        state["pending"] = {
            "target": rel,
            "target_workspace": str(workspace),
            "user_text": str(text or ""),
            "proposal": proposal,
            "validation": validation,
            "assessment": assessment,
            "test_commands": commands,
            "generator": generator,
            "managed_workspace": "ui_dist",
            "managed_workspace_gate": "ADF-H-R7.2.12-R4",
            "superseded_pending": superseded,
        }
        state["last_receipt"] = None
        state["last_rollback"] = None
        _save_state(state)

        _queue(
            "Modification UI préparée et testée en staging. "
            "Vérifie le diff dans l'espace développeur avant toute application."
        )
        return True

    except Exception as exc:
        try:
            _aura_record_managed_ui_attempt_r7212r5r3(
                status="prepare_exception",
                workspace=workspace,
                rel=rel,
                user_text=text,
                proposal=proposal,
                validation=validation,
                test_commands=commands,
                generator=generator,
                error=f"{type(exc).__name__}: {exc}",
            )
        except Exception:
            pass
        _queue(
            "Préparation UI gérée refusée: "
            f"{type(exc).__name__}: {exc}"
        )
        return True



_aura_r7212r4_base_handle_general_self_development = handle_general_self_development


def handle_general_self_development(aura_core, text: str) -> bool:
    if _aura_prepare_managed_ui_r7212r4(aura_core, text):
        return True
    return _aura_r7212r4_base_handle_general_self_development(aura_core, text)


_aura_r7212r4_base_capability_snapshot = capability_snapshot


def capability_snapshot():
    data = dict(_aura_r7212r4_base_capability_snapshot())
    data.update({
        "managed_ui_workspace": True,
        "managed_ui_requires_explicit_filename": True,
        "managed_ui_direct_apply": False,
        "managed_ui_adf_f_staging": True,
        "managed_ui_adf_g_governance": True,
        "managed_ui_extensions": sorted(_AURA_R7212R4_UI_EXTENSIONS),
        "managed_ui_route_id": "ADF-H-R7.2.12-R4-MANAGED-UI",
        "managed_ui_staging_failure_evidence": True,
        "managed_ui_failure_preserves_existing_pending": True,
        "managed_ui_evidence_gate": "ADF-H-R7.2.12-R5-R3",
        "project_active_semantic_staging": True,
        "general_generation_failure_evidence": True,
        "general_staging_failure_evidence": True,
        "general_evidence_gate": "ADF-H-R7.2.12-R5-R6",
    })
    return data


# AURA ROADMAP RM26-2 — explicit Developer task -> proposal metadata binding
_rm26_general_propose_edits_base = propose_edits


def propose_edits(
    workspace,
    edits,
    *,
    task: str = "",
    metadata: dict[str, Any] | None = None,
):
    if metadata is None:
        from runtime.aura_roadmap_developer_binding_rm26 import (
            roadmap_metadata_for_developer_task,
        )
        metadata = roadmap_metadata_for_developer_task(task, root=ROOT)

    return _rm26_general_propose_edits_base(
        workspace,
        edits,
        task=task,
        metadata=metadata,
    )
