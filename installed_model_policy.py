from __future__ import annotations

import re
from typing import Iterable, Mapping

SCHEMA = "aura.installed-model-policy.v1"
PATCH = "P0.8.5.3.2"

PROFILE_TEXT_CAP_B = {
    "P1": 4.5,
    "P2": 9.0,
    "P3": 14.0,
}
# Spoken interaction stays latency-first even on P3.
PROFILE_VOICE_CAP_B = {
    "P1": 4.5,
    "P2": 4.5,
    "P3": 4.5,
}


def _canonical(value: str) -> str:
    return str(value or "").strip()


def _model_matches(requested: str, actual: str) -> bool:
    requested = _canonical(requested).casefold()
    actual = _canonical(actual).casefold()
    if not requested or not actual:
        return False
    if requested == actual:
        return True
    if ":" not in requested:
        return actual.split(":", 1)[0] == requested
    return False


def _parameter_billions(item: Mapping[str, object]) -> float | None:
    details = item.get("details") if isinstance(item, Mapping) else None
    if isinstance(details, Mapping):
        raw = str(details.get("parameter_size") or "").strip()
        m = re.search(r"(?i)(\d+(?:\.\d+)?)\s*B\b", raw)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass

    name = str(item.get("name") or item.get("model") or "") if isinstance(item, Mapping) else ""
    m = re.search(r"(?i)(?:^|[:_\-])(\d+(?:\.\d+)?)b(?:$|[:_\-])", name)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    return None


def _size_bytes(item: Mapping[str, object]) -> int:
    try:
        return max(0, int(item.get("size") or item.get("size_bytes") or 0))
    except Exception:
        return 0


def normalize_catalog(models: Iterable[Mapping[str, object]]) -> tuple[dict, ...]:
    result = []
    seen = set()
    for raw in models or ():
        if not isinstance(raw, Mapping):
            continue
        name = _canonical(str(raw.get("name") or raw.get("model") or ""))
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        details = raw.get("details")
        if not isinstance(details, Mapping):
            details = {}
        result.append({
            "name": name,
            "size_bytes": _size_bytes(raw),
            "parameter_b": _parameter_billions(raw),
            "family": str(details.get("family") or ""),
            "parameter_size": str(details.get("parameter_size") or ""),
            "quantization_level": str(details.get("quantization_level") or ""),
        })
    return tuple(result)


def _find_requested(catalog: tuple[dict, ...], requested: str) -> dict | None:
    for item in catalog:
        if _model_matches(requested, item["name"]):
            return item
    return None


def _fits(item: Mapping[str, object], cap_b: float) -> bool:
    p = item.get("parameter_b")
    if p is None:
        return True
    try:
        return float(p) <= float(cap_b)
    except Exception:
        return True


def _rank(item: Mapping[str, object]) -> tuple[float, int, str]:
    p = item.get("parameter_b")
    param = float(p) if p is not None else -1.0
    return (param, int(item.get("size_bytes") or 0), str(item.get("name") or "").casefold())


def _best_with_cap(catalog: tuple[dict, ...], cap_b: float) -> dict | None:
    fitting = [item for item in catalog if _fits(item, cap_b)]
    if fitting:
        return max(fitting, key=_rank)
    if catalog:
        # No model fits the profile target. Fail conservatively toward the
        # smallest installed model instead of trying to download anything.
        return min(catalog, key=lambda x: (
            float(x["parameter_b"]) if x.get("parameter_b") is not None else 1e9,
            int(x.get("size_bytes") or 0),
            str(x.get("name") or "").casefold(),
        ))
    return None


def select_installed_models(
    *,
    profile_code: str,
    catalog,
    requested_text: str,
    requested_voice: str,
    explicit_text: bool = False,
    explicit_voice: bool = False,
) -> dict:
    code = str(profile_code or "P2").upper()
    if code not in PROFILE_TEXT_CAP_B:
        code = "P2"

    normalized = normalize_catalog(catalog)
    text_current = _find_requested(normalized, requested_text)
    voice_current = _find_requested(normalized, requested_voice)
    text_cap = PROFILE_TEXT_CAP_B[code]
    voice_cap = PROFILE_VOICE_CAP_B[code]

    if explicit_text:
        text_selected = _canonical(requested_text)
        text_reason = "explicit-override-preserved"
    elif text_current is not None and _fits(text_current, text_cap):
        text_selected = _canonical(requested_text) or text_current["name"]
        text_reason = "requested-installed-and-fits"
    else:
        candidate = _best_with_cap(normalized, text_cap)
        text_selected = candidate["name"] if candidate else _canonical(requested_text)
        text_reason = "installed-profile-selection" if candidate else "catalog-empty-fallback"

    if explicit_voice:
        voice_selected = _canonical(requested_voice)
        voice_reason = "explicit-override-preserved"
    elif voice_current is not None and _fits(voice_current, voice_cap):
        voice_selected = _canonical(requested_voice) or voice_current["name"]
        voice_reason = "requested-installed-and-fits"
    else:
        candidate = _best_with_cap(normalized, voice_cap)
        voice_selected = candidate["name"] if candidate else _canonical(requested_voice)
        voice_reason = "installed-profile-selection" if candidate else "catalog-empty-fallback"

    text_changed = bool(text_selected and text_selected != _canonical(requested_text))
    voice_changed = bool(voice_selected and voice_selected != _canonical(requested_voice))

    return {
        "schema": SCHEMA,
        "patch": PATCH,
        "profile_code": code,
        "catalog_count": len(normalized),
        "catalog": list(normalized),
        "requested_text": _canonical(requested_text),
        "requested_voice": _canonical(requested_voice),
        "selected_text": text_selected,
        "selected_voice": voice_selected,
        "text_reason": text_reason,
        "voice_reason": voice_reason,
        "explicit_text": bool(explicit_text),
        "explicit_voice": bool(explicit_voice),
        "text_changed": text_changed,
        "voice_changed": voice_changed,
        "changed": bool(text_changed or voice_changed),
        "download_required": False,
        "download_allowed": False,
        "text_cap_b": text_cap,
        "voice_cap_b": voice_cap,
    }


def self_test() -> bool:
    catalog = [
        {"name": "llama3.2:3b", "size": 2_019_393_189,
         "details": {"parameter_size": "3.2B", "quantization_level": "Q4_K_M"}},
        {"name": "llama3.1:latest", "size": 4_920_753_328,
         "details": {"parameter_size": "8.0B", "quantization_level": "Q4_K_M"}},
    ]
    p1 = select_installed_models(
        profile_code="P1", catalog=catalog,
        requested_text="llama3.1", requested_voice="llama3.2:3b",
    )
    p2 = select_installed_models(
        profile_code="P2", catalog=catalog,
        requested_text="llama3.1", requested_voice="llama3.2:3b",
    )
    forced = select_installed_models(
        profile_code="P1", catalog=catalog,
        requested_text="llama3.1", requested_voice="custom:99b",
        explicit_text=True, explicit_voice=True,
    )
    return (
        p1["selected_text"] == "llama3.2:3b"
        and p1["selected_voice"] == "llama3.2:3b"
        and p2["selected_text"] == "llama3.1"
        and p2["selected_voice"] == "llama3.2:3b"
        and not p2["changed"]
        and forced["selected_text"] == "llama3.1"
        and forced["selected_voice"] == "custom:99b"
        and forced["download_required"] is False
    )


if __name__ == "__main__":
    import json
    print(json.dumps({"self_test": self_test()}, indent=2))
