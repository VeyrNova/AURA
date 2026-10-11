from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
def now(): return datetime.now(timezone.utc).isoformat()
@dataclass(frozen=True)
class CalendarEvent: event_id:str; title:str; start:str; end:str; timezone:str; location:str=""; description:str=""; attendees:tuple[str,...]=(); status:str="confirmed"
@dataclass(frozen=True)
class CalendarBusyInterval: start:str; end:str; timezone:str
@dataclass(frozen=True)
class TaskItem: task_id:str; title:str; due:str|None; status:str="needsAction"; notes:str=""; completed_at:str|None=None
@dataclass(frozen=True)
class PreparedAction:
    action_id:str; tool_name:str; action_type:str; payload:dict; summary:str; requires_confirmation:bool=True; state:str="prepared"; created_at:str=field(default_factory=now); expires_at:str|None=None; confirmed_at:str|None=None; executed_at:str|None=None; error_code:str=""
@dataclass(frozen=True)
class GoogleAuthState: configured:bool=False; authenticated:bool=False; account_email:str|None=None; scopes:tuple[str,...]=(); error_code:str="google_not_configured"
