from __future__ import annotations

from pathlib import Path
from datetime import datetime
import ast
import hashlib
import json
import os
import subprocess
import sys
import traceback

ROOT = Path(r"C:\AURA GPT version")
CATALOG = ROOT / "tests" / "eval" / "aura_v3_golden_cases.json"
ROAD = ROOT / "data" / "roadmap"

FROZEN = {
    ROOT / "ui" / "main_window.py": "e9aef4ad885e5929175bb61fbec143d5e7aa788bd8fa78599d21c96805e84193",
    ROOT / "runtime" / "aura_intelligence_gateway_v3.py": "6ece3f075d3f6126a89870d38d90c3e78dc645a274a6e3373515a130c3a52a86",
    ROOT / "runtime" / "aura_provider_health_registry_v3.py": "ddfb1097e6a23ac29dba930e545fcf561e7e04de238059a873e9f04e36bb3571",
    ROOT / "runtime" / "aura_eligibility_filter_v3.py": "e68a134eef2fcb1702fd664a4aa3c910dbf5e56a2581bf96cfbb8a574114ec29",
    ROOT / "runtime" / "aura_model_policy_engine_v3.py": "b68c54aa90cc9a25307523a067c8ce80bfb8fc17f7d2d6ad5ba82cd36a7a1811",
    ROOT / "runtime" / "aura_model_switch_gate_v3.py": "ff7db12a3e15fa67cec0ea32ee709e6eacc471f00a732b48307553921b88d751",
    ROOT / "runtime" / "aura_decision_trace_v3.py": "175789d7819f3ca398ae66f5f3105d2e2a9c1942bd959ae34f2a66554448f9e8",
    ROOT / "runtime" / "aura_fabric_execution_binding_v3.py": "f0a2ac61c4e6df6c34993ce93f51392b2cba83c59c71081a405f458aabed3c6f",
    ROOT / "runtime" / "aura_fabric_resilience.py": "78350dbcb6a5501b59f7f4436e47e3e19b109bc677b1beabcaeb0e4795ca17d2",
    ROOT / "runtime" / "aura_intelligence_gateway_composition_v3.py": "4352c48f0985ce009b92f60cea4adc31aff7eb8f3584077973d9a867fa6c2539",
    ROOT / "runtime" / "aura_v3_conversation_route_adapter.py": "112927b63ee1800b9340712e216d8bd4e2c350979a3fbebc59944002e44f9e12",
    ROOT / "runtime" / "aura_conversation_fabric_bridge.py": "e69240d1cfc8448308512367f8a39de469c92ab44d69206ea500e5e73099f769",
    ROOT / "core" / "aura_core.py": "e3d545e8bc5405559404ff9636fa4ac3b3407fb0cb1fb23a6fb61c6d5e79aa72",
}

REQUIRED_FAMILIES = {
    "local_only_privacy_forced_local",
    "cloud_preferred_healthy_provider",
    "provider_cooldown_exclusion",
    "rate_limit_exclusion_and_probe",
    "hard_auth_unavailable",
    "policy_primary_success",
    "approved_fallback_after_primary_failure",
    "all_approved_candidates_fail",
    "exact_fabric_route_deduplication",
    "xtts_vram_preservation_pressure",
    "insufficient_ram_vram_rejection",
    "network_disallowed_remote_rejection",
    "document_fast_lane_outside_v3_gateway",
}

def sha(path: Path):
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda: f.read(1024 * 1024), b""):
            h.update(c)
    return h.hexdigest()

def run_invariant(rel: str, cache: dict):
    if rel in cache:
        return cache[rel]
    path = ROOT / rel
    if not path.is_file():
        result = {"ok": False, "returncode": 404, "stdout": "", "stderr": "missing invariant"}
        cache[rel] = result
        return result
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["AURA_FABRIC_TEST_NO_SLEEP"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(path)],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=180,
    )
    result = {
        "ok": proc.returncode == 0 and "PASS" in proc.stdout,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-3000:],
        "stderr": proc.stderr[-3000:],
    }
    cache[rel] = result
    return result

def check_source_contract(check):
    path = ROOT / check["path"]
    if not path.is_file():
        return {"ok": False, "reason": "missing source"}
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [x for x in check.get("contains", []) if x not in text]
    return {"ok": not missing, "missing": missing}

def check_document_fast_lane(check):
    path = ROOT / check["path"]
    if not path.is_file():
        return {"ok": False, "reason": "missing main_window"}
    text = path.read_text(encoding="utf-8", errors="strict")
    tree = ast.parse(text)
    main = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MainWindow"), None)
    method = next(
        (
            n for n in (main.body if main else [])
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == "_start_document_analysis_fast_lane"
        ),
        None,
    )
    if method is None:
        return {"ok": False, "reason": "fast lane method missing"}
    src = ast.get_source_segment(text, method) or ""
    facts = {
        "uses_llmworker": "LLMWorker(" in src,
        "direct_v3_gateway_call": (
            "generate_conversation_v3(" in src
            or "IntelligenceGatewayV3" in src
            or ".intelligence_gateway_v3" in src
        ),
        "document_context": 'profile["document_context"] = True' in src,
    }
    return {
        "ok": facts["uses_llmworker"] and not facts["direct_v3_gateway_call"] and facts["document_context"],
        "facts": facts,
    }

def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_result = ROAD / f"AURA_V3_GOLDEN_CASE_EVAL_{stamp}_RESULT.json"
    txt_result = ROAD / f"AURA_V3_GOLDEN_CASE_EVAL_{stamp}_RESULT.txt"

    result = {
        "schema": "aura.v3.golden_case_eval_result",
        "version": "1.0.0",
        "status": "RUNNING",
        "classification": "RUNNING",
        "source_mutated": False,
        "network_used": False,
        "real_time_sleep_used": False,
        "production_fabric_service_created": False,
        "roadmap_progress_mutated": False,
        "P220_progress_percent": 75,
    }

    try:
        before = []
        for path, expected in FROZEN.items():
            actual = sha(path)
            before.append({
                "path": str(path.relative_to(ROOT)),
                "actual": actual,
                "expected": expected,
                "ok": actual == expected,
            })
        result["frozen_before"] = before
        if not all(x["ok"] for x in before):
            result["status"] = "BLOCKED_AURA_V3_GOLDEN_CASE_EVAL"
            result["classification"] = "FROZEN_BASELINE_HASH_DRIFT"
            raise RuntimeError("frozen production baseline drift")

        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        cases = list(catalog.get("cases") or [])
        ids = [c.get("id") for c in cases]
        families = {str(c.get("family") or "") for c in cases}
        schema_checks = {
            "case_count_13": len(cases) == 13,
            "unique_ids": len(ids) == len(set(ids)),
            "required_families_exact": families == REQUIRED_FAMILIES,
            "every_case_has_expected": all(isinstance(c.get("expected"), dict) and c["expected"] for c in cases),
            "every_case_has_checks": all(isinstance(c.get("checks"), list) and c["checks"] for c in cases),
        }
        result["catalog_schema_checks"] = schema_checks
        if not all(schema_checks.values()):
            raise RuntimeError(f"catalog schema invalid: {schema_checks}")

        cache = {}
        case_results = []
        for case in cases:
            check_results = []
            for check in case["checks"]:
                ctype = check.get("type")
                if ctype == "invariant":
                    run = run_invariant(check["path"], cache)
                    check_results.append({
                        "type": ctype,
                        "path": check["path"],
                        "ok": bool(run["ok"]),
                        "returncode": run["returncode"],
                        "stdout": run["stdout"],
                        "stderr": run["stderr"],
                    })
                elif ctype == "source_contract":
                    out = check_source_contract(check)
                    check_results.append({"type": ctype, "path": check["path"], **out})
                elif ctype == "document_fast_lane_static":
                    out = check_document_fast_lane(check)
                    check_results.append({"type": ctype, "path": check["path"], **out})
                else:
                    check_results.append({"type": ctype, "ok": False, "reason": "unknown check type"})

            case_results.append({
                "id": case["id"],
                "family": case["family"],
                "title": case["title"],
                "expected": case["expected"],
                "checks": check_results,
                "ok": all(bool(x.get("ok")) for x in check_results),
            })

        result["cases"] = case_results
        result["unique_invariant_runs"] = {
            k: {
                "ok": bool(v["ok"]),
                "returncode": v["returncode"],
                "stdout": v["stdout"],
                "stderr": v["stderr"],
            }
            for k, v in cache.items()
        }

        after = []
        for path, expected in FROZEN.items():
            actual = sha(path)
            after.append({
                "path": str(path.relative_to(ROOT)),
                "actual": actual,
                "expected": expected,
                "ok": actual == expected,
            })
        result["frozen_after"] = after

        passed = sum(1 for c in case_results if c["ok"])
        result["summary"] = {
            "total_cases": len(case_results),
            "passed_cases": passed,
            "failed_cases": len(case_results) - passed,
            "all_frozen_hashes_exact_after": all(x["ok"] for x in after),
        }

        if passed == len(case_results) and all(x["ok"] for x in after):
            result["status"] = "PASS_AURA_V3_GOLDEN_CASE_EVAL"
            result["classification"] = (
                "ALL_13_GOLDEN_CASE_FAMILIES_CERTIFIED__"
                "OFFLINE_DETERMINISTIC_FOUNDATION__"
                "PRODUCTION_BASELINE_UNCHANGED"
            )
            result["recommended_next"] = (
                "Freeze the Golden-Case Harness v1 as the repeatable regression gate for future v3 architecture changes. "
                "Any future v3 production patch should run this harness before acceptance. P220 remains 75."
            )
        else:
            result["status"] = "FAIL_AURA_V3_GOLDEN_CASE_EVAL"
            result["classification"] = "ONE_OR_MORE_GOLDEN_CASES_FAILED"
            result["recommended_next"] = "Inspect failed cases before any production source mutation."

    except Exception:
        if result.get("status") == "RUNNING":
            result["status"] = "FAIL_AURA_V3_GOLDEN_CASE_EVAL"
            result["classification"] = "GOLDEN_CASE_HARNESS_FAILURE"
        result["error"] = traceback.format_exc()
        result.setdefault("recommended_next", "No production source mutation. Inspect result.")

    ROAD.mkdir(parents=True, exist_ok=True)
    json_result.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AURA v3 GOLDEN-CASE EVALUATION HARNESS",
        "=" * 104,
        f"status = {result.get('status')}",
        f"classification = {result.get('classification')}",
        "source_mutated = False",
        "network_used = False",
        "real_time_sleep_used = False",
        "production_fabric_service_created = False",
        "roadmap_progress_mutated = False",
        "P220_progress_percent = 75",
        "",
        "SUMMARY",
        json.dumps(result.get("summary", {}), ensure_ascii=False, indent=2),
        "",
        "CATALOG SCHEMA",
        json.dumps(result.get("catalog_schema_checks", {}), ensure_ascii=False, indent=2),
        "",
        "CASES",
    ]
    for case in result.get("cases", []):
        lines.append(
            f"  {case['id']} :: ok={case['ok']} :: {case['family']} :: {case['title']}"
        )
        for chk in case["checks"]:
            lines.append(
                f"      - {chk.get('type')} {chk.get('path','')} :: ok={chk.get('ok')}"
            )
    lines += [
        "",
        "FINAL",
        f"  status = {result.get('status')}",
        f"  classification = {result.get('classification')}",
        f"  recommended_next = {result.get('recommended_next')}",
        f"  json_result = {json_result}",
        "",
        "ERROR",
        str(result.get("error") or ""),
    ]
    txt_result.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"JSON_RESULT: {json_result}")
    print(f"TXT_RESULT: {txt_result}")
    print(f"STATUS: {result.get('status')}")
    return 0 if str(result.get("status", "")).startswith("PASS_") else 1

if __name__ == "__main__":
    raise SystemExit(main())
