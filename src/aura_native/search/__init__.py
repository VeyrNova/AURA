"""Native Web search contracts and service."""

from .models import SearchResult
from .service import SearchError, SearchService

__all__ = ["SearchError", "SearchResult", "SearchService"]
