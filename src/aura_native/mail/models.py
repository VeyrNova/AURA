from dataclasses import dataclass, field

@dataclass(frozen=True)
class MailMessage:
    message_id: str; thread_id: str; sender: str; recipients: tuple[str,...]; subject: str; snippet: str; body: str; date: str; unread: bool=False; attachments: tuple[dict,...]=()

@dataclass(frozen=True)
class MailThread:
    thread_id: str; messages: tuple[MailMessage,...]

@dataclass
class MailMessagesModel:
    items: list[MailMessage] = field(default_factory=list)
    @property
    def count(self): return len(self.items)
