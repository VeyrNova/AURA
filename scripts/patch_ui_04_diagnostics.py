from __future__ import annotations
from pathlib import Path
import ast, re, sys

ROOT = Path(__file__).resolve().parents[1]
checks=[]
def ok(name, cond):
    checks.append((name,bool(cond)))

def text(rel): return (ROOT/rel).read_text(encoding="utf-8")

for rel in ("ui/opengl_orb_surface.py","ui/orb_widget.py","ui/main_window.py","ui/aura_mood.py"):
    try:
        ast.parse(text(rel)); ok(f"syntax {rel}", True)
    except Exception as exc:
        print(rel, exc); ok(f"syntax {rel}", False)

gl=text("ui/opengl_orb_surface.py")
orb=text("ui/orb_widget.py")
main=text("ui/main_window.py")
mood=text("ui/aura_mood.py")

ok("44 explicit neural nodes", "i < 44" in gl and "mod(fi * 13.0" in gl)
ok("procedural micro-neuron fabric", "microNode" in gl and "fineWeb" in gl)
ok("travelling GLSL synapses", "pulseAlong" in gl and "synapticActivity" in gl)
ok("speaking state gate", "speakingGate" in gl)
ok("larger neural radius", "neuralRadius = 0.405" in gl)
ok("late boot network", "smoothstep(0.350, 0.700, boot)" in gl and "smoothstep(0.540, 0.820, boot)" in gl)
ok("late vector logo reveal", "0.82, 0.95" in orb)
ok("fallback 176 nodes", "total = 176" in orb)
ok("fallback travelling synapse", "Travelling synaptic packet" in orb)
ok("fallback voice amplitude", "def set_voice_amplitude" in orb)
ok("mood public API", "def set_mood" in orb and "def set_mood" in gl)
ok("mood palette module", "MOOD_PALETTES" in mood and "infer_aura_mood" in mood)
ok("mood attached to LLM", '_apply_orb_mood_for_text(reply, source="llm-final")' in main)
ok("mood attached to TTS", '_apply_orb_mood_for_text(text, source="tts")' in main)
ok("synaptic boot copy", "CONSTRUCTION DU RÉSEAU SYNAPTIQUE" in main)
ok("startup neutral mood", 'self.orb.set_mood("neutral")' in main)
ok("official startup sentence retained", "Initialisation terminée, les paramètres sont tous au vert. Version" in main)
ok("no greeting copy", "que faisons nous" not in main.casefold() and "que faisons-nous" not in main.casefold())
ok("single vector master retained", "from ui.aura_logo import master_symbol_path" in orb)

failed=[name for name,passed in checks if not passed]
for name,passed in checks: print(("PASS" if passed else "FAIL"), name)
print(f"\n{len(checks)-len(failed)}/{len(checks)} PASS")
sys.exit(1 if failed else 0)
