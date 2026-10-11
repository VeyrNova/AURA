"""Native voice contracts and an offline-safe controller.

No provider is loaded, no device is opened, and no process is started at import
time. Real audio adapters can be supplied explicitly in a later lot.
"""
from .models import VoiceState, VoiceEvent, VoiceResult
from .providers import AudioInputAdapter, STTProvider, TTSProvider, FakeSTT, FakeTTS
from .controller import VoiceController

__all__ = [
    "VoiceState", "VoiceEvent", "VoiceResult", "AudioInputAdapter",
    "STTProvider", "TTSProvider", "FakeSTT", "FakeTTS", "VoiceController",
]
