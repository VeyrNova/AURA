import os
import unittest
from unittest.mock import MagicMock, patch
from voice.xtts_tts import XTTSTTS

class XTTSGPUVoiceLabTests(unittest.TestCase):
    def test_cuda_remains_explicit_opt_in(self):
        torch=MagicMock(); torch.cuda.is_available.return_value=True
        with self.assertRaises(Exception):
            XTTSTTS.resolve_device('cuda', False, torch)

    def test_cuda_selected_after_opt_in_and_availability(self):
        torch=MagicMock(); torch.cuda.is_available.return_value=True
        self.assertEqual(XTTSTTS.resolve_device('cuda', True, torch),'cuda')

    def test_preview_method_exists(self):
        self.assertTrue(hasattr(XTTSTTS,'speak_preview'))

    def test_runtime_info_method_exists(self):
        self.assertTrue(hasattr(XTTSTTS,'runtime_info'))

if __name__=='__main__': unittest.main()
