from __future__ import annotations
import importlib
from dataclasses import dataclass

class ProviderCredentialError(Exception): pass

class ProviderCredentialStore:
 def set_secret(self,provider_id,secret): raise NotImplementedError
 def get_secret(self,provider_id): raise NotImplementedError
 def has_secret(self,provider_id): return self.get_secret(provider_id) is not None
 def delete_secret(self,provider_id): raise NotImplementedError

class FakeProviderCredentialStore(ProviderCredentialStore):
 def __init__(self): self._values={}
 def set_secret(self,provider_id,secret):
  if not isinstance(secret,str) or not secret: raise ProviderCredentialError('empty_secret')
  self._values[str(provider_id)]=secret
 def get_secret(self,provider_id): return self._values.get(str(provider_id))
 def delete_secret(self,provider_id): self._values.pop(str(provider_id),None)

class KeyringProviderCredentialStore(ProviderCredentialStore):
 def __init__(self,service='aura-native-providers'): self.service=service
 def _keyring(self):
  try:return importlib.import_module('keyring')
  except Exception as exc: raise ProviderCredentialError('secure_storage_unavailable') from exc
 def set_secret(self,provider_id,secret):
  if not isinstance(secret,str) or not secret: raise ProviderCredentialError('empty_secret')
  self._keyring().set_password(self.service,str(provider_id),secret)
 def get_secret(self,provider_id): return self._keyring().get_password(self.service,str(provider_id))
 def delete_secret(self,provider_id):
  try:self._keyring().delete_password(self.service,str(provider_id))
  except Exception: pass

@dataclass(frozen=True)
class ProviderConfig:
 provider_id:str; display_name:str; provider_type:str; enabled:bool=True; configured:bool=False; selected_model:str=''; base_url:str=''; credential_required:bool=True; connection_status:str='not_tested'; last_error_code:str=''
