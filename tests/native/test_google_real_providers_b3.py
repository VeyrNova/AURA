from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path
from aura_native.google.auth import GoogleAuthProvider, GoogleOAuthConfig, FakeGoogleCredentialStore, serialize_credentials

from aura_native.google.providers import GoogleProviderError
from aura_native.google.real_providers import GoogleCalendarProvider, GoogleTasksProvider, map_google_error


class Auth:
    def __init__(self, credentials=None): self.credentials = credentials
    def load_credentials(self): return self.credentials
    def get_credentials(self):
        from google.oauth2.credentials import Credentials
        return Credentials(token='offline-token') if self.credentials else None


class Request:
    def __init__(self, value): self.value = value
    def execute(self): return self.value


class Events:
    def __init__(self, pages): self.pages = list(pages); self.calls = []
    def list(self, **kwargs): self.calls.append(kwargs); return Request(self.pages.pop(0))


class CalendarService:
    def __init__(self, pages, busy=()): self.events_resource = Events(pages); self.busy = busy
    def events(self): return self.events_resource
    def freebusy(self): return self
    def query(self, **kwargs): self.query_kwargs = kwargs; return Request({'calendars': {'primary': {'busy': list(self.busy)}}})


class TasksResource:
    def __init__(self, pages): self.pages = list(pages); self.calls = []
    def list(self, **kwargs): self.calls.append(kwargs); return Request(self.pages.pop(0))


class TasksService:
    def __init__(self, pages): self.tasks_resource = TasksResource(pages)
    def tasklists(self): return self
    def list(self, **kwargs): return Request({'items': [{'id': 'default'}]})
    def tasks(self): return self.tasks_resource


class RealProviderB3Tests(unittest.TestCase):
 def test_calendar_pagination_and_normalization(self):
    service = CalendarService([
        {'items': [{'id': '1', 'summary': 'A', 'start': {'dateTime': '2026-10-02T15:00:00+02:00', 'timeZone': 'Europe/Paris'}, 'end': {'dateTime': '2026-10-02T16:00:00+02:00'}}], 'nextPageToken': 'next'},
        {'items': [{'id': '2', 'start': {'date': '2026-10-03'}, 'end': {'date': '2026-10-04'}}]},
    ])
    p = GoogleCalendarProvider(Auth({'token': 'x'}), build=lambda *a, **k: service)
    events = p.list_events('2026-10-01T00:00:00Z', '2026-10-05T00:00:00Z')
    self.assertEqual([e.event_id for e in events], ['1', '2']); self.assertEqual(events[0].timezone, 'Europe/Paris'); self.assertEqual(events[1].start, '2026-10-03'); self.assertEqual(service.events_resource.calls[1]['pageToken'], 'next')


 def test_calendar_freebusy_and_missing_fields(self):
    service = CalendarService([{'items': []}], busy=[{'start': 'a', 'end': 'b'}])
    p = GoogleCalendarProvider(Auth({'token': 'x'}), build=lambda *a, **k: service)
    self.assertEqual(p.find_free_time('a', 'c')[0].start, 'a')
    event = p._event({'id': 'x'})
    self.assertEqual((event.title, event.start), ('Sans titre', ''))


 def test_calendar_requires_auth_and_is_read_only(self):
    p = GoogleCalendarProvider(Auth(), build=lambda *a, **k: None)
    with self.assertRaisesRegex(GoogleProviderError, 'google_auth_required'): p.list_events()
    self.assertTrue(callable(p.create_event))


 def test_tasks_default_list_pagination_and_missing_fields(self):
    service = TasksService([{'items': [{'id': 't1', 'title': 'One'}], 'nextPageToken': 'p'}, {'items': [{'id': 't2', 'status': 'completed', 'completed': '2026-10-01T00:00:00Z'}]}])
    p = GoogleTasksProvider(Auth({'token': 'x'}), build=lambda *a, **k: service)
    tasks = p.list_tasks()
    self.assertEqual([t.task_id for t in tasks], ['t1', 't2']); self.assertEqual(tasks[0].title, 'One'); self.assertIsNone(tasks[0].due); self.assertEqual(service.tasks_resource.calls[1]['pageToken'], 'p')


 def test_tasks_requires_auth_and_is_read_only(self):
    p = GoogleTasksProvider(Auth(), build=lambda *a, **k: None)
    with self.assertRaisesRegex(GoogleProviderError, 'google_auth_required'): p.list_tasks()
    self.assertTrue(callable(p.create_task))


 def test_error_mapping_is_normalized(self):
    class E: pass
    for status, expected in ((401, 'google_auth_expired'), (403, 'google_permission_denied'), (429, 'google_rate_limited'), (500, 'google_network_error')):
        e = E(); e.resp = type('R', (), {'status': status})()
        self.assertEqual(map_google_error(e), expected)
    self.assertEqual(map_google_error(ValueError('bad')), 'google_invalid_response')


 def test_empty_tasklist_is_invalid_response(self):
    class Empty(TasksService):
        def list(self, **kwargs): return Request({'items': []})
    p = GoogleTasksProvider(Auth({'token': 'x'}), build=lambda *a, **k: Empty([]))
    with self.assertRaisesRegex(GoogleProviderError, 'google_invalid_response'): p.list_tasks()


 def test_build_receives_official_service_identifiers(self):
    seen = []
    def build(*args, **kwargs): seen.append((args, kwargs)); return CalendarService([{'items': []}])
    GoogleCalendarProvider(Auth({'token': 'x'}), build=build).list_events()
    from google.oauth2.credentials import Credentials
    self.assertEqual(seen[0][0], ('calendar', 'v3')); self.assertIsInstance(seen[0][1]['credentials'], Credentials); self.assertFalse(isinstance(seen[0][1]['credentials'], dict))

 def test_auth_store_roundtrip_returns_google_credentials(self):
    with tempfile.TemporaryDirectory() as d:
        client=Path(d)/'client.json'; client.write_text(json.dumps({'installed': {'client_id':'id','client_secret':'secret','auth_uri':'a','token_uri':'https://oauth2.googleapis.com/token'}}), encoding='utf-8')
        store=FakeGoogleCredentialStore(); store.save('default', {'token':'offline','refresh_token':'refresh','scopes':['scope']})
        auth=GoogleAuthProvider(GoogleOAuthConfig(client_file=client, scopes=('scope',)), store=store)
        credentials=auth.get_credentials()
        self.assertEqual(credentials.token, 'offline'); self.assertEqual(credentials.refresh_token, 'refresh'); self.assertEqual(credentials.scopes, ['scope'])

 def test_legacy_and_canonical_expiry_are_accepted(self):
    with tempfile.TemporaryDirectory() as d:
        client=Path(d)/'client.json'; client.write_text(json.dumps({'installed': {'client_id':'id','client_secret':'secret','auth_uri':'a','token_uri':'https://oauth2.googleapis.com/token'}}), encoding='utf-8')
        for expiry in ('2026-09-29 19:26:09', '2026-09-29T19:26:09'):
            store=FakeGoogleCredentialStore(); store.save('default', {'token':'offline','refresh_token':'refresh','expiry':expiry,'scopes':['scope']})
            auth=GoogleAuthProvider(GoogleOAuthConfig(client_file=client, scopes=('scope',)), store=store)
            self.assertIsNotNone(auth.get_credentials())

 def test_expiry_none_and_future_serialization(self):
    self.assertIn('"expiry": null', serialize_credentials({'token':'x','expiry':None}))
    self.assertIn('2026-09-29T19:26:09', serialize_credentials({'token':'x','expiry':'2026-09-29 19:26:09'}))
