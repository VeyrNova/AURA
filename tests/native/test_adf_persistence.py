import tempfile,unittest
from pathlib import Path
from aura_native.developer_fabric.project_picker import *
class PickerTests(unittest.TestCase):
 def test_valid_and_cancel(self):
  t=tempfile.TemporaryDirectory(); self.assertEqual(FakeProjectPicker(t.name).choose(),Path(t.name).resolve()); self.assertIsNone(FakeProjectPicker().choose()); t.cleanup()
 def test_invalid(self):
  with self.assertRaises(ValueError): FakeProjectPicker('missing').choose()
 def test_legacy(self):
  with self.assertRaises(ValueError): ProjectPickerService().validate(r'C:\AURA GPT version')
if __name__=='__main__':unittest.main()
