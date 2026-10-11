"""Versioned, immutable contracts shared by the native runtime and UI."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Protocol
from uuid import uuid4

PayloadValue = str | int | float | bool | None | tuple["PayloadValue", ...] | Mapping[str, "PayloadValue"]

def freeze_payload(value: object) -> PayloadValue:
    if value is None or isinstance(value, (str, int, float, bool)): return value
    if isinstance(value, Mapping):
        frozen = {}
        for key, item in value.items():
            if not isinstance(key, str): raise TypeError("payload keys must be strings")
            frozen[key] = freeze_payload(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)): return tuple(freeze_payload(item) for item in value)
    raise TypeError("payload values must be JSON-shaped")

def _id(value: str | None) -> str: return value or str(uuid4())
def _utc(value: datetime | None) -> datetime:
    stamp = value or datetime.now(timezone.utc)
    if stamp.tzinfo is None: raise ValueError("timestamp_utc must be timezone-aware")
    return stamp.astimezone(timezone.utc)

class RuntimeState(str, Enum): CREATED="created"; RUNNING="running"; STOPPED="stopped"
class CapabilityState(str, Enum): AVAILABLE="available"; UNAVAILABLE="unavailable"; NOT_MIGRATED="not_migrated"

@dataclass(frozen=True)
class Capability: name: str; state: CapabilityState; reason: str

@dataclass(frozen=True)
class CommandError:
    code: str; message: str; retryable: bool=False; details: Mapping[str, PayloadValue]=field(default_factory=dict)
    def __post_init__(self): object.__setattr__(self,"details",freeze_payload(self.details))

@dataclass(frozen=True)
class Command:
    command_id: str=field(default_factory=lambda:str(uuid4())); name: str=""; payload: Mapping[str, PayloadValue]=field(default_factory=dict)
    correlation_id: str|None=None; session_id: str=field(default_factory=lambda:str(uuid4())); timestamp_utc: datetime=field(default_factory=lambda:datetime.now(timezone.utc)); source: str="ui"; contract_version:int=1
    def __post_init__(self):
        object.__setattr__(self,"command_id",_id(self.command_id)); object.__setattr__(self,"correlation_id",self.correlation_id or self.command_id); object.__setattr__(self,"session_id",_id(self.session_id)); object.__setattr__(self,"timestamp_utc",_utc(self.timestamp_utc)); object.__setattr__(self,"payload",freeze_payload(self.payload))
    @property
    def schema_version(self): return self.contract_version

@dataclass(frozen=True)
class CommandResult:
    command_id: str; ok: bool; status: str="ok"; payload: Mapping[str, PayloadValue]=field(default_factory=dict); error: CommandError|None=None
    correlation_id: str|None=None; session_id: str=""; timestamp_utc:datetime=field(default_factory=lambda:datetime.now(timezone.utc)); source:str="core"; contract_version:int=1
    def __post_init__(self):
        object.__setattr__(self,"correlation_id",self.correlation_id or self.command_id); object.__setattr__(self,"session_id",_id(self.session_id)); object.__setattr__(self,"timestamp_utc",_utc(self.timestamp_utc)); object.__setattr__(self,"payload",freeze_payload(self.payload))
    @property
    def error_code(self): return self.error.code if self.error else None
    @property
    def schema_version(self): return self.contract_version

@dataclass(frozen=True)
class Event:
    event_id: str=field(default_factory=lambda:str(uuid4())); name:str=""; payload:Mapping[str, PayloadValue]=field(default_factory=dict)
    correlation_id:str|None=None; session_id:str=field(default_factory=lambda:str(uuid4())); timestamp_utc:datetime=field(default_factory=lambda:datetime.now(timezone.utc)); source:str="core"; contract_version:int=1; sequence:int=0
    def __post_init__(self):
        object.__setattr__(self,"event_id",_id(self.event_id)); object.__setattr__(self,"session_id",_id(self.session_id)); object.__setattr__(self,"timestamp_utc",_utc(self.timestamp_utc)); object.__setattr__(self,"payload",freeze_payload(self.payload))
    @property
    def schema_version(self): return self.contract_version

class ServiceLifecycle(Protocol):
    def start(self)->None: ...
    def stop(self)->None: ...
