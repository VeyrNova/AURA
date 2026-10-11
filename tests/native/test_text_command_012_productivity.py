import unittest
from aura_native.intents.router import NativeIntentRouter

class TextCommand012ProductivityTests(unittest.TestCase):
    def setUp(self): self.r=NativeIntentRouter()
    def test_mail_read_routes(self):
        self.assertEqual(self.r.parse('montre mes derniers mails').intent,'MAIL_LIST')
        a=self.r.parse('cherche les mails de Dupont'); self.assertEqual(a.intent,'MAIL_SEARCH'); self.assertEqual(a.slots['query'],'Dupont')
        self.assertEqual(self.r.parse('lis le mail msg-001').slots['message_id'],'msg-001')
    def test_calendar_read_routes(self):
        self.assertEqual(self.r.parse("qu'ai-je aujourd'hui").intent,'CALENDAR_FOR_DATE')
        self.assertEqual(self.r.parse('quels rendez-vous demain').slots['date'],'tomorrow')
        self.assertEqual(self.r.parse('liste mon agenda').intent,'CALENDAR_LIST')
        self.assertEqual(self.r.parse('cherche un événement dentiste').slots['query'],'dentiste')
    def test_contacts_read_routes(self):
        self.assertEqual(self.r.parse('liste mes contacts').intent,'CONTACT_LIST')
        a=self.r.parse('cherche Dupont dans mes contacts'); self.assertEqual(a.intent,'CONTACT_SEARCH'); self.assertEqual(a.slots['query'],'Dupont')
        self.assertEqual(self.r.parse('ouvre le contact ctc-001').slots['contact_id'],'ctc-001')
    def test_domains_do_not_conflict(self):
        self.assertEqual(self.r.parse('cherche Dupont sur internet').intent,'WEB_SEARCH')
        self.assertIsNone(self.r.parse('comment fonctionne Gmail ?').intent)
        self.assertIsNone(self.r.parse("qu'est-ce qu'un calendrier").intent)
        self.assertIsNone(self.r.parse('comment organiser mes contacts').intent)
    def test_text_voice_parity(self):
        for text in ('montre mes derniers mails','liste mon agenda','cherche Dupont dans mes contacts'):
            a=self.r.parse(text,source='keyboard'); b=self.r.parse(text,source='voice'); self.assertEqual(a.intent,b.intent); self.assertEqual(a.slots,b.slots)
    def test_google_writes_are_not_new_read_intents(self):
        for text in ('envoie un mail à dupont@example.com','crée un événement demain'):
            self.assertNotIn(self.r.parse(text).intent, {'MAIL_LIST','MAIL_SEARCH','MAIL_READ','CALENDAR_LIST','CALENDAR_FOR_DATE','CALENDAR_SEARCH'})

if __name__=='__main__': unittest.main()
