"""Safe native Documents module."""

from .filesystem import FileSystemRepository
from .service import DocumentsError, DocumentsService

__all__ = ["DocumentsError", "DocumentsService", "FileSystemRepository"]
