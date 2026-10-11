"""Native local Contacts module."""
from .models import Contact
from .repository import ContactsRepository
from .service import ContactsService, ContactsError

__all__ = ["Contact", "ContactsRepository", "ContactsService", "ContactsError"]
