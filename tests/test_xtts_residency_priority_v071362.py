import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from config.settings import settings
from runtime.resource_guardian import ResourceGuardian, ResourcePressureError
from ai.local_first_voice import social_reply


ROOT = Path(__file__).parents[1]
GUARDIAN = (ROOT / 'runtime' / 'resource_guardian.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'ui' / 'main_window.py').read_text(encoding='utf-8')


class _Voice:
    profile = SimpleNamespace(engine='xtts')
    def xtts_model_loaded(self): return True
    def release_stt_model(self): return False
    def release_xtts_model(self): raise AssertionError('XTTS must not be released')


class _LLM:
    def get_running_info(self, model=None): return None
    def model_available(self, model): return True


class XTTSResidencyPriorityV071362Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(settings.APP_VERSION, '0.7.2')

    def test_social_bypass_is_narrow_and_deterministic(self):
        self.assertIn('Je suis là', social_reply('Bonjour Aura'))
        self.assertEqual(social_reply('Merci beaucoup'), 'Avec plaisir.')
        self.assertEqual(social_reply('Quelle est la météo ?'), '')

    def test_cold_local_llm_is_blocked_without_releasing_xtts(self):
        guardian = ResourceGuardian(_LLM(), _Voice())
        profile = {
            'name': 'voice-fast', 'provider': 'local', 'model': 'llama3.2:3b',
            'co_resident': True, 'preserve_xtts_for_voice': True,
        }
        with patch.object(settings, 'XTTS_LOCAL_FIRST_ENABLED', True), \
             patch.object(settings, 'XTTS_LOCAL_FIRST_PROTECT_RESIDENCY', True), \
             patch.object(settings, 'XTTS_ALLOW_CUDA', True), \
             patch.object(settings, 'XTTS_DEVICE', 'cuda'):
            with self.assertRaises(ResourcePressureError) as ctx:
                guardian.prepare_for_llm(profile)
        self.assertIn('garde ma voix locale XTTS prête', str(ctx.exception))

    def test_source_contains_residency_priority_contract(self):
        self.assertIn('XTTS local-first safe bypass: cold local LLM skipped', GUARDIAN)
        self.assertIn('XTTS local-first residency priority: skip XTTS release', GUARDIAN)
        self.assertIn('profile["preserve_xtts_for_voice"] = True', MAIN)
        self.assertIn('XTTS local-first conscious social bypass', MAIN)


if __name__ == '__main__':
    unittest.main()
