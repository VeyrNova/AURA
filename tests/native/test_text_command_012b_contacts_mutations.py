import tempfile, unittest
from pathlib import Path
from aura_native.contacts.repository import ContactsRepository
from aura_native.contacts.service import ContactsService, ContactsError
from aura_native.contacts.product import ContactsProductService
from aura_native.storage.database import NativeDatabase
from aura_native.storage.prepared_action_repository import PreparedActionRepository
from aura_native.intents.router import NativeIntentRouter

class Contacts012B(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); d=Path(self.t.name)
        self.repo=ContactsRepository(d/'contacts.sqlite'); self.service=ContactsService(self.repo)
        self.actions=PreparedActionRepository(NativeDatabase(d/'actions.sqlite'))
        self.product=ContactsProductService(self.service,self.actions)
    def tearDown(self): self.repo.close(); self.t.cleanup()
    def confirm_execute(self,a): self.actions.confirm(a.action_id); return self.product.execute_prepared_action(a.action_id)
    def test_create_is_prepared_and_exactly_once(self):
        a=self.product.prepare_create('Alice',['alice@example.com']); self.assertEqual([],self.service.list_contacts())
        self.confirm_execute(a); self.assertEqual('executed',self.actions.get(a.action_id).state); self.assertEqual(1,len(self.service.list_contacts()))
        with self.assertRaises(ContactsError): self.product.execute_prepared_action(a.action_id)
    def test_cancel_zero_mutation(self):
        a=self.product.prepare_create('Alice'); self.actions.cancel(a.action_id); self.assertEqual([],self.service.list_contacts())
    def test_update_binds_id_and_version(self):
        c=self.service.create_contact('Alice'); a=self.product.prepare_update(c.contact_id,'Alice Two'); self.assertEqual(c.contact_id,a.payload['contact_id']); self.confirm_execute(a); self.assertEqual('Alice Two',self.service.get_contact(c.contact_id).display_name)
    def test_update_stale_refused(self):
        c=self.service.create_contact('Alice'); a=self.product.prepare_update(c.contact_id,'New'); self.service.update_contact(c.contact_id,'Changed',expected_version=1); self.actions.confirm(a.action_id)
        with self.assertRaises(ContactsError): self.product.execute_prepared_action(a.action_id)
    def test_delete_exact_id_and_cancel(self):
        c=self.service.create_contact('Alice'); a=self.product.prepare_delete('Alice'); self.assertEqual(c.contact_id,a.payload['contact_id']); self.actions.cancel(a.action_id); self.assertIsNotNone(self.service.get_contact(c.contact_id))
    def test_delete_exactly_once(self):
        c=self.service.create_contact('Alice'); a=self.product.prepare_delete(c.contact_id); self.confirm_execute(a); self.assertIsNone(self.repo.get_contact(c.contact_id)); self.assertEqual('executed',self.actions.get(a.action_id).state)
    def test_ambiguity_and_not_found(self):
        self.service.create_contact('Alex'); self.service.create_contact('Alex')
        with self.assertRaises(ContactsError) as e:self.product.prepare_delete('Alex')
        self.assertEqual('AMBIGUOUS',e.exception.code)
        with self.assertRaises(ContactsError) as e:self.product.prepare_delete('missing')
        self.assertEqual('NOT_FOUND',e.exception.code)
    def test_invalid_email_no_action(self):
        with self.assertRaises(ContactsError): self.product.prepare_create('A',['bad'])
        self.assertEqual([],self.service.list_contacts())
    def test_router_mutations_and_reads(self):
        r=NativeIntentRouter(); self.assertEqual('CREATE_CONTACT',r.parse('ajoute un contact Alice avec email alice@example.com').intent); self.assertEqual('DELETE_CONTACT',r.parse('supprime le contact Alice').intent); self.assertEqual('CONTACT_LIST',r.parse('liste mes contacts').intent); self.assertIsNone(r.parse('comment ajouter un contact').intent)
    def test_phone_and_organization_payload(self):
        a=self.product.prepare_create('A',phones=['+33123456789'],organization='Org'); self.assertEqual(['+33123456789'],a.payload['phones']); self.assertEqual('Org',a.payload['organization'])
    def test_no_google_or_network_boundary(self):
        a=self.product.prepare_create('A'); self.assertEqual('aura.contacts',a.tool_name); self.assertTrue(a.requires_confirmation)

if __name__=='__main__': unittest.main()
