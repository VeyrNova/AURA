import unittest
from pathlib import Path

ROOT=Path(__file__).parents[2]

class MapsMailClassificationTests(unittest.TestCase):
    def test_maps_is_explicitly_not_native_functionality(self):
        modules=(ROOT/'app/qml/views/ModulesView.qml').read_text(encoding='utf-8')
        native=(ROOT/'app/qml/views/NativeWorkspaceView.qml').read_text(encoding='utf-8')
        self.assertIn('key: "maps"',modules)
        self.assertNotIn('MapsView {',native)

    def test_mail_native_parity_is_not_claimed(self):
        bridge=(ROOT/'src/aura_native/ui/qt_bridge.py').read_text(encoding='utf-8')
        registry=(ROOT/'src/aura_native/tools/registry.py').read_text(encoding='utf-8')
        self.assertNotIn('gmail',bridge.lower())
        self.assertNotIn('mail.search',registry.lower())

if __name__=='__main__': unittest.main()
