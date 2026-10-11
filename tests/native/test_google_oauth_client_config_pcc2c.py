import json, tempfile, unittest
from pathlib import Path
from aura_native.google.oauth_client_config import GoogleOAuthClientConfigService, OAuthClientConfigError, validate_client_file

ROOT=Path(__file__).parents[2]; FIX=ROOT/'tests/native/fixtures/oauth'
class GoogleOAuthClientConfigPcc2cTests(unittest.TestCase):
    def test_validation_codes(self):
        self.assertTrue(validate_client_file(FIX/'valid_installed_client.json').client_id_present)
        for name, code in [('invalid_json.json','invalid_json'),('web_client_only.json','unsupported_oauth_client_type'),('missing_client_id.json','missing_client_id')]:
            with self.assertRaises(OAuthClientConfigError) as ctx: validate_client_file(FIX/name)
            self.assertEqual(ctx.exception.code, code)
    def test_atomic_import_and_invalid_replacement_preserves_old(self):
        with tempfile.TemporaryDirectory() as d:
            s=GoogleOAuthClientConfigService(Path(d)); s.import_client(FIX/'valid_installed_client.json')
            old=s.active_path.read_bytes()
            with self.assertRaises(OAuthClientConfigError): s.import_client(FIX/'invalid_json.json', replace=True)
            self.assertEqual(s.active_path.read_bytes(), old)
            s.import_client(FIX/'valid_installed_client.json', replace=True)
            self.assertTrue(s.status()['configured'])
    def test_isolated_root_and_no_secret_in_errors(self):
        with tempfile.TemporaryDirectory() as d:
            s=GoogleOAuthClientConfigService(Path(d)); self.assertEqual(s.root,Path(d));
            with self.assertRaises(OAuthClientConfigError) as ctx: s.import_client(FIX/'web_client_only.json')
            self.assertNotIn('fake-client-secret', str(ctx.exception)); self.assertNotIn('AURA GPT version', str(ctx.exception))
if __name__=='__main__': unittest.main()
