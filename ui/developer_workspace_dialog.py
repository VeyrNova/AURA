
from __future__ import annotations
from pathlib import Path
import json, os
from runtime.aura_developer_live_bridge import workspace_snapshot
from runtime.aura_audit_ledger import AuditLedger

try:
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QTabWidget
    PYSIDE_AVAILABLE = True
except Exception:
    PYSIDE_AVAILABLE = False
    QDialog = object

ROOT = Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()

if PYSIDE_AVAILABLE:
    class DeveloperWorkspaceDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("AURA // DEVELOPER WORKSPACE")
            self.resize(980, 700)
            self.setMinimumSize(760, 520)
            self.setStyleSheet("""
                QDialog { background: #0D1018; color: #E8E9ED; }
                QLabel { color: #E8E9ED; }
                QPushButton { background: #171B25; color: #F3B257; border: 1px solid rgba(240,162,58,0.55); border-radius: 7px; padding: 7px 12px; }
                QPushButton:hover { background: #211B16; border-color: #F0A23A; }
                QTabWidget::pane { border: 1px solid rgba(240,162,58,0.28); border-radius: 8px; }
                QTabBar::tab { background: #151923; color: #AEB3BD; padding: 8px 14px; }
                QTabBar::tab:selected { color: #F3B257; border-bottom: 2px solid #F0A23A; }
                QPlainTextEdit { background: #090C12; color: #D7DBE2; border: none; font-family: Consolas; font-size: 12px; }
            """)
            root = QVBoxLayout(self)
            header = QHBoxLayout()
            self.mode_label = QLabel("Developer Mode")
            self.mode_label.setStyleSheet("font-size:18px;font-weight:800;color:#F3B257;letter-spacing:1px;")
            refresh = QPushButton("Actualiser")
            refresh.clicked.connect(self.refresh)
            verify = QPushButton("Vérifier audit")
            verify.clicked.connect(self.verify_audit)
            header.addWidget(self.mode_label); header.addStretch(1); header.addWidget(verify); header.addWidget(refresh)
            root.addLayout(header)
            self.tabs = QTabWidget()
            self.overview = QPlainTextEdit(); self.transactions = QPlainTextEdit(); self.audit = QPlainTextEdit()
            for edit in (self.overview, self.transactions, self.audit):
                edit.setReadOnly(True)
            self.tabs.addTab(self.overview, "État"); self.tabs.addTab(self.transactions, "Transactions"); self.tabs.addTab(self.audit, "Audit")
            root.addWidget(self.tabs)
            self.refresh()
        def refresh(self):
            data = workspace_snapshot(ROOT)
            enabled = bool(data.get("developer_mode", {}).get("enabled"))
            self.mode_label.setText("MODE DÉVELOPPEUR · " + ("ACTIF" if enabled else "INACTIF"))
            self.overview.setPlainText(json.dumps({"developer_mode":data.get("developer_mode"),"safety":data.get("safety")}, indent=2, ensure_ascii=False))
            self.transactions.setPlainText(json.dumps(data.get("recent_transactions") or [], indent=2, ensure_ascii=False))
            self.audit.setPlainText(json.dumps(data.get("audit_head"), indent=2, ensure_ascii=False))
        def verify_audit(self):
            try:
                state = AuditLedger(ROOT).verify()
            except Exception as exc:
                state = {"ok":False,"error":f"{type(exc).__name__}: {exc}"}
            self.audit.setPlainText(json.dumps(state, indent=2, ensure_ascii=False))
else:
    class DeveloperWorkspaceDialog:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("PySide6 is required for the native AURA Developer Workspace")

def capability_snapshot():
    return {
        "schema":"aura.native-developer-workspace-capabilities.v1",
        "pyside_available":PYSIDE_AVAILABLE,
        "native_qt_dialog":True,
        "read_only_operational_surface":True,
        "shows_developer_mode":True,
        "shows_transactions":True,
        "shows_audit":True,
        "can_verify_audit":True,
        "write_approvals_remain_outside_ui":True,
        "developer_visual_identity":"amber-electric",
    }
