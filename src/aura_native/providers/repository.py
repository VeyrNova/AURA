from __future__ import annotations
from aura_native.storage.database import NativeDatabase
class ProviderSettingsRepository:
 def __init__(self,db:NativeDatabase): self.db=db
 def _ensure(self):
  with self.db.transaction() as c:c.execute('CREATE TABLE IF NOT EXISTS provider_settings (provider_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL, selected_model TEXT NOT NULL, base_url TEXT NOT NULL, is_active INTEGER NOT NULL, configured INTEGER NOT NULL, updated_at TEXT NOT NULL)')
 def load(self):
  self._ensure()
  with self.db.reader() as c:return [dict(x) for x in c.execute('SELECT * FROM provider_settings ORDER BY provider_id')]
 def save(self,provider_id,**values):
  import datetime
  row={'enabled':1,'selected_model':'','base_url':'','is_active':0,'configured':0,**values}
  with self.db.transaction() as c:c.execute('INSERT INTO provider_settings(provider_id,enabled,selected_model,base_url,is_active,configured,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(provider_id) DO UPDATE SET enabled=excluded.enabled,selected_model=excluded.selected_model,base_url=excluded.base_url,is_active=excluded.is_active,configured=excluded.configured,updated_at=excluded.updated_at',(provider_id,int(row['enabled']),row['selected_model'],row['base_url'],int(row['is_active']),int(row['configured']),datetime.datetime.now(datetime.timezone.utc).isoformat()))
