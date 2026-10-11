from __future__ import annotations
from uuid import uuid4
from aura_native.google.models import PreparedAction
from .service import ContactsError


class ContactsProductService:
    """PreparedAction boundary for local contacts mutations."""
    def __init__(self, service, repository):
        self.service, self.repository = service, repository

    def _resolve(self, target):
        value = str(target or '').strip()
        exact = self.service.repository.get_contact(value) if value else None
        if exact:
            return exact
        matches = [c for c in self.service.search_contacts(value)
                   if c.display_name.casefold() == value.casefold()]
        if not matches:
            raise ContactsError('NOT_FOUND')
        if len(matches) != 1:
            raise ContactsError('AMBIGUOUS')
        return matches[0]

    def _action(self, kind, payload, summary):
        action = PreparedAction(str(uuid4()), 'aura.contacts', kind, payload, summary)
        self.repository.create(action)
        return action

    def prepare_create(self, display_name, emails=(), phones=(), organization='', notes=''):
        name = str(display_name or '').strip()
        if not name:
            raise ContactsError('INVALID_CONTACT')
        # Validate without mutating; duplicate detection also stays in service.
        self.service._validate(name, emails, phones)
        if self.service._duplicate(tuple(str(x).strip() for x in emails if str(x).strip())):
            raise ContactsError('POSSIBLE_DUPLICATE')
        return self._action('contact.create', {'display_name': name, 'emails': list(emails),
            'phones': list(phones), 'organization': organization, 'notes': notes},
            f'Créer le contact « {name} »')

    def prepare_update(self, target, display_name=None, emails=(), phones=(), organization='', notes=''):
        current = self._resolve(target)
        name = current.display_name if display_name is None else str(display_name).strip()
        self.service._validate(name, emails, phones)
        return self._action('contact.update', {'contact_id': current.contact_id,
            'expected_version': current.version, 'display_name': name, 'emails': list(emails),
            'phones': list(phones), 'organization': organization, 'notes': notes},
            f'Modifier le contact « {current.display_name} »')

    def prepare_delete(self, target):
        current = self._resolve(target)
        return self._action('contact.delete', {'contact_id': current.contact_id,
            'expected_version': current.version, 'display_name': current.display_name},
            f'Supprimer le contact « {current.display_name} »')

    def execute_prepared_action(self, action_id):
        action = self.repository.get(action_id)
        if not action or action.state != 'confirmed':
            raise ContactsError('INVALID_STATE')
        p = action.payload
        if action.action_type == 'contact.create':
            self.service.create_contact(p['display_name'], p.get('emails', ()), p.get('phones', ()), p.get('organization', ''), p.get('notes', ''))
        elif action.action_type == 'contact.update':
            current = self.service.get_contact(p['contact_id'])
            if current.version != int(p['expected_version']): raise ContactsError('EXTERNAL_CHANGE')
            self.service.update_contact(p['contact_id'], p['display_name'], p.get('emails', ()), p.get('phones', ()), p.get('organization', ''), p.get('notes', ''), p['expected_version'])
        elif action.action_type == 'contact.delete':
            current = self.service.get_contact(p['contact_id'])
            if current.version != int(p['expected_version']): raise ContactsError('EXTERNAL_CHANGE')
            self.service.delete_contact(p['contact_id'], confirmed=True)
        else:
            raise ContactsError('UNSUPPORTED_ACTION')
        self.repository.mark_executed(action_id)
        return self.repository.get(action_id)
