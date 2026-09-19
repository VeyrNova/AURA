
from pathlib import Path
import os, sys, tempfile
ROOT=Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from runtime.aura_developer_live_bridge import handle_live_developer_input,queue_spoken_summary,dequeue_spoken_summary,capability_snapshot
from runtime.aura_developer_mode import developer_mode_enabled
from runtime.aura_self_development_governance import classify_path
from ui.developer_workspace_dialog import capability_snapshot as workspace_capabilities
from ui.developer_mode_visuals import capability_snapshot as visual_capabilities

with tempfile.TemporaryDirectory(prefix="aura_adf_h_bridge_") as td:
    root=Path(td).resolve(); (root/"runtime").mkdir()
    assert developer_mode_enabled(root) is False
    on=handle_live_developer_input("Aura, active le mode développeur",channel="voice",root=root)
    assert on["recognized"] and on["consume"] and not on["forward_to_llm"] and on["enabled"]
    ordinary=handle_live_developer_input("quelle heure est-il",channel="voice",root=root)
    assert not ordinary["recognized"] and ordinary["forward_to_llm"]
    workspace=handle_live_developer_input("Aura, ouvre l'espace développeur",channel="voice",root=root)
    assert workspace["recognized"] and workspace["open_workspace"]
    off=handle_live_developer_input("Aura, repasse en mode normal",channel="text",root=root)
    assert off["recognized"] and not off["enabled"]
    queue_spoken_summary("J’ai modifié aura_fabric_http_gateway.py. Les tests sont passés.",root=root)
    queue_spoken_summary("J’ai modifié 3 fichiers. Les tests sont passés.",root=root)
    first=dequeue_spoken_summary(root=root); second=dequeue_spoken_summary(root=root)
    assert first.startswith("J’ai modifié aura_fabric_http_gateway.py") and len(first)<=150
    assert second.startswith("J’ai modifié 3 fichiers") and len(second)<=150
    assert dequeue_spoken_summary(root=root) is None

caps=capability_snapshot()
assert caps["text_intercept_before_llm"] and caps["voice_transcript_same_route"] and caps["native_tts_confirmation"] and caps["brief_summary_queue"]
wcaps=workspace_capabilities()
assert wcaps["native_qt_dialog"] and wcaps["read_only_operational_surface"] and wcaps["shows_transactions"] and wcaps["shows_audit"]
vcaps=visual_capabilities()
assert vcaps["persistent_dev_badge"] and vcaps["persistent_write_gated_audit_status"] and vcaps["amber_window_border"]
assert vcaps["normal_mode_restores_clean_ui"] and vcaps["layout_mutation_required"] is False
assert classify_path(".aura_audit/events.jsonl")=="forbidden"
print("[PASS] ADF-H R2 live bridge + native workspace + DEV visual identity semantics")
