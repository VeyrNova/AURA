"""Local memory control center for AURA v0.6."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class MemoryDialog(QDialog):
    """Inspect and delete persistent memories without bypassing the router."""

    def __init__(self, aura_core, parent=None):
        super().__init__(parent)
        self.aura_core = aura_core
        self.memory = aura_core.memory_manager
        self.router = aura_core.action_router
        self.setWindowTitle("AURA — Mémoire & continuité")
        self.resize(760, 520)

        root = QVBoxLayout(self)

        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher dans la mémoire locale…")
        self.search.returnPressed.connect(self.refresh)
        search_row.addWidget(self.search)
        search_btn = QPushButton("Rechercher")
        search_btn.clicked.connect(self.refresh)
        search_row.addWidget(search_btn)
        clear_btn = QPushButton("Tout afficher")
        clear_btn.clicked.connect(self._clear_search)
        search_row.addWidget(clear_btn)
        root.addLayout(search_row)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        root.addWidget(self.list_widget, stretch=1)

        controls = QHBoxLayout()
        self.private_checkbox = QCheckBox("Mode privé pour cette session")
        self.private_checkbox.toggled.connect(self._toggle_private)
        controls.addWidget(self.private_checkbox)
        controls.addStretch()

        delete_btn = QPushButton("Supprimer le souvenir")
        delete_btn.clicked.connect(self._delete_selected)
        controls.addWidget(delete_btn)

        purge_btn = QPushButton("Tout oublier…")
        purge_btn.clicked.connect(self._purge_all)
        controls.addWidget(purge_btn)
        root.addLayout(controls)

        hint = QLabel(
            "Les souvenirs marqués 🔒 sont sensibles. Ils peuvent être conservés sur demande explicite, "
            "mais ne sont pas injectés automatiquement dans le LLM par défaut."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8fa6b8;")
        root.addWidget(hint)

        self.refresh()

    def _clear_search(self):
        self.search.clear()
        self.refresh()

    def refresh(self):
        query = self.search.text().strip()
        if query:
            records = self.memory.search(query, limit=100, include_sensitive=True)
        else:
            records = self.memory.list_memories(limit=200, include_sensitive=True)

        self.list_widget.clear()
        for rec in records:
            lock = " 🔒" if rec.is_sensitive else ""
            item = QListWidgetItem(
                f"#{rec.id} · {rec.type}{lock} · importance {rec.importance}/5\n{rec.content}"
            )
            item.setData(Qt.UserRole, rec.id)
            item.setToolTip(
                f"Source: {rec.source}\nConfiance: {rec.confidence:.2f}\nCréé: {rec.created_at}"
            )
            self.list_widget.addItem(item)

        self.private_checkbox.blockSignals(True)
        self.private_checkbox.setChecked(self.memory.private_mode)
        self.private_checkbox.blockSignals(False)
        mode = "PRIVÉ" if self.memory.private_mode else "NORMAL"
        self.status.setText(
            f"Mémoire persistante : {len(records)} élément(s) affiché(s) · mode {mode}. "
            "Les notes, tâches et rappels sont stockés séparément."
        )

    def _toggle_private(self, enabled: bool):
        intent = "SET_MEMORY_PRIVATE_MODE" if enabled else "SET_MEMORY_NORMAL_MODE"
        response = self.router.route(intent, {})
        self.aura_core._sync_private_mode()
        self.status.setText(response)

    def _delete_selected(self):
        item = self.list_widget.currentItem()
        if item is None:
            self.status.setText("Sélectionne d'abord un souvenir à supprimer.")
            return
        memory_id = int(item.data(Qt.UserRole))
        response = self.router.route("FORGET_MEMORY", {"raw": str(memory_id)})
        self.status.setText(response)
        self.refresh()

    def _purge_all(self):
        answer = QMessageBox.question(
            self,
            "Tout oublier",
            "Effacer tous les souvenirs personnels ainsi que la continuité/familiarité locale ?\n\n"
            "Les notes, tâches et rappels ne seront pas supprimés.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        response = self.aura_core.forget_all_personal_memory()
        self.status.setText(response)
        self.refresh()
