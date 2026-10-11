from __future__ import annotations
import re, unicodedata
from .models import Contact

class ContactsError(Exception):
    def __init__(self, code, message=None): self.code=code; super().__init__(message or code)

class ContactsService:
    EMAIL=re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    def __init__(self, repository): self.repository=repository
    def _text(self,v): return str(v or "").strip()
    def _validate(self,name,emails,phones):
        name=self._text(name); emails=tuple(self._text(x) for x in (emails or ()) if self._text(x)); phones=tuple(self._text(x) for x in (phones or ()) if self._text(x))
        if not name: raise ContactsError("INVALID_CONTACT")
        if any(not self.EMAIL.match(x) for x in emails): raise ContactsError("INVALID_EMAIL")
        if any(not re.search(r"\d",x) or re.search(r"[\r\n\t]",x) for x in phones): raise ContactsError("INVALID_PHONE")
        return name,emails,phones
    def list_contacts(self): return self.repository.list_contacts()
    def search_contacts(self,q): return self.repository.search_contacts(q)
    def get_contact(self,cid):
        c=self.repository.get_contact(cid)
        if not c: raise ContactsError("NOT_FOUND")
        return c
    def _duplicate(self,emails,exclude=None):
        wanted={x.casefold() for x in emails}
        return any(c.contact_id!=exclude and wanted.intersection(x.casefold() for x in c.emails) for c in self.repository.list_contacts())
    def create_contact(self,display_name,emails=(),phones=(),organization="",notes=""):
        name,emails,phones=self._validate(display_name,emails,phones)
        if self._duplicate(emails): raise ContactsError("POSSIBLE_DUPLICATE")
        return self.repository.create_contact(name,emails,phones,self._text(organization),self._text(notes))
    def update_contact(self,cid,display_name,emails=(),phones=(),organization="",notes="",expected_version=1):
        self.get_contact(cid); name,emails,phones=self._validate(display_name,emails,phones)
        if self._duplicate(emails,cid): raise ContactsError("POSSIBLE_DUPLICATE")
        c=self.repository.update_contact(cid,name,emails,phones,self._text(organization),self._text(notes),expected_version)
        if not c: raise ContactsError("EXTERNAL_CHANGE")
        return c
    def delete_contact(self,cid,confirmed=False):
        if not confirmed: raise ContactsError("CONFIRMATION_REQUIRED")
        if not self.repository.delete_contact(cid): raise ContactsError("NOT_FOUND")
        return True
