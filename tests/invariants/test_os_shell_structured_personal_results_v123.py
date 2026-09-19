from __future__ import annotations
import ast,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from runtime.personal_result_presenter_v123 import build_personal_result_payload_v123,summarize_personal_result_for_tts_v123
core=(ROOT/"core"/"aura_core.py").read_text(encoding="utf-8-sig"); bus=(ROOT/"core"/"event_bus.py").read_text(encoding="utf-8-sig"); main=(ROOT/"ui"/"main_window.py").read_text(encoding="utf-8-sig"); panel=(ROOT/"ui"/"personal_result_panel_v123.py").read_text(encoding="utf-8-sig")
assert core.count("AURA_V123_STRUCTURED_PERSONAL_RESULT_BEGIN")==1 and "personal_result.emit" in core and "self.handle_aura_response(_aura_pi_text)" in core
assert bus.count("AURA_V123_PERSONAL_RESULT_SIGNAL")==1 and "Signal(object)" in bus
tree=ast.parse(main); mw=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="MainWindow"); names={n.name for n in mw.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
assert {"showEvent","keyPressEvent","_on_personal_result_v123"}<=names and "showFullScreen" in main and "Key_F11" in main and "Key_Escape" in main
assert "QColor(" not in panel and "background-color:" not in panel and "color:" not in panel
r=SimpleNamespace(text="De: Test\nObjet: Sujet\nAperçu: Bonjour",status="succeeded",messages=[{"sender":"Test","subject":"Sujet","preview":"Bonjour"}]); q=SimpleNamespace(provider_id="email.provider",capability_id="email.search")
p=build_personal_result_payload_v123(r,q); assert p["kind"]=="mail" and p["count"]>=1; s=summarize_personal_result_for_tts_v123(p,r.text); assert "mail" in s.lower() and "Sujet" not in s
print("[PASS] v1.2.3 OS shell + structured personal result invariant")
