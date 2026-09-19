"""Interactive XTTS speaker audition lab for AURA v0.5.3."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from voice.errors import VoiceError
from voice.voice_audition import VoiceAuditionStore, VoiceRating
from voice.voice_engine import VoiceEngine
from voice.voice_profile import VoiceProfileStore, XTTS_FEMALE_PRESETS


DEFAULT_AUDITION_TEXT = (
    "Bonsoir. Je suis AURA. Dis-moi ce que tu veux faire. Je m'occupe du reste."
)


class VoicePreviewWorker(QObject):
    finished = Signal(str, object)
    failed = Signal(str)

    def __init__(self, engine: VoiceEngine, speaker: str, text: str, fast: bool):
        super().__init__()
        self.engine = engine
        self.speaker = speaker
        self.text = text
        self.fast = fast

    def run(self):
        try:
            metrics = self.engine.preview_xtts_speaker(self.speaker, self.text, fast=self.fast)
            self.finished.emit(self.speaker, metrics)
        except VoiceError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit("Le test XTTS a échoué. Consulte les logs pour le détail.")


class VoiceLabDialog(QDialog):
    profile_selected = Signal(object)

    def __init__(
        self,
        engine: VoiceEngine,
        profile_store: VoiceProfileStore,
        speakers: tuple[str, ...],
        parent=None,
    ):
        super().__init__(parent)
        self.engine = engine
        self.profile_store = profile_store
        self.speakers = tuple(speakers)
        self.rating_store = VoiceAuditionStore()
        self.ratings = self.rating_store.load()
        self._preview_thread: QThread | None = None
        self._preview_worker: VoicePreviewWorker | None = None
        self._loading_rating = False

        self.setWindowTitle("AURA — XTTS Voice Lab")
        self.resize(980, 690)
        self.setMinimumSize(820, 600)
        self._build_ui()
        self._populate_speakers()
        if self.speaker_list.count():
            self.speaker_list.setCurrentRow(0)

    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("XTTS Voice Lab — comparer les voix d'AURA")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #8fe8ff;")
        root.addWidget(title)

        subtitle = QLabel(
            f"{len(self.speakers)} speakers détectés. Le modèle XTTS reste chargé entre les essais. "
            "Note chaque voix puis exporte le classement."
        )
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # Left: speaker browser
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher une voix…")
        self.search.textChanged.connect(self._populate_speakers)
        left_layout.addWidget(self.search)

        self.female_only = QCheckBox("Présélection féminine uniquement")
        self.female_only.stateChanged.connect(self._populate_speakers)
        left_layout.addWidget(self.female_only)

        self.favorites_only = QCheckBox("Favoris uniquement")
        self.favorites_only.stateChanged.connect(self._populate_speakers)
        left_layout.addWidget(self.favorites_only)

        self.speaker_list = QListWidget()
        self.speaker_list.currentItemChanged.connect(self._on_speaker_changed)
        left_layout.addWidget(self.speaker_list, 1)

        self.counter = QLabel()
        left_layout.addWidget(self.counter)
        splitter.addWidget(left)

        # Right: audition and scoring
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.current_name = QLabel("—")
        self.current_name.setStyleSheet("font-size: 22px; font-weight: 700; color: #d9b4ff;")
        right_layout.addWidget(self.current_name)

        self.current_meta = QLabel()
        right_layout.addWidget(self.current_meta)

        try:
            info = self.engine.xtts_runtime_info()
            if info.device == "cuda":
                runtime_text = f"⚡ CUDA · {info.gpu_name} · VRAM {info.allocated_mb:.0f}/{info.total_mb:.0f} Mo alloués"
            else:
                runtime_text = "⚠ XTTS fonctionne actuellement sur CPU"
        except Exception:
            runtime_text = "Runtime XTTS : état indisponible"
        self.runtime_label = QLabel(runtime_text)
        self.runtime_label.setWordWrap(True)
        right_layout.addWidget(self.runtime_label)

        self.fast_preview = QCheckBox("⚡ Audition rapide (recommandé pour les 58 voix)")
        self.fast_preview.setChecked(True)
        right_layout.addWidget(self.fast_preview)

        right_layout.addWidget(QLabel("Phrase de test"))
        self.preview_text = QPlainTextEdit(DEFAULT_AUDITION_TEXT)
        self.preview_text.setMaximumHeight(105)
        right_layout.addWidget(self.preview_text)

        nav = QHBoxLayout()
        self.prev_button = QPushButton("◀ Précédente")
        self.prev_button.clicked.connect(lambda: self._move_selection(-1))
        self.play_button = QPushButton("▶ Tester cette voix")
        self.play_button.clicked.connect(self._play_current)
        self.stop_button = QPushButton("■ Stop")
        self.stop_button.clicked.connect(self.engine.stop_speaking)
        self.next_button = QPushButton("Suivante ▶")
        self.next_button.clicked.connect(lambda: self._move_selection(1))
        nav.addWidget(self.prev_button)
        nav.addWidget(self.play_button, 1)
        nav.addWidget(self.stop_button)
        nav.addWidget(self.next_button)
        right_layout.addLayout(nav)

        self.status = QLabel("Prêt.")
        self.status.setWordWrap(True)
        right_layout.addWidget(self.status)

        rating_form = QFormLayout()
        self.naturality = self._rating_spin()
        self.warmth = self._rating_spin()
        self.sensuality = self._rating_spin()
        self.preference = self._rating_spin()
        for spin in (self.naturality, self.warmth, self.sensuality, self.preference):
            spin.valueChanged.connect(self._autosave_rating)
        rating_form.addRow("Naturalité (0–5)", self.naturality)
        rating_form.addRow("Chaleur (0–5)", self.warmth)
        rating_form.addRow("Sensualité (0–5)", self.sensuality)
        rating_form.addRow("Préférence globale (0–5)", self.preference)
        right_layout.addLayout(rating_form)

        self.favorite = QCheckBox("★ Ajouter aux favoris")
        self.favorite.stateChanged.connect(self._autosave_rating)
        right_layout.addWidget(self.favorite)

        right_layout.addWidget(QLabel("Notes"))
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Ex. très naturelle, trop aiguë, bonne chaleur, consonnes trop sèches…")
        self.notes.setMaximumHeight(90)
        self.notes.textChanged.connect(self._autosave_rating)
        right_layout.addWidget(self.notes)

        self.score_label = QLabel("Score : —")
        right_layout.addWidget(self.score_label)

        actions = QHBoxLayout()
        self.apply_button = QPushButton("✓ Utiliser cette voix pour AURA")
        self.apply_button.clicked.connect(self._apply_current_voice)
        self.export_button = QPushButton("Exporter le classement")
        self.export_button.clicked.connect(self._export_ranking)
        actions.addWidget(self.apply_button)
        actions.addWidget(self.export_button)
        right_layout.addLayout(actions)

        right_layout.addStretch()
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        close_row.addWidget(close)
        root.addLayout(close_row)

    @staticmethod
    def _rating_spin() -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 5)
        spin.setSpecialValueText("Non notée")
        return spin

    # ------------------------------------------------------------------
    def _filtered_speakers(self) -> list[str]:
        query = self.search.text().strip().casefold() if hasattr(self, "search") else ""
        speakers = list(self.speakers)
        if hasattr(self, "female_only") and self.female_only.isChecked():
            female = set(XTTS_FEMALE_PRESETS)
            speakers = [s for s in speakers if s in female]
        if hasattr(self, "favorites_only") and self.favorites_only.isChecked():
            speakers = [s for s in speakers if self.ratings.get(s, VoiceRating(s)).favorite]
        if query:
            speakers = [s for s in speakers if query in s.casefold()]
        return speakers

    def _populate_speakers(self):
        if not hasattr(self, "speaker_list"):
            return
        current = self.current_speaker()
        self.speaker_list.blockSignals(True)
        self.speaker_list.clear()
        for speaker in self._filtered_speakers():
            rating = self.ratings.get(speaker, VoiceRating(speaker))
            prefix = "★ " if rating.favorite else ""
            suffix = f"  [{rating.score:.1f}]" if rating.score else ""
            item = QListWidgetItem(f"{prefix}{speaker}{suffix}")
            item.setData(Qt.UserRole, speaker)
            self.speaker_list.addItem(item)
        self.speaker_list.blockSignals(False)
        self.counter.setText(f"{self.speaker_list.count()} affichées / {len(self.speakers)} détectées")
        if current:
            for row in range(self.speaker_list.count()):
                if self.speaker_list.item(row).data(Qt.UserRole) == current:
                    self.speaker_list.setCurrentRow(row)
                    break
        elif self.speaker_list.count():
            self.speaker_list.setCurrentRow(0)

    def current_speaker(self) -> str:
        item = self.speaker_list.currentItem() if hasattr(self, "speaker_list") else None
        return str(item.data(Qt.UserRole)) if item else ""

    def _on_speaker_changed(self, current, _previous):
        speaker = str(current.data(Qt.UserRole)) if current else ""
        self._load_rating(speaker)

    def _load_rating(self, speaker: str):
        self._loading_rating = True
        try:
            self.current_name.setText(speaker or "—")
            index = self.speakers.index(speaker) + 1 if speaker in self.speakers else 0
            curated = " · présélection féminine" if speaker in XTTS_FEMALE_PRESETS else ""
            self.current_meta.setText(f"Speaker {index}/{len(self.speakers)}{curated}")
            rating = self.ratings.get(speaker, VoiceRating(speaker))
            self.naturality.setValue(rating.naturality)
            self.warmth.setValue(rating.warmth)
            self.sensuality.setValue(rating.sensuality)
            self.preference.setValue(rating.preference)
            self.favorite.setChecked(rating.favorite)
            self.notes.setPlainText(rating.notes)
            self._update_score(rating)
        finally:
            self._loading_rating = False

    def _rating_from_ui(self) -> VoiceRating | None:
        speaker = self.current_speaker()
        if not speaker:
            return None
        return VoiceRating(
            speaker=speaker,
            naturality=self.naturality.value(),
            warmth=self.warmth.value(),
            sensuality=self.sensuality.value(),
            preference=self.preference.value(),
            favorite=self.favorite.isChecked(),
            notes=self.notes.toPlainText(),
        ).normalized()

    def _autosave_rating(self):
        if self._loading_rating:
            return
        rating = self._rating_from_ui()
        if rating is None:
            return
        self.ratings[rating.speaker] = rating
        self.rating_store.save_all(self.ratings)
        self._update_score(rating)

    def _update_score(self, rating: VoiceRating):
        self.score_label.setText(f"Score : {rating.score:.2f}/5" if rating.score else "Score : non notée")

    def _move_selection(self, delta: int):
        count = self.speaker_list.count()
        if not count:
            return
        row = self.speaker_list.currentRow()
        self.speaker_list.setCurrentRow((row + delta) % count)

    # ------------------------------------------------------------------
    def _set_busy(self, busy: bool):
        self.play_button.setEnabled(not busy)
        self.prev_button.setEnabled(not busy)
        self.next_button.setEnabled(not busy)
        self.apply_button.setEnabled(not busy)
        self.speaker_list.setEnabled(not busy)

    def _play_current(self):
        speaker = self.current_speaker()
        text = self.preview_text.toPlainText().strip()
        if not speaker or not text or self._preview_thread is not None:
            return
        self._set_busy(True)
        self.status.setText(f"Synthèse XTTS : {speaker}…")
        self._preview_thread = QThread()
        self._preview_worker = VoicePreviewWorker(self.engine, speaker, text, self.fast_preview.isChecked())
        self._preview_worker.moveToThread(self._preview_thread)
        self._preview_thread.started.connect(self._preview_worker.run)
        self._preview_worker.finished.connect(self._on_preview_finished)
        self._preview_worker.failed.connect(self._on_preview_failed)
        self._preview_worker.finished.connect(self._preview_thread.quit)
        self._preview_worker.failed.connect(self._preview_thread.quit)
        self._preview_thread.finished.connect(self._cleanup_preview)
        self._preview_thread.start()

    def _on_preview_finished(self, speaker: str, metrics):
        device = getattr(metrics, "device", "?").upper()
        synth = float(getattr(metrics, "synthesis_seconds", 0.0) or 0.0)
        chars = int(getattr(metrics, "text_chars", 0) or 0)
        self.status.setText(
            f"Lecture terminée : {speaker} · {device} · audio prêt en {synth:.2f}s · {chars} caractères."
        )
        self._set_busy(False)

    def _on_preview_failed(self, message: str):
        self.status.setText(f"Échec XTTS : {message}")
        self._set_busy(False)

    def _cleanup_preview(self):
        if self._preview_worker is not None:
            self._preview_worker.deleteLater()
        if self._preview_thread is not None:
            self._preview_thread.deleteLater()
        self._preview_worker = None
        self._preview_thread = None

    # ------------------------------------------------------------------
    def _apply_current_voice(self):
        speaker = self.current_speaker()
        if not speaker:
            return
        profile = self.profile_store.load()
        profile.engine = "xtts"
        profile.xtts_mode = "preset"
        profile.xtts_preset = speaker
        saved = self.profile_store.save(profile)
        self.profile_selected.emit(saved)
        QMessageBox.information(self, "Voix AURA", f"{speaker} est maintenant la voix XTTS sélectionnée pour AURA.")

    def _export_ranking(self):
        default = str(Path.cwd() / "exports" / "xtts_voice_ranking.csv")
        destination, _ = QFileDialog.getSaveFileName(self, "Exporter le classement", default, "CSV (*.csv)")
        if not destination:
            return
        path = self.rating_store.export_csv(Path(destination))
        QMessageBox.information(self, "Classement exporté", f"Classement enregistré :\n{path}")

    def closeEvent(self, event):
        try:
            self.engine.stop_speaking()
        finally:
            super().closeEvent(event)
