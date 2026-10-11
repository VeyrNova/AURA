import unittest
from aura_native.google.auth import GOOGLE_SCOPES, GMAIL_READ_SCOPES
from aura_native.mail.gmail_adapter import GmailMailBackend, GMAIL_READ_SCOPE
from aura_native.google.providers import GoogleProviderError

class GoogleScopePolicyTests(unittest.TestCase):
    def test_only_gmail_read_scope_is_added(self):
        self.assertIn(GMAIL_READ_SCOPE,GOOGLE_SCOPES)
        self.assertEqual(set(s for s in GOOGLE_SCOPES if 'gmail' in s),{GMAIL_READ_SCOPE})
        self.assertEqual(GMAIL_READ_SCOPES,(GMAIL_READ_SCOPE,))
    def test_production_backend_writes_are_disabled(self):
        backend=GmailMailBackend.__new__(GmailMailBackend)
        with self.assertRaises(GoogleProviderError) as ctx: backend.send({})
        self.assertEqual(ctx.exception.code,'WRITE_NOT_SUPPORTED')
        with self.assertRaises(GoogleProviderError): backend.create_draft({})

if __name__=='__main__': unittest.main()
