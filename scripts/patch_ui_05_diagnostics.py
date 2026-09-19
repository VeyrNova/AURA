from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
checks=[]
def check(name, cond):
    checks.append((name,bool(cond)))
    print(("PASS" if cond else "FAIL")+"  "+name)
svg=(ROOT/'ui/assets/branding/aura_symbol_master.svg').read_text(encoding='utf-8')
orb=(ROOT/'ui/orb_widget.py').read_text(encoding='utf-8')
gl=(ROOT/'ui/opengl_orb_surface.py').read_text(encoding='utf-8')
main=(ROOT/'ui/main_window.py').read_text(encoding='utf-8')
check('master SVG exists', 'aura-symbol-master' in svg)
check('master glyph is open path', ' L 530 735' in svg and ' 735 Z' not in svg)
check('master SVG uses no filled polygon', 'fill="none"' in svg)
check('logo uses layered rails', 'Dark optical channel' in orb and 'Outer luminous rail' in orb)
check('logo mood palette', '_state_mood_colors(self._state, self._mood)' in orb)
check('logo enlarged', '* .188' in orb and '* .218' in orb)
check('fallback node density >= 248', 'total = 248' in orb)
check('neural radius enlarged', 'float neuralRadius = 0.455' in gl)
check('second procedural neuron lattice', 'microGridB' in gl and '* 25.0' in gl)
check('regional synaptic wave', 'float webPulse' in gl and 'regionalWave' in gl)
check('synaptic membrane', 'membraneHot' in gl and 'shellEdge' in gl)
check('speaking waveform modulation', 'signalAmp' in gl and 'speakingGate' in gl)
check('layered reflection', 'reflectR2' in gl and 'reflectR3' in gl)
check('mood system retained', 'AURA neural mood=' in gl)
check('startup greeting not reintroduced', 'Bonjour, que faisons nous' not in main and 'Bonsoir, que faisons nous' not in main)
check('startup voice phrase retained', 'Initialisation terminée, les paramètres sont tous au vert. Version' in main)
failed=[n for n,ok in checks if not ok]
print(f"\n{len(checks)-len(failed)}/{len(checks)} checks PASS")
sys.exit(1 if failed else 0)
