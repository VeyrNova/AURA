from __future__ import annotations
from dataclasses import replace
from aura_native.providers.credentials import ProviderCredentialStore,ProviderCredentialError,ProviderConfig

class ProviderSettingsService:
 def __init__(self,store:ProviderCredentialStore,configs=(),repository=None): self.store=store; self.repository=repository; self._configs={c.provider_id:c for c in configs}; self._active=''; self._model=''; self._loaded=False
 def _load(self):
  if self._loaded:return
  self._loaded=True
  for row in self.repository.load() if self.repository else ():
   c=self._configs.get(row['provider_id'])
   if c:self._configs[c.provider_id]=replace(c,enabled=bool(row['enabled']),selected_model=row['selected_model'],base_url=row['base_url'],configured=self.store.has_secret(c.provider_id));
   if row['is_active']: self._active=row['provider_id']; self._model=row['selected_model']
 def configs(self): self._load(); return tuple(self._configs.values())
 def config(self,provider_id): self._load(); return self._configs.get(provider_id)
 def save_api_key(self,provider_id,secret):
  self.store.set_secret(provider_id,secret); c=self._configs.get(provider_id)
  if c:self._configs[provider_id]=replace(c,configured=True,connection_status='configured',last_error_code='')
  if self.repository:self.repository.save(provider_id,configured=1)
 def remove_api_key(self,provider_id):
  self.store.delete_secret(provider_id); c=self._configs.get(provider_id)
  if c:self._configs[provider_id]=replace(c,configured=False,connection_status='not_configured')
  if self.repository:self.repository.save(provider_id,configured=0)
 def provider_configured(self,provider_id): return self.store.has_secret(provider_id) if (self.config(provider_id) or True) else False
 def set_active(self,provider_id,model=''):
  c=self._configs.get(provider_id)
  if not c: raise ProviderCredentialError('unknown_provider')
  self._configs[provider_id]=replace(c,selected_model=model or c.selected_model,enabled=True)
  self._active=provider_id; self._model=model or c.selected_model
  if self.repository:
   for pid in self._configs:self.repository.save(pid,is_active=int(pid==provider_id),selected_model=self._configs[pid].selected_model)
 def get_active_provider(self): self._load(); return self._active
 def set_active_provider(self,provider_id): self.set_active(provider_id)
 def get_active_model(self): self._load(); return self._model
 def set_active_model(self,provider_id,model):
  self._load(); c=self._configs.get(provider_id)
  if not c: raise ProviderCredentialError('unknown_provider')
  self._configs[provider_id]=replace(c,selected_model=str(model or ''))
  if provider_id==self._active: self._model=str(model or '')
  if self.repository:self.repository.save(provider_id,selected_model=str(model or ''),is_active=int(provider_id==self._active))
 def set_provider_base_url(self,provider_id,url):
  self._load(); c=self._configs.get(provider_id)
  if not c: raise ProviderCredentialError('unknown_provider')
  value=str(url or '').strip().rstrip('/')
  self._configs[provider_id]=replace(c,base_url=value)
  if self.repository:self.repository.save(provider_id,base_url=value)
 def get_provider_config(self,provider_id): self._load(); return self._configs.get(provider_id)
 def list_provider_configs(self): return self.configs()
