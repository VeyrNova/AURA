import unittest

from voice.microphone import MicrophoneRecorder


DEVICES = [
    {"name": "Speakers", "max_input_channels": 0, "default_samplerate": 48000},
    {"name": "Microphone Realtek", "max_input_channels": 2, "default_samplerate": 48000},
    {"name": "Jabra USB Mic", "max_input_channels": 1, "default_samplerate": 44100},
]


class FakeInputOutputPair:
    def __init__(self, input_index, output_index):
        self.input = input_index
        self.output = output_index


class IndexablePair:
    def __init__(self, input_index, output_index):
        self.values = (input_index, output_index)

    def __getitem__(self, index):
        return self.values[index]


class MicrophoneSelectionTests(unittest.TestCase):
    def test_uses_default_input_when_valid(self):
        info = MicrophoneRecorder.choose_input_device(DEVICES, 2, "")
        self.assertIsNotNone(info)
        self.assertEqual(info.index, 2)

    def test_handles_sounddevice_input_output_pair(self):
        pair = FakeInputOutputPair(2, 0)
        info = MicrophoneRecorder.choose_input_device(DEVICES, pair, "")
        self.assertIsNotNone(info)
        self.assertEqual(info.index, 2)

    def test_handles_indexable_pair_object(self):
        pair = IndexablePair(1, 0)
        info = MicrophoneRecorder.choose_input_device(DEVICES, pair, "")
        self.assertEqual(info.index, 1)

    def test_falls_back_to_real_microphone(self):
        devices = [
            {"name": "Mappeur de sons Microsoft - Input", "max_input_channels": 2, "default_samplerate": 44100},
            {"name": "Microphone (Realtek(R) Audio)", "max_input_channels": 2, "default_samplerate": 44100},
            {"name": "Mixage stéréo (Realtek HD Audio Stereo input)", "max_input_channels": 2, "default_samplerate": 48000},
        ]
        info = MicrophoneRecorder.choose_input_device(devices, None, "")
        self.assertEqual(info.index, 1)

    def test_falls_back_to_first_real_input(self):
        info = MicrophoneRecorder.choose_input_device(DEVICES, -1, "")
        self.assertEqual(info.index, 1)

    def test_can_select_by_index(self):
        info = MicrophoneRecorder.choose_input_device(DEVICES, 1, "2")
        self.assertEqual(info.name, "Jabra USB Mic")

    def test_can_select_by_name_fragment(self):
        info = MicrophoneRecorder.choose_input_device(DEVICES, 1, "jabra")
        self.assertEqual(info.index, 2)

    def test_unknown_requested_device_fails_closed(self):
        self.assertIsNone(MicrophoneRecorder.choose_input_device(DEVICES, 1, "does-not-exist"))


if __name__ == "__main__":
    unittest.main()
