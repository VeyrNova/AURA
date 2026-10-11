import unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class GoogleReauthorizeUiTests(unittest.TestCase):
    def test_reauthorize_is_separate_from_client_import(self):
        source=(ROOT/'app/qml/views/ProviderIntegrationsView.qml').read_text(encoding='utf-8')
        self.assertIn('objectName:"nativeGoogleReauthorize"',source)
        self.assertIn('RÉAUTORISER GOOGLE',source)
        self.assertIn('onClicked:bridge.startGoogleWorkspaceOAuth()',source)
        self.assertIn('onClicked:oauthDialog.open()',source)
        self.assertIn('Met à jour les autorisations du compte Google connecté.',source)
        self.assertNotIn('onClicked:bridge.importGoogleOAuthClient',source)
if __name__=='__main__':unittest.main()
