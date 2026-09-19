from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )

from action_receipts import (
    ActionReceiptService,
    ActionReceiptStore,
)
from core.version import AURA_VERSION
from integrations.files import (
    FILES_CAPABILITIES,
    FILES_PROVIDER_ID,
    FilesPathSecurityError,
    FilesProvider,
    SyntheticFilesBackend,
)
from integrations.registry import IntegrationRequest
from runtime.personal_integrations import (
    PersonalIntegrationDispatcher,
    build_synthetic_runtime_context,
)
from ui.personal_integration_modules import (
    FilesModuleController,
    PersonalIntegrationModules,
)

assert AURA_VERSION == '0.9.4', AURA_VERSION

assert FILES_PROVIDER_ID == "files.provider"

assert tuple(FILES_CAPABILITIES) == (
    "files.list",
    "files.search",
    "files.read",
    "files.create",
    "files.update",
    "files.move",
    "files.delete",
)

with tempfile.TemporaryDirectory(
    prefix="aura_files_v094_inv_"
) as td:
    sandbox_root = Path(td) / "sandbox"
    backend = SyntheticFilesBackend(
        root=sandbox_root,
    )
    provider = FilesProvider(
        backend=backend
    )

    assert provider.manifest.provider_id == FILES_PROVIDER_ID
    assert len(provider.manifest.capabilities) == 7

    cap_map = {
        capability.capability_id: capability
        for capability in provider.manifest.capabilities
    }

    for capability_id in FILES_CAPABILITIES:
        capability = cap_map[capability_id]
        assert capability.risk_tier is not None
        assert capability.side_effect_class is not None

    for capability_id in (
        "files.list",
        "files.search",
        "files.read",
    ):
        assert cap_map[capability_id].requires_confirmation is False

    for capability_id in (
        "files.create",
        "files.update",
        "files.move",
        "files.delete",
    ):
        assert cap_map[capability_id].requires_confirmation is True

    health = provider.health_snapshot()
    assert health["available"] is True
    assert health["external_connection"] is False
    assert health["allowed_roots_only"] is True
    assert health["network_side_effects"] is False

    listed = provider.execute(
        IntegrationRequest.create(
            provider_id=FILES_PROVIDER_ID,
            capability_id="files.list",
            params={"path": ""},
            origin="files-invariant",
        )
    )
    assert listed["items"]

    searched = provider.execute(
        IntegrationRequest.create(
            provider_id=FILES_PROVIDER_ID,
            capability_id="files.search",
            params={
                "query": {
                    "text": "welcome",
                    "limit": 20,
                }
            },
            origin="files-invariant",
        )
    )
    assert any(
        item["path"] == "documents/welcome.txt"
        for item in searched["items"]
    )

    content = provider.execute(
        IntegrationRequest.create(
            provider_id=FILES_PROVIDER_ID,
            capability_id="files.read",
            params={
                "path": "documents/welcome.txt"
            },
            origin="files-invariant",
        )
    )
    assert "AURA Files sandbox ready" in content["content"]["text"]

    for bad_path in (
        "../escape.txt",
        "..\\escape.txt",
        "/absolute.txt",
        "C:\\escape.txt",
        "~/escape.txt",
    ):
        try:
            provider.execute(
                IntegrationRequest.create(
                    provider_id=FILES_PROVIDER_ID,
                    capability_id="files.create",
                    params={
                        "path": bad_path,
                        "text": "DENIED",
                    },
                    origin="files-path-security",
                )
            )
        except FilesPathSecurityError:
            pass
        else:
            raise AssertionError(
                "unsafe path unexpectedly allowed: "
                + bad_path
            )

    # Prove symlink escape fail-closed when Windows allows symlink creation.
    outside = Path(td) / "outside"
    outside.mkdir(
        parents=True,
        exist_ok=True,
    )
    link = sandbox_root / "escape-link"
    symlink_tested = False

    try:
        link.symlink_to(
            outside,
            target_is_directory=True,
        )
        symlink_tested = True
    except (OSError, NotImplementedError):
        pass

    if symlink_tested:
        try:
            provider.execute(
                IntegrationRequest.create(
                    provider_id=FILES_PROVIDER_ID,
                    capability_id="files.create",
                    params={
                        "path": "escape-link/out.txt",
                        "text": "DENIED",
                    },
                    origin="files-symlink-security",
                )
            )
        except FilesPathSecurityError:
            pass
        else:
            raise AssertionError(
                "symlink escape unexpectedly allowed"
            )


class Security:
    def authorize(
        self,
        action,
        params,
        user_confirmed=False,
    ):
        writes = {
            "files.create",
            "files.update",
            "files.move",
            "files.delete",
        }

        if (
            action in writes
            and not user_confirmed
        ):
            return "REQUIRE_CONFIRMATION"

        return "ALLOW"


with tempfile.TemporaryDirectory(
    prefix="aura_files_v094_receipts_"
) as td:
    receipts = ActionReceiptService(
        store=ActionReceiptStore(
            Path(td) / "receipts.db"
        )
    )

    context = build_synthetic_runtime_context(
        security_engine=Security(),
        receipt_service=receipts,
    )

    dispatcher = PersonalIntegrationDispatcher(
        context=context
    )

    modules = PersonalIntegrationModules(
        dispatcher=dispatcher
    )

    catalog = modules.catalog()

    assert "mail" in catalog
    assert "calendar" in catalog
    assert "contacts" in catalog
    assert "documents" in catalog
    assert catalog["documents"]["capabilities"] == 7
    assert isinstance(
        modules.documents,
        FilesModuleController,
    )

    list_reply = modules.documents.list()
    assert list_reply.status == "succeeded"

    search_reply = modules.documents.search(
        "welcome"
    )
    assert search_reply.status == "succeeded"

    read_reply = modules.documents.read(
        "documents/welcome.txt"
    )
    assert read_reply.status == "succeeded"
    assert "AURA Files sandbox ready" in read_reply.text

    create_waiting = modules.documents.create(
        "work/test.txt",
        "alpha",
    )
    assert create_waiting.status == "waiting_confirmation"
    assert create_waiting.receipt_id

    create_done = modules.confirm()
    assert create_done.status == "succeeded"
    assert create_done.receipt_id == create_waiting.receipt_id

    update_waiting = modules.documents.update(
        "work/test.txt",
        "beta",
    )
    assert update_waiting.status == "waiting_confirmation"
    update_done = modules.confirm()
    assert update_done.status == "succeeded"
    assert update_done.receipt_id == update_waiting.receipt_id

    move_waiting = modules.documents.move(
        "work/test.txt",
        "archive/test.txt",
    )
    assert move_waiting.status == "waiting_confirmation"
    move_done = modules.confirm()
    assert move_done.status == "succeeded"
    assert move_done.receipt_id == move_waiting.receipt_id

    delete_waiting = modules.documents.delete(
        "archive/test.txt"
    )
    assert delete_waiting.status == "waiting_confirmation"
    delete_done = modules.confirm()
    assert delete_done.status == "succeeded"
    assert delete_done.receipt_id == delete_waiting.receipt_id

    text_list = dispatcher.handle_text(
        "liste mes fichiers"
    )
    assert text_list.status == "succeeded"

print("[PASS] AURA v0.9.4 FilesProvider")
print("[PASS] files.list/search/read are read-only")
print("[PASS] files.create/update/move/delete require confirmation")
print("[PASS] same ActionReceipt survives each confirmation")
print("[PASS] allowed-root containment + traversal denial")
print("[PASS] symlink escape denied when symlink creation is available")
print("[PASS] FilesModuleController reuses DOCUMENTS identity")
print("[PASS] conversation Files intents")
print("[PASS] synthetic/local sandbox; no cloud/OAuth/network side effect")
raise SystemExit(0)
