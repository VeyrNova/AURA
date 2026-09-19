"""Safe voice errors shown to the user without leaking technical details."""


class VoiceError(RuntimeError):
    """Base class for expected voice subsystem failures."""


class MicrophoneUnavailableError(VoiceError):
    pass


class SpeechRecognitionUnavailableError(VoiceError):
    pass


class SpeechSynthesisUnavailableError(VoiceError):
    pass
