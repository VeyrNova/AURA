import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from consciousness.self_model import CapabilityState, SelfModel
from voice.speech_to_text import FasterWhisperSTT
from voice.text_to_speech import PiperTTS


class VoiceModelTests(unittest.TestCase):
    def test_self_model_can_report_voice_subcapabilities(self):
        model = SelfModel(CapabilityState(voice=True, voice_input=True, voice_output=True))
        self.assertTrue(model.has_capability("voice"))
        self.assertTrue(model.has_capability("voice_input"))
        self.assertTrue(model.has_capability("voice_output"))

    def test_whisper_model_ready_requires_model_bin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stt = FasterWhisperSTT()
            with patch.object(stt, "model_path", return_value=root):
                self.assertFalse(stt.model_ready())
                (root / "model.bin").write_bytes(b"x")
                self.assertTrue(stt.model_ready())

    def test_piper_model_ready_requires_model_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "voice.onnx"
            tts = PiperTTS()
            with patch.object(tts, "model_path", return_value=model):
                self.assertFalse(tts.model_ready())
                model.write_bytes(b"x")
                self.assertFalse(tts.model_ready())
                Path(str(model) + ".json").write_text("{}", encoding="utf-8")
                self.assertTrue(tts.model_ready())


if __name__ == "__main__":
    unittest.main()
