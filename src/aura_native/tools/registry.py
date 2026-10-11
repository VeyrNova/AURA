from dataclasses import dataclass

@dataclass(frozen=True)
class ToolDefinition:
    name: str; description: str; input_schema: dict; capability: str; handler: object

class ToolRegistry:
    def __init__(self): self._tools={}
    def register(self, definition):
        if definition.name in self._tools: raise ValueError("tool already registered")
        self._tools[definition.name]=definition
    def get(self, name): return self._tools.get(name)
    def execute(self, name, payload):
        definition=self.get(name)
        if definition is None: raise ValueError("unknown tool")
        return definition.handler.execute(payload)
    @property
    def definitions(self): return tuple(self._tools.values())

def register_google_offline_tools(registry, calendar_service, tasks_service):
    """Register offline Google-domain contracts; this does not configure Google."""
    from aura_native.tools.calendar_tool import CalendarTool
    from aura_native.tools.tasks_tool import TasksTool
    definitions=(
     ('calendar.list_events','List upcoming calendar events',{},'google.calendar'),('calendar.get_day','List calendar events for an ISO date',{'date':'string'},'google.calendar'),('calendar.find_free_time','List busy intervals in a range',{'start':'string','end':'string'},'google.calendar'),
     ('calendar.create','Prepare calendar event creation',{'title':'string','start':'string','end':'string','timezone':'string'},'google.calendar'),('calendar.update','Prepare calendar event update',{'event_id':'string'},'google.calendar'),('calendar.delete','Prepare calendar event deletion',{'event_id':'string'},'google.calendar'),
     ('tasks.list','List tasks',{},'google.tasks'),('tasks.create','Prepare task creation',{'title':'string'},'google.tasks'),('tasks.complete','Prepare task completion',{'task_id':'string'},'google.tasks'),('tasks.delete','Prepare task deletion',{'task_id':'string'},'google.tasks'))
    for name,description,properties,capability in definitions:
     service=calendar_service if name.startswith('calendar.') else tasks_service
     handler=CalendarTool(service,name) if name.startswith('calendar.') else TasksTool(service,name)
     registry.register(ToolDefinition(name,description,{'type':'object','properties':properties},capability,handler))
