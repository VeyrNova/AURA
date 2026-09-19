from __future__ import annotations
import unittest
from unittest.mock import patch
import runtime.ollama_gpu_diagnostics as mod

class OllamaGpuDiagnosticsTests(unittest.TestCase):
    def test_nvidia_process_confirmation(self):
        with patch.object(mod,'_nvidia_snapshot',return_value=(True,'RTX 4050',2200.0,6141.0,42.0,(123,))), patch.object(mod,'_ollama_pids_windows',return_value=(123,)):
            d=mod.collect_ollama_gpu_diagnostic()
        self.assertTrue(d.ollama_on_nvidia)
        self.assertEqual(d.verdict,'nvidia-process-confirmed')
        self.assertEqual(d.nvidia_used_mb,2200.0)

    def test_ollama_not_seen_on_nvidia(self):
        with patch.object(mod,'_nvidia_snapshot',return_value=(True,'RTX 4050',0.0,6141.0,0.0,(999,))), patch.object(mod,'_ollama_pids_windows',return_value=(123,)):
            d=mod.collect_ollama_gpu_diagnostic()
        self.assertFalse(d.ollama_on_nvidia)
        self.assertEqual(d.verdict,'ollama-not-seen-on-nvidia')

    def test_no_shell_user_command_surface(self):
        with patch.object(mod.subprocess,'run') as run:
            run.return_value.returncode=0; run.return_value.stdout=''
            mod._run_fixed(['fixed','arg'])
        self.assertFalse(run.call_args.kwargs['shell'])
        self.assertEqual(run.call_args.args[0],['fixed','arg'])

    def test_format_contains_verdict(self):
        d=mod.OllamaGpuDiagnostic(verdict='ollama-not-seen-on-nvidia')
        self.assertIn('ollama-not-seen-on-nvidia',mod.format_ollama_gpu_diagnostic(d))

if __name__=='__main__': unittest.main()
