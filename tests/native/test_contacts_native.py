from __future__ import annotations
import tempfile
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from aura_native.contacts import ContactsRepository, ContactsService, ContactsError
from aura_native.contacts.qt_bridge import NativeContactsBridge

class ContactsTests(unittest.TestCase):
  def setUp(self):
    self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tests/native/_evidence'); self.service=ContactsService(ContactsRepository(Path(self.tmp.name)/'contacts.sqlite'))
  def tearDown(self):
    self.service.repository.close(); self.tmp.cleanup()
  def test_repository_crud_and_persistence(self):
    service=self.service; self.assertEqual(service.list_contacts(),[])
    c=service.create_contact('Alice Example',['alice@example.com'],['+33123456789'],'Acme','note')
    self.assertEqual(service.get_contact(c.contact_id).display_name,'Alice Example')
    self.assertEqual(service.search_contacts('ACME')[0].contact_id,c.contact_id)
    c2=service.update_contact(c.contact_id,'Alice Example',['alice@example.com'],['+33123456789'],'Acme 2','note',1)
    self.assertEqual(c2.version,2)
    with self.assertRaises(ContactsError): service.delete_contact(c.contact_id)
    self.assertTrue(service.delete_contact(c.contact_id,True))
    with self.assertRaises(ContactsError): service.delete_contact(c.contact_id,True)

  def test_validation_duplicates_and_stable_reopen(self):
    service=self.service
    c=service.create_contact("Élodie O'Neil",['elodie@example.com'],['+1 555 0100'],'A-1')
    with self.assertRaises(ContactsError): service.create_contact('Bad',['wrong'],[])
    with self.assertRaises(ContactsError): service.create_contact('Other',['ELODIE@example.com'],[])
    path=service.repository.path; service.repository.close(); reopened=ContactsService(ContactsRepository(path)); self.assertEqual(reopened.get_contact(c.contact_id).contact_id,c.contact_id); reopened.repository.close()

  def test_repository_constructor_is_lazy(self):
    p=Path(self.tmp.name)/'nested'/'contacts.sqlite'; r=ContactsRepository(p); self.assertFalse(p.exists()); self.assertFalse(p.parent.exists()); self.assertEqual(r.list_contacts(),[]); self.assertTrue(p.exists()); r.close()

  def test_bridge_optimistic_concurrency(self):
    bridge=NativeContactsBridge(self.service)
    self.assertTrue(bridge.createContact('Alice Example','alice@example.com','+33123456789','Acme',''))
    cid=bridge.selected['contact_id']; version=bridge.selected['version']
    self.assertTrue(bridge.updateContact(cid,'Alice Example','alice@example.com','+33123456789','Acme 2','',version))
    self.assertEqual(bridge.selected['version'],version+1)
    self.assertFalse(bridge.updateContact(cid,'Alice Example','alice@example.com','+33123456789','Stale','',version))
    self.assertEqual(bridge.errorCode,'EXTERNAL_CHANGE')
    self.assertTrue(bridge.updateContact(cid,'Alice Example','alice@example.com','+33123456789','Acme 3','',version+1))

if __name__=='__main__': unittest.main()
