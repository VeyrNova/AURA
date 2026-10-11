from dataclasses import dataclass

@dataclass(frozen=True)
class Conversation:
    conversation_id: str
    session_id: str
    title: str
    created_at: str
    updated_at: str
    status: str
    def as_payload(self): return self.__dict__.copy()

@dataclass(frozen=True)
class ConversationMessage:
    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at: str
    sequence: int
    status: str
    source: str
    def as_payload(self): return self.__dict__.copy()
