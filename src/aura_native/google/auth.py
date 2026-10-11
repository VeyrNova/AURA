from __future__ import annotations
import json
import importlib
from datetime import datetime
from threading import Lock
from dataclasses import dataclass
from pathlib import Path
from aura_native.google.models import GoogleAuthState
CALENDAR_SCOPES=("https://www.googleapis.com/auth/calendar",); TASKS_SCOPES=("https://www.googleapis.com/auth/tasks",); GMAIL_READ_SCOPES=("https://www.googleapis.com/auth/gmail.readonly",); GOOGLE_SCOPES=CALENDAR_SCOPES+TASKS_SCOPES+GMAIL_READ_SCOPES; GOOGLE_SCOPE_VERSION="google-scopes-v1"
class GoogleAuthError(Exception):
 def __init__(self,code):self.code=code;super().__init__(code)
@dataclass(frozen=True)
class GoogleOAuthConfig:
 client_file:Path|None=None; scopes:tuple[str,...]=GOOGLE_SCOPES; scope_version:str=GOOGLE_SCOPE_VERSION
 def validate(self):
  if self.client_file is None:return False
  if not self.client_file.exists():raise GoogleAuthError('google_client_file_missing')
  try:data=json.loads(self.client_file.read_text(encoding='utf-8'))
  except (OSError,ValueError):raise GoogleAuthError('google_client_file_invalid')
  if not isinstance(data,dict) or not isinstance(data.get('installed'),dict):raise GoogleAuthError('google_client_file_invalid')
  installed=data['installed']
  if not installed.get('client_id') or not installed.get('auth_uri') or not installed.get('token_uri'):raise GoogleAuthError('google_client_file_invalid')
  return True
@dataclass(frozen=True)
class GoogleCredentialMetadata:
 account_email:str|None; scopes:tuple[str,...]; expiry:str|None; has_refresh_token:bool
def _canonical_expiry(value):
 if value is None or value == '': return value
 if isinstance(value, datetime): return value.strftime('%Y-%m-%dT%H:%M:%S')
 text=str(value)
 for fmt in ('%Y-%m-%dT%H:%M:%S.%f','%Y-%m-%dT%H:%M:%S','%Y-%m-%d %H:%M:%S.%f','%Y-%m-%d %H:%M:%S'):
  try:return datetime.strptime(text,fmt).strftime('%Y-%m-%dT%H:%M:%S')
  except ValueError: pass
 return text
def serialize_credentials(c):
 data={k:c[k] for k in ('token','refresh_token','expiry','scopes','account_email','token_uri','client_id','client_secret') if k in c}
 if 'expiry' in data:data['expiry']=_canonical_expiry(data['expiry'])
 return json.dumps(data,sort_keys=True)
def deserialize_credentials(v):return json.loads(v)
class GoogleCredentialStore:
 def save(self,k,c):raise NotImplementedError
 def load(self,k):raise NotImplementedError
 def delete(self,k):raise NotImplementedError
 def exists(self,k):return self.load(k) is not None
class FakeGoogleCredentialStore(GoogleCredentialStore):
 def __init__(self):self.values={}
 def save(self,k,c):self.values[str(k)]=dict(c)
 def load(self,k):return dict(self.values[k]) if str(k) in self.values else None
 def delete(self,k):self.values.pop(str(k),None)
class KeyringGoogleCredentialStore(GoogleCredentialStore):
 def __init__(self,service='aura-native-google'):self.service=service
 def _keyring(self):
  try:return importlib.import_module('keyring')
  except Exception as exc:raise GoogleAuthError('google_secure_storage_unavailable') from exc
 def save(self,k,c):self._keyring().set_password(self.service,str(k),serialize_credentials(c))
 def load(self,k):
  v=self._keyring().get_password(self.service,str(k));return deserialize_credentials(v) if v else None
 def delete(self,k):self._keyring().delete_password(self.service,str(k))
class GoogleAuthProvider:
 def __init__(self,config=None,store=None,flow_factory=None):self.config=config or GoogleOAuthConfig();self.store=store or KeyringGoogleCredentialStore();self.flow_factory=flow_factory;self._lock=Lock();self._connecting=False
 def is_configured(self):return self.config.validate()
 def load_credentials(self):
  try:self.is_configured()
  except GoogleAuthError:return None
  return self.store.load('default')
 def get_credentials(self):
  """Return google-auth Credentials, keeping keyring storage opaque to providers."""
  data=self.load_credentials()
  if not data:return None
  try:
   mod=importlib.import_module('google.oauth2.credentials')
   installed={}
   if self.config.client_file and self.config.client_file.exists():
    raw=json.loads(self.config.client_file.read_text(encoding='utf-8'))
    installed=raw.get('installed') or raw.get('web') or {}
   info=dict(data)
   if 'expiry' in info: info['expiry']=_canonical_expiry(info['expiry'])
   info.setdefault('token_uri',installed.get('token_uri','https://oauth2.googleapis.com/token'))
   info.setdefault('client_id',installed.get('client_id'))
   info.setdefault('client_secret',installed.get('client_secret'))
   info['scopes']=list(info.get('scopes') or self.config.scopes)
   return mod.Credentials.from_authorized_user_info(info,scopes=info['scopes'])
  except Exception as exc: raise GoogleAuthError('google_credentials_invalid') from exc
 def delete_credentials(self):self.store.delete('default')
 def get_state(self):
  if self.config.client_file is None:return GoogleAuthState(False,False,None,(), 'google_not_configured')
  try:configured=self.is_configured()
  except GoogleAuthError as exc:return GoogleAuthState(False,False,None,(),exc.code)
  c=self.store.load('default')
  if not c:return GoogleAuthState(configured,False,None,tuple(self.config.scopes),'google_auth_required')
  scopes=tuple(c.get('scopes',()))
  required=set(CALENDAR_SCOPES+TASKS_SCOPES)
  if not required.issubset(set(scopes)):return GoogleAuthState(configured,False,c.get('account_email'),scopes,'google_scope_mismatch')
  return GoogleAuthState(True,True,c.get('account_email'),scopes,'')
 def create_authorization_flow(self):self.is_configured();return {'scopes':self.config.scopes,'scope_version':self.config.scope_version}
 def connect(self):
  if not self._lock.acquire(blocking=False):raise GoogleAuthError('google_auth_in_progress')
  try:
   existing=self.store.load('default')
   if existing:
    granted=set(existing.get('scopes',()))
    if set(self.config.scopes).issubset(granted): return self.get_state()
    # The user explicitly invoked the existing reconnect action. Reuse the
    # same OAuth flow to request the newly configured read scope; never loop
    # or trigger this implicitly during startup.
   if not self.is_configured():raise GoogleAuthError('google_not_configured')
   if self.flow_factory is None:
    try:mod=importlib.import_module('google_auth_oauthlib.flow');flow=mod.InstalledAppFlow.from_client_secrets_file(str(self.config.client_file),list(self.config.scopes))
    except Exception as exc:raise GoogleAuthError('google_auth_flow_unavailable') from exc
   else:flow=self.flow_factory(self.config)
   credentials=flow.run_local_server(host='127.0.0.1',port=0,open_browser=True)
   data={'token':getattr(credentials,'token',None),'refresh_token':getattr(credentials,'refresh_token',None),'expiry':_canonical_expiry(getattr(credentials,'expiry',None)),'scopes':list(getattr(credentials,'scopes',None) or self.config.scopes),'account_email':None}
   self.store.save('default',data);return self.get_state()
  except GoogleAuthError:raise
  except Exception as exc:raise GoogleAuthError('google_auth_failed') from exc
  finally:self._lock.release()
