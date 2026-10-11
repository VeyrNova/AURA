"""Native local memory contracts.

The service import is lazy so the repository can import ``memory.models``
without recursively importing the bus-facing service.
"""
from aura_native.memory.models import MemoryRecord

__all__ = ["MemoryRecord", "MemoryService"]

def __getattr__(name):
    if name == "MemoryService":
        from aura_native.memory.service import MemoryService
        return MemoryService
    raise AttributeError(name)
