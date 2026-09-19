from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from runtime.workspace_runtime_binding_v130 import (
    RUNTIME_CONTEXT_SCHEMA,
    WorkspaceRuntimeBindingV130,
    get_workspace_runtime_binding_v130,
)

PROJECT_CONTEXT_MARKER = "AURA_ACTIVE_PROJECT"
PROJECT_CONTEXT_BEGIN = f"[{PROJECT_CONTEXT_MARKER}]"
PROJECT_CONTEXT_END = f"[/{PROJECT_CONTEXT_MARKER}]"
CONVERSATION_CONTEXT_SCHEMA = "aura.workspace.conversation-context.v1"


@dataclass(frozen=True)
class ConversationContextEnvelope:
    schema: str
    active: bool
    workspace_id: str
    context_block: str
    system_message: dict[str, str] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "active": self.active,
            "workspace_id": self.workspace_id,
            "context_block": self.context_block,
            "system_message": None if self.system_message is None else dict(self.system_message),
        }


def _strip_project_block(text: str) -> str:
    raw = str(text or "")
    while True:
        start = raw.find(PROJECT_CONTEXT_BEGIN)
        if start < 0:
            break
        end = raw.find(PROJECT_CONTEXT_END, start + len(PROJECT_CONTEXT_BEGIN))
        if end < 0:
            # Fail-safe: remove only from marker to end if a malformed old block exists.
            raw = raw[:start].rstrip()
            break
        end += len(PROJECT_CONTEXT_END)
        raw = (raw[:start] + raw[end:]).strip()
    return raw


def _message_role(message: Any) -> str:
    if isinstance(message, Mapping):
        return str(message.get("role") or "")
    return str(getattr(message, "role", "") or "")


def _message_content(message: Any) -> str:
    if isinstance(message, Mapping):
        return str(message.get("content") or "")
    return str(getattr(message, "content", "") or "")


class WorkspaceConversationContextInjectorV130:
    """Deterministic active-project context injection for Conversation/AuraCore.

    W130-C does not yet alter an existing core source file. It establishes the exact,
    tested injection contract that the live Conversation bridge will consume in W130-D.
    """

    def __init__(self, binding: WorkspaceRuntimeBindingV130 | None = None) -> None:
        self.binding = binding or get_workspace_runtime_binding_v130()

    def envelope(self) -> ConversationContextEnvelope:
        context = self.binding.active_context()
        if context is None:
            return ConversationContextEnvelope(
                schema=CONVERSATION_CONTEXT_SCHEMA,
                active=False,
                workspace_id="",
                context_block="",
                system_message=None,
            )
        block = self.binding.prompt_context_block()
        return ConversationContextEnvelope(
            schema=CONVERSATION_CONTEXT_SCHEMA,
            active=True,
            workspace_id=context.workspace_id,
            context_block=block,
            system_message={
                "role": "system",
                "content": (
                    "Contexte de projet actif AURA. Utilise-le uniquement comme contexte "
                    "de continuité du projet; ne prétends pas qu'une action a été exécutée "
                    "si aucun outil/receipt ne le prouve.\n" + block
                ),
            },
        )

    def sanitize_messages(
        self,
        messages: Sequence[Mapping[str, Any] | Any],
    ) -> list[dict[str, Any]]:
        """Return plain message dictionaries with any previous project block removed."""
        out: list[dict[str, Any]] = []
        for message in messages:
            role = _message_role(message)
            content = _message_content(message)
            if role == "system" and PROJECT_CONTEXT_BEGIN in content:
                cleaned = _strip_project_block(content)
                # If this was only the old workspace system message, drop it.
                if not cleaned or cleaned.startswith(
                    "Contexte de projet actif AURA. Utilise-le uniquement comme contexte"
                ):
                    continue
                out.append({"role": role, "content": cleaned})
                continue
            if isinstance(message, Mapping):
                row = dict(message)
                row["role"] = role
                row["content"] = content
                out.append(row)
            else:
                out.append({"role": role, "content": content})
        return out

    def inject_messages(
        self,
        messages: Sequence[Mapping[str, Any] | Any],
        *,
        position: str = "before_user",
    ) -> list[dict[str, Any]]:
        """Inject exactly one current active-project system message.

        `before_user` places it immediately before the first user message; otherwise
        it is inserted at the start. Repeated calls are idempotent.
        """
        clean = self.sanitize_messages(messages)
        env = self.envelope()
        if not env.active or env.system_message is None:
            return clean

        system_message = dict(env.system_message)
        if position == "before_user":
            index = next(
                (i for i, m in enumerate(clean) if str(m.get("role") or "") == "user"),
                len(clean),
            )
        else:
            index = 0
        return [*clean[:index], system_message, *clean[index:]]

    def inject_prompt(self, prompt: str) -> str:
        """Inject active-project context into a plain prompt, idempotently."""
        clean = _strip_project_block(str(prompt or ""))
        env = self.envelope()
        if not env.active:
            return clean
        if clean:
            return f"{env.context_block}\n\n{clean}"
        return env.context_block

    def conversation_metadata(self) -> dict[str, Any]:
        env = self.envelope()
        return {
            "schema": CONVERSATION_CONTEXT_SCHEMA,
            "active_project": env.active,
            "workspace_id": env.workspace_id,
            "runtime_context_schema": RUNTIME_CONTEXT_SCHEMA,
            "marker": PROJECT_CONTEXT_MARKER,
        }

    def explain_active_project(self) -> dict[str, Any]:
        """Structured payload suitable for a future 'quel projet est actif ?' intent."""
        context = self.binding.active_context()
        if context is None:
            return {
                "schema": CONVERSATION_CONTEXT_SCHEMA,
                "active": False,
                "workspace": None,
            }
        return {
            "schema": CONVERSATION_CONTEXT_SCHEMA,
            "active": True,
            "workspace": {
                "workspace_id": context.workspace_id,
                "name": context.name,
                "status": context.status,
                "root_path": context.root_path,
                "last_action": context.last_action,
                "next_action": context.next_action,
                "artifact_count": context.artifact_count,
                "updated_at": context.updated_at,
            },
        }


def get_workspace_conversation_context_injector_v130(
    binding: WorkspaceRuntimeBindingV130 | None = None,
) -> WorkspaceConversationContextInjectorV130:
    return WorkspaceConversationContextInjectorV130(binding=binding)
