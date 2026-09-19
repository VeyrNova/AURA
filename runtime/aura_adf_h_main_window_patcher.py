
from __future__ import annotations
from pathlib import Path
import ast
import re

IMPORT_BLOCK = (
    "from runtime.aura_developer_live_bridge import "
    "handle_live_developer_input, dequeue_spoken_summary\n"
    "from ui.developer_workspace_dialog import DeveloperWorkspaceDialog\n"
    "from ui.developer_mode_visuals import apply_developer_mode_visuals, sync_developer_mode_visuals\n"
)

LIVE_METHOD = """
    def _handle_developer_mode_command_live(self, text: str) -> bool:
        channel = str(getattr(self, "_aura_developer_input_channel", "text") or "text")
        self._aura_developer_input_channel = "text"
        try:
            result = handle_live_developer_input(text, channel=channel)
        except Exception:
            logger.exception("Developer Mode live command bridge failed")
            return False
        if not result.get("recognized"):
            return False

        try:
            apply_developer_mode_visuals(self, bool(result.get("enabled")))
        except Exception:
            logger.debug("Developer Mode visual identity update failed", exc_info=True)

        self.chat_panel.add_user_message(text)
        if result.get("open_workspace"):
            try:
                dialog = getattr(self, "_aura_developer_workspace_dialog", None)
                if dialog is None:
                    dialog = DeveloperWorkspaceDialog(self)
                    self._aura_developer_workspace_dialog = dialog
                dialog.show()
                dialog.raise_()
                dialog.activateWindow()
            except Exception:
                logger.exception("AURA Developer Workspace open failed")

        spoken = str(result.get("speak") or "").strip()
        if spoken:
            self.chat_panel.add_aura_message(spoken)
            self._speak_text(spoken, strict_test=False)
        return True

"""

QUEUE_BLOCK = """        try:
            sync_developer_mode_visuals(self)
        except Exception:
            logger.debug("Developer Mode visual identity sync unavailable", exc_info=True)
        try:
            _aura_dev_summary = dequeue_spoken_summary()
            if _aura_dev_summary:
                self.chat_panel.add_aura_message(_aura_dev_summary)
                self._speak_text(_aura_dev_summary, strict_test=False)
        except Exception:
            logger.debug("Developer Mode spoken-summary queue unavailable", exc_info=True)
"""

def _parse(source: str, path: Path):
    return ast.parse(source, filename=str(path))

def _class_method(tree: ast.AST, class_name: str, method_name: str):
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name), None)
    if cls is None:
        raise RuntimeError(f"class {class_name} not found")
    fn = next(
        (
            n for n in cls.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == method_name
        ),
        None,
    )
    if fn is None:
        raise RuntimeError(f"{class_name}.{method_name} not found")
    return cls, fn

def _calls_self_method(fn, method_name: str) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
                and node.func.attr == method_name
            ):
                return True
    return False

def _method_span(source: str, method_name: str) -> tuple[int, int, str]:
    # MainWindow methods are class-indented by exactly four spaces.
    pattern = re.compile(
        rf"(?m)^    def {re.escape(method_name)}\([^\n]*\)(?:[ \t]*->[ \t]*[^:\n]+)?:[ \t]*\n"
    )
    match = pattern.search(source)
    if not match:
        raise RuntimeError(f"method span not found: {method_name}")
    start = match.start()
    next_member = re.search(r"(?m)^    (?:def |async def |@)", source[match.end():])
    end = match.end() + next_member.start() if next_member else len(source)
    return start, end, source[start:end]

def _replace_method(source: str, method_name: str, new_method: str) -> str:
    start, end, _ = _method_span(source, method_name)
    return source[:start] + new_method.rstrip("\n") + "\n\n" + source[end:].lstrip("\n")

def _insert_top_level_imports(source: str, path: Path) -> str:
    missing = []
    if "from runtime.aura_developer_live_bridge import " not in source:
        missing.append(
            "from runtime.aura_developer_live_bridge import "
            "handle_live_developer_input, dequeue_spoken_summary\n"
        )
    if "from ui.developer_workspace_dialog import DeveloperWorkspaceDialog" not in source:
        missing.append("from ui.developer_workspace_dialog import DeveloperWorkspaceDialog\n")
    if "from ui.developer_mode_visuals import " not in source:
        missing.append(
            "from ui.developer_mode_visuals import "
            "apply_developer_mode_visuals, sync_developer_mode_visuals\n"
        )
    if not missing:
        return source
    tree = _parse(source, path)
    imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    if not imports:
        raise RuntimeError("no top-level import anchor")
    last = max(imports, key=lambda n: getattr(n, "end_lineno", n.lineno))
    lines = source.splitlines(keepends=True)
    insert_index = getattr(last, "end_lineno", last.lineno)
    lines[insert_index:insert_index] = ["\n", "".join(missing), "\n"]
    return "".join(lines)

def patch_main_window(path: Path) -> dict:
    source = path.read_text(encoding="utf-8-sig", errors="strict")
    original = source

    # Preflight against the actual AURA route contract.
    tree = _parse(source, path)
    _, user_fn = _class_method(tree, "MainWindow", "_on_user_message")
    _, stt_fn = _class_method(tree, "MainWindow", "_on_stt_finished")
    _class_method(tree, "MainWindow", "_refresh_resource_status")
    _class_method(tree, "MainWindow", "_speak_text")
    if not _calls_self_method(stt_fn, "_on_user_message"):
        raise RuntimeError("STT path no longer converges into _on_user_message")
    user_segment = ast.get_source_segment(source, user_fn) or ""
    if "try_handle_intent" not in user_segment:
        raise RuntimeError("_on_user_message no longer matches supported AURA route shape")

    source = _insert_top_level_imports(source, path)

    # Add the live handler immediately before the common user-message route.
    if "def _handle_developer_mode_command_live(self, text: str)" not in source:
        start, _, _ = _method_span(source, "_on_user_message")
        source = source[:start] + LIVE_METHOD.lstrip("\n") + source[start:]

    # Upgrade a pre-existing ADF-H v1 handler with immediate visual switching.
    _, _, live_method = _method_span(source, "_handle_developer_mode_command_live")
    if "apply_developer_mode_visuals(self" not in live_method:
        live_anchor = "        self.chat_panel.add_user_message(text)"
        if live_anchor not in live_method:
            raise RuntimeError("existing Developer Mode handler shape is unsupported")
        visual_block = (
            "        try:\n"
            "            apply_developer_mode_visuals(self, bool(result.get(\"enabled\")))\n"
            "        except Exception:\n"
            "            logger.debug(\"Developer Mode visual identity update failed\", exc_info=True)\n\n"
        )
        live_method = live_method.replace(live_anchor, visual_block + live_anchor, 1)
        source = _replace_method(source, "_handle_developer_mode_command_live", live_method)

    # Intercept developer commands immediately after the existing empty-text gate.
    if "if self._handle_developer_mode_command_live(text):" not in source:
        _, _, method = _method_span(source, "_on_user_message")
        anchor = '        if not text:\n            return\n'
        if anchor not in method:
            raise RuntimeError("_on_user_message empty-text gate anchor not found")
        updated = method.replace(
            anchor,
            anchor + '        if self._handle_developer_mode_command_live(text):\n            return\n',
            1,
        )
        source = _replace_method(source, "_on_user_message", updated)

    # The STT route tags only the next common-route call as voice.
    if 'self._aura_developer_input_channel = "voice"' not in source:
        _, _, method = _method_span(source, "_on_stt_finished")
        anchor = "        self._on_user_message(text)"
        if anchor not in method:
            raise RuntimeError("_on_stt_finished common-route anchor not found")
        updated = method.replace(
            anchor,
            '        self._aura_developer_input_channel = "voice"\n' + anchor,
            1,
        )
        source = _replace_method(source, "_on_stt_finished", updated)

    # Reuse the existing resource timer. Upgrade ADF-H v1 independently: its
    # spoken-summary pump may already exist even when visual sync does not.
    _, _, refresh_method = _method_span(source, "_refresh_resource_status")
    if "Developer Mode spoken-summary queue unavailable" not in refresh_method:
        lines = refresh_method.splitlines(keepends=True)
        if not lines or not lines[0].lstrip().startswith("def _refresh_resource_status"):
            raise RuntimeError("_refresh_resource_status header anchor not found")
        refresh_method = lines[0] + QUEUE_BLOCK + "".join(lines[1:])
        source = _replace_method(source, "_refresh_resource_status", refresh_method)
    else:
        _, _, refresh_method = _method_span(source, "_refresh_resource_status")
        if "sync_developer_mode_visuals(self)" not in refresh_method:
            lines = refresh_method.splitlines(keepends=True)
            visual_sync = (
                "        try:\n"
                "            sync_developer_mode_visuals(self)\n"
                "        except Exception:\n"
                "            logger.debug(\"Developer Mode visual identity sync unavailable\", exc_info=True)\n"
            )
            refresh_method = lines[0] + visual_sync + "".join(lines[1:])
            source = _replace_method(source, "_refresh_resource_status", refresh_method)

    # Final structural verification.
    final = _parse(source, path)
    _class_method(final, "MainWindow", "_handle_developer_mode_command_live")
    _, user_fn = _class_method(final, "MainWindow", "_on_user_message")
    _, stt_fn = _class_method(final, "MainWindow", "_on_stt_finished")
    _, refresh_fn = _class_method(final, "MainWindow", "_refresh_resource_status")
    _class_method(final, "MainWindow", "_speak_text")

    user_segment = ast.get_source_segment(source, user_fn) or ""
    live_pos = user_segment.find("_handle_developer_mode_command_live")
    intent_pos = user_segment.find("try_handle_intent")
    if live_pos < 0 or (intent_pos >= 0 and live_pos > intent_pos):
        raise RuntimeError("developer mode interception is not before intent routing")
    if not _calls_self_method(stt_fn, "_on_user_message"):
        raise RuntimeError("STT common-route invariant lost after patch")
    if 'self._aura_developer_input_channel = "voice"' not in (ast.get_source_segment(source, stt_fn) or ""):
        raise RuntimeError("voice channel tag missing after patch")
    refresh_segment = ast.get_source_segment(source, refresh_fn) or ""
    if "dequeue_spoken_summary" not in refresh_segment:
        raise RuntimeError("spoken summary delivery pump missing")
    if "sync_developer_mode_visuals" not in refresh_segment:
        raise RuntimeError("developer visual identity sync missing")
    if "from ui.developer_mode_visuals import " not in source:
        raise RuntimeError("developer visual identity import missing")
    if "DeveloperWorkspaceDialog" not in source:
        raise RuntimeError("native Developer Workspace binding missing")

    if source != original:
        path.write_text(source, encoding="utf-8", newline="\n")

    return {
        "changed": source != original,
        "has_live_method": True,
        "voice_to_common_route": True,
        "intercept_before_intent": True,
        "spoken_summary_pump": True,
        "native_workspace_import": True,
        "developer_visual_identity": True,
    }
