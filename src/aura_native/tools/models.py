from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ToolResult:
 tool_name:str; success:bool; data:dict; error_code:str=""; requires_confirmation:bool=False; prepared_action_id:str|None=None

@dataclass(frozen=True)
class ToolRouteResult:
 matched:bool
 tool_name:str=""
 arguments:dict[str,Any]=None
 needs_clarification:bool=False
 clarification_reason:str=""
 confidence:float=1.0
 def __post_init__(self):
  object.__setattr__(self,"arguments",dict(self.arguments or {}))
 def __getitem__(self,key):
  if key=="name": return self.tool_name
  if key=="payload": return self.arguments
  return getattr(self,key)