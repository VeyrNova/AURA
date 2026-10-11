import tempfile,unittest
from pathlib import Path
from aura_native.developer_fabric.adf import *
class AuditTests(unittest.TestCase):
 def test_chain_and_tamper(self):
  t=tempfile.TemporaryDirectory(); l=AuditLedger(Path(t.name)/'a.db'); l.append('A'); l.append('B'); self.assertTrue(l.verify_chain()); row=l.conn.execute('select event_id from developer_audit limit 1').fetchone(); l.conn.execute('update developer_audit set metadata=? where event_id=?',('{"x":1}',row[0])); l.conn.commit(); self.assertFalse(l.verify_chain()); l.close(); t.cleanup()
 def test_restart_continuity(self):
  t=tempfile.TemporaryDirectory(); p=Path(t.name)/'a.db'; l=AuditLedger(p); l.append('A'); l.close(); l=AuditLedger(p); l.append('B'); self.assertTrue(l.verify_chain()); l.close(); t.cleanup()
 def test_empty(self):
  t=tempfile.TemporaryDirectory(); l=AuditLedger(Path(t.name)/'a.db'); self.assertTrue(l.verify_chain()); l.close(); t.cleanup()
if __name__=='__main__':unittest.main()
