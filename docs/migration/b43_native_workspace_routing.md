# B4.3 — native Agenda and Tasks routing

Audit found the shared cause: the native path loaded `NativeWorkspaceView`, which only declared Settings, Memory and Conversation. `agenda` and `tasks` therefore fell through to its Foundation/Memory-style fallback, despite real views already existing at `app/qml/views/AgendaView.qml` and `app/qml/views/TasksView.qml`. The dock IDs were already distinct (`agenda` and `tasks`).

The native workspace now mounts those existing views directly and excludes both routes from Foundation. Memory remains `MemoryView`; Conversation remains `NativeConversationView`; Settings remains `SettingsView`. Memory refresh on component completion is restricted to memory routes, so Agenda/Tasks do not trigger memory work.

Offline routing tests: 4/4; full tests/native: 312/312; QML self-check: OK. No Google write, network, OAuth or credential was used.

B4.3 remains **PASS TECHNIQUE / REAL UI VALIDATION REQUIRED**.
