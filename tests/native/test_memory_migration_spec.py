import sqlite3, tempfile, unittest
from pathlib import Path
from aura_native.migration.memory_legacy import *
class MigrationSpecTests(unittest.TestCase):
 def setUp(self): self.r=LegacyMemoryRecord(1,'Préférence café','preference',4,.8,'legacy','2024-01-01','2024-01-02')
 def test_direct_field_mapping(self): c=plan([self.r]).candidates[0]; self.assertEqual(c.native_content,'Préférence café')
 def test_unicode(self): self.assertEqual(plan([self.r]).candidates[0].native_content,'Préférence café')
 def test_type_mapping(self): self.assertEqual(plan([self.r]).candidates[0].native_memory_type,'preference')
 def test_scope_mapping(self): self.assertEqual(plan([self.r]).candidates[0].native_scope,'user')
 def test_timestamps(self): c=plan([self.r]).candidates[0]; self.assertEqual(c.created_at,'2024-01-01'); self.assertEqual(c.updated_at,'2024-01-02')
 def test_provenance(self): self.assertEqual(plan([self.r]).candidates[0].native_source,'legacy_aura')
 def test_stable_identity(self): self.assertEqual(plan([self.r]).candidates[0].legacy_id,'1')
 def test_idempotent_repeat(self): self.assertEqual(plan([self.r],migrated_legacy_ids=['1']).already_migrated,1)
 def test_duplicate_classification(self): self.assertEqual(plan([self.r,LegacyMemoryRecord(2,'Préférence café','preference')]).possible_duplicates,1)
 def test_conflicts_are_not_updates(self): x=plan([self.r],native_contents=['Préférence café']); self.assertEqual(x.would_update,0); self.assertEqual(x.possible_duplicates,1)
 def test_invalid_row(self): self.assertEqual(plan([LegacyMemoryRecord(3,None)]).invalid,1)
 def test_unsupported_type(self): self.assertEqual(plan([LegacyMemoryRecord(4,'x','alien')]).unsupported,1)
 def test_deleted_row(self): self.assertEqual(plan([LegacyMemoryRecord(5,'x',status='DELETED')]).unsupported,1)
 def test_preference_is_explicit(self): self.assertEqual(plan([self.r]).candidates[0].native_memory_type,'preference')
 def test_fingerprint_deterministic(self): self.assertEqual(fingerprint(self.r),fingerprint(self.r))
 def test_version(self): self.assertEqual(MIGRATION_VERSION,'legacy_memory_to_native_v1')
 def test_counts(self): x=plan([self.r]); self.assertEqual((x.source_records,x.eligible,x.would_insert),(1,1,1))
 def test_zero_destination_writes(self): x=plan([self.r]); self.assertEqual(x.would_update,0)
 def test_privacy_safe_candidate(self): self.assertNotIn('Préférence café',fingerprint(self.r))
 def test_read_only_synthetic_source(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'legacy.db'; c=sqlite3.connect(p); c.execute('create table memories(id integer,content text,type text,importance integer,confidence real,source text,created_at text,updated_at text,status text,is_sensitive integer)'); c.execute("insert into memories values(1,'fake','fact',1,1,'test','a','a','ACTIVE',0)"); c.commit(); c.close(); rows=read_synthetic_source_read_only(p); self.assertEqual(len(rows),1)
   ro=sqlite3.connect(f'file:{p.as_posix()}?mode=ro',uri=True)
   try:
    with self.assertRaises(sqlite3.OperationalError): ro.execute("insert into memories values(2,'x','fact',1,1,'t','a','a','ACTIVE',0)")
   finally: ro.close()
 def test_malformed_schema(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bad.db'; sqlite3.connect(p).close()
   with self.assertRaises(sqlite3.OperationalError): read_synthetic_source_read_only(p)
 def test_null_scope_is_rejected(self): self.assertEqual(plan([LegacyMemoryRecord(6,'x',scope='session',scope_id='s')]).unsupported,1)
 def test_confidence_range(self): self.assertEqual(plan([LegacyMemoryRecord(7,'x',confidence=2)]).invalid,1)
 def test_no_raw_logging_contract(self): self.assertEqual(plan([self.r]).candidates[0].reason,'')
if __name__=='__main__': unittest.main()
