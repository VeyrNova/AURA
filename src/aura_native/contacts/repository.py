from __future__ import annotations
import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .models import Contact

class ContactsRepository:
    def __init__(self, path):
        self.path = Path(path); self._conn = None
    def initialize(self):
        if self._conn: return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.execute("PRAGMA user_version=1")
        self._conn.execute("CREATE TABLE IF NOT EXISTS contacts (contact_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, emails_json TEXT NOT NULL, phones_json TEXT NOT NULL, organization TEXT NOT NULL, notes TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL)")
        self._conn.commit()
    def _ensure(self): self.initialize()
    def close(self):
        if self._conn: self._conn.close(); self._conn = None
    def _row(self, r):
        return Contact(r[0], r[1], tuple(json.loads(r[2])), tuple(json.loads(r[3])), r[4], r[5], r[6], r[7], int(r[8]))
    def list_contacts(self):
        self._ensure(); return [self._row(r) for r in self._conn.execute("SELECT * FROM contacts ORDER BY display_name COLLATE NOCASE, contact_id")]
    def search_contacts(self, query):
        q = str(query or "").casefold().strip()
        return [c for c in self.list_contacts() if not q or q in " ".join((c.display_name,c.organization,c.notes,*c.emails,*c.phones)).casefold()]
    def get_contact(self, contact_id):
        self._ensure(); r=self._conn.execute("SELECT * FROM contacts WHERE contact_id=?",(str(contact_id),)).fetchone(); return self._row(r) if r else None
    def create_contact(self, display_name, emails=(), phones=(), organization="", notes=""):
        self._ensure(); now=datetime.now(timezone.utc).isoformat(); cid=str(uuid4()); c=Contact(cid,display_name,tuple(emails),tuple(phones),organization,notes,now,now,1)
        self._conn.execute("INSERT INTO contacts VALUES (?,?,?,?,?,?,?,?,?)",(c.contact_id,c.display_name,json.dumps(c.emails),json.dumps(c.phones),c.organization,c.notes,c.created_at,c.updated_at,c.version)); self._conn.commit(); return c
    def update_contact(self, contact_id, display_name, emails, phones, organization, notes, expected_version):
        self._ensure(); old=self.get_contact(contact_id)
        if not old:return None
        now=datetime.now(timezone.utc).isoformat(); c=Contact(old.contact_id,display_name,tuple(emails),tuple(phones),organization,notes,old.created_at,now,old.version+1)
        cur=self._conn.execute("UPDATE contacts SET display_name=?,emails_json=?,phones_json=?,organization=?,notes=?,updated_at=?,version=? WHERE contact_id=? AND version=?",(c.display_name,json.dumps(c.emails),json.dumps(c.phones),c.organization,c.notes,c.updated_at,c.version,c.contact_id,int(expected_version))); self._conn.commit()
        return c if cur.rowcount else None
    def delete_contact(self, contact_id):
        self._ensure(); cur=self._conn.execute("DELETE FROM contacts WHERE contact_id=?",(str(contact_id),)); self._conn.commit(); return bool(cur.rowcount)
