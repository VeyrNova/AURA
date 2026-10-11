import tempfile,unittest
from pathlib import Path
from aura_native.developer_fabric.adf import AuditLedger
class Tamper(unittest.TestCase):
 def make(self):
  t=tempfile.TemporaryDirectory(); l=AuditLedger(Path(t.name)/'a.db'); l.append('A',job_id='j1'); l.append('B',job_id='j2'); return t,l
 def test_metadata(self): t,l=self.make(); l.conn.execute("update developer_audit set metadata='{""x"":1}' where sequence=1"); l.conn.commit(); self.assertFalse(l.verify_chain()); l.close(); t.cleanup()
 def test_delete(self): t,l=self.make(); l.conn.execute('delete from developer_audit where sequence=1'); l.conn.commit(); self.assertFalse(l.verify_chain()); l.close(); t.cleanup()
 def test_insert(self): t,l=self.make(); l.conn.execute("insert into developer_audit(event_id,job_id,timestamp,event_type,metadata,prev_hash,hash,sequence) values('x','x',0,'X','{}','','x',3)"); l.conn.commit(); self.assertFalse(l.verify_chain()); l.close(); t.cleanup()
 def test_reorder(self): t,l=self.make(); l.conn.execute('update developer_audit set sequence=3 where sequence=1'); l.conn.commit(); self.assertFalse(l.verify_chain()); l.close(); t.cleanup()
 def test_hash(self): t,l=self.make(); l.conn.execute("update developer_audit set hash='bad' where sequence=1"); l.conn.commit(); self.assertFalse(l.verify_chain()); l.close(); t.cleanup()
 def test_prev(self): t,l=self.make(); l.conn.execute("update developer_audit set prev_hash='bad' where sequence=2"); l.conn.commit(); self.assertFalse(l.verify_chain()); l.close(); t.cleanup()
 def test_sequence_gap(self): t,l=self.make(); l.conn.execute('update developer_audit set sequence=4 where sequence=2'); l.conn.commit(); self.assertFalse(l.verify_chain()); l.close(); t.cleanup()
if __name__=='__main__': unittest.main()

