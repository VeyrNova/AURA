import unittest
from unittest.mock import MagicMock

from voice.errors import SpeechSynthesisUnavailableError
from voice.xtts_tts import XTTSTTS


class XTTSSafetyTests(unittest.TestCase):
    def test_auto_is_cpu_without_touching_cuda(self):
        torch = MagicMock()
        device = XTTSTTS.resolve_device('auto', False, torch)
        self.assertEqual(device, 'cpu')
        torch.cuda.is_available.assert_not_called()

    def test_cpu_is_cpu_without_touching_cuda(self):
        torch = MagicMock()
        device = XTTSTTS.resolve_device('cpu', False, torch)
        self.assertEqual(device, 'cpu')
        torch.cuda.is_available.assert_not_called()

    def test_cuda_requires_explicit_opt_in(self):
        torch = MagicMock()
        with self.assertRaises(SpeechSynthesisUnavailableError):
            XTTSTTS.resolve_device('cuda', False, torch)
        torch.cuda.is_available.assert_not_called()

    def test_cuda_opt_in_still_requires_available_cuda(self):
        torch = MagicMock()
        torch.cuda.is_available.return_value = False
        with self.assertRaises(SpeechSynthesisUnavailableError):
            XTTSTTS.resolve_device('cuda', True, torch)

    def test_cuda_opt_in_can_select_cuda_after_probe(self):
        torch = MagicMock()
        torch.cuda.is_available.return_value = True
        self.assertEqual(XTTSTTS.resolve_device('cuda', True, torch), 'cuda')


if __name__ == '__main__':
    unittest.main()
