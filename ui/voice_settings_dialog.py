"""Voice settings dialog for AURA v0.5.2."""
from __future__ import annotations

from pathlib import Path
import logging

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

from voice.voice_profile import VoiceProfile, VoiceProfileStore, XTTS_FEMALE_PRESETS
from voice.elevenlabs_tts import ElevenLabsTTS
from voice.gradium_tts import GradiumTTS
from voice.gradium_dependency import install_websockets_for_current_aura, probe_websockets
from voice.resemble_tts import ResembleTTS
from voice.errors import SpeechSynthesisUnavailableError
from config.settings import (
    settings,
    persist_local_env_value,
    read_elevenlabs_env_import,
    valid_elevenlabs_api_key,
    valid_cloud_api_token,
)


logger = logging.getLogger("aura.ui.voice_settings")


class _GradiumDependencyWorker(QObject):
    finished = Signal(object)

    def run(self):
        self.finished.emit(install_websockets_for_current_aura())


class VoiceSettingsDialog(QDialog):
    profile_saved = Signal(object)
    test_requested = Signal(str)
    voice_lab_requested = Signal()

    def __init__(self, store: VoiceProfileStore, parent=None, xtts_speakers: tuple[str, ...] | None = None):
        super().__init__(parent)
        self.store = store
        self.profile = store.load()
        self.xtts_speakers = tuple(xtts_speakers or ())
        self.setWindowTitle("Voix d'AURA")
        self.setMinimumWidth(520)
        self._build_ui()
        self._load_profile()

    def _build_ui(self):
        root = QVBoxLayout(self)
        intro = QLabel(
            "Choisis la voix d'AURA. XTTS est plus naturel et peut utiliser une voix prédéfinie "
            "ou un WAV de référence pour lequel tu as l'autorisation d'utilisation."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("Gradium (cloud · temps réel)", "gradium")
        self.engine_combo.addItem("ElevenLabs (cloud · réponses courtes)", "elevenlabs")
        self.engine_combo.addItem("Resemble AI (cloud · streaming HTTP)", "resemble")
        self.engine_combo.addItem("Chatterbox Multilingual V3 (local · expérimental)", "chatterbox")
        self.engine_combo.addItem("XTTS-v2 (local naturel)", "xtts")
        self.engine_combo.addItem("Piper (local rapide)", "piper")
        self.engine_combo.currentIndexChanged.connect(self._refresh_mode)
        form.addRow("Moteur", self.engine_combo)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Voix XTTS prédéfinie", "preset")
        self.mode_combo.addItem("Voix personnalisée (WAV autorisé)", "custom")
        self.mode_combo.currentIndexChanged.connect(self._refresh_mode)
        form.addRow("Mode XTTS", self.mode_combo)

        self.preset_combo = QComboBox()
        if self.xtts_speakers:
            female_runtime = [name for name in self.xtts_speakers if name in XTTS_FEMALE_PRESETS]
            speaker_choices = female_runtime or list(self.xtts_speakers)
        else:
            speaker_choices = list(XTTS_FEMALE_PRESETS)
        self.preset_combo.addItems(speaker_choices)
        form.addRow("Speaker XTTS", self.preset_combo)

        source = "modèle XTTS installé" if self.xtts_speakers else "liste de secours (modèle non interrogé)"
        self.speaker_source_label = QLabel(f"{len(speaker_choices)} voix · {source}")
        self.speaker_source_label.setWordWrap(True)
        form.addRow("Source des voix", self.speaker_source_label)

        eleven_row = QHBoxLayout()
        self.eleven_voice_combo = QComboBox()
        self.eleven_voice_combo.setMinimumWidth(240)
        self.eleven_refresh_button = QPushButton("Actualiser")
        self.eleven_refresh_button.clicked.connect(self._refresh_elevenlabs_voices)
        eleven_row.addWidget(self.eleven_voice_combo, 1)
        eleven_row.addWidget(self.eleven_refresh_button)
        form.addRow("Voix ElevenLabs", eleven_row)

        self.eleven_model_combo = QComboBox()
        self.eleven_model_combo.addItem("Flash v2.5 · faible latence", "eleven_flash_v2_5")
        self.eleven_model_combo.addItem("Multilingual v2 · qualité", "eleven_multilingual_v2")
        form.addRow("Modèle ElevenLabs", self.eleven_model_combo)

        self.eleven_stability_slider = QSlider(Qt.Horizontal)
        self.eleven_stability_slider.setRange(0, 100)
        self.eleven_stability_value = QLabel()
        self.eleven_stability_slider.valueChanged.connect(
            lambda value: self.eleven_stability_value.setText(f"{value/100:.2f}")
        )
        eleven_stability_row = QHBoxLayout()
        eleven_stability_row.addWidget(self.eleven_stability_slider, 1)
        eleven_stability_row.addWidget(self.eleven_stability_value)
        form.addRow("Stabilité ElevenLabs", eleven_stability_row)

        self.eleven_similarity_slider = QSlider(Qt.Horizontal)
        self.eleven_similarity_slider.setRange(0, 100)
        self.eleven_similarity_value = QLabel()
        self.eleven_similarity_slider.valueChanged.connect(
            lambda value: self.eleven_similarity_value.setText(f"{value/100:.2f}")
        )
        eleven_similarity_row = QHBoxLayout()
        eleven_similarity_row.addWidget(self.eleven_similarity_slider, 1)
        eleven_similarity_row.addWidget(self.eleven_similarity_value)
        form.addRow("Similarité ElevenLabs", eleven_similarity_row)

        self.eleven_speed_slider = QSlider(Qt.Horizontal)
        self.eleven_speed_slider.setRange(70, 120)
        self.eleven_speed_value = QLabel()
        self.eleven_speed_slider.valueChanged.connect(
            lambda value: self.eleven_speed_value.setText(f"{value/100:.2f}x")
        )
        eleven_speed_row = QHBoxLayout()
        eleven_speed_row.addWidget(self.eleven_speed_slider, 1)
        eleven_speed_row.addWidget(self.eleven_speed_value)
        form.addRow("Débit ElevenLabs", eleven_speed_row)

        key_row = QHBoxLayout()
        self.eleven_key_edit = QLineEdit()
        self.eleven_key_edit.setEchoMode(QLineEdit.Password)
        self.eleven_key_edit.setPlaceholderText(
            "Clé déjà configurée · laisser vide pour la conserver"
            if settings.ELEVENLABS_API_KEY else "Coller la clé API ElevenLabs"
        )
        # v0.7.1.3.4.3: ElevenLabs setup must remain editable even when
        # another TTS engine (XTTS/Piper) is currently selected.
        self.eleven_key_edit.textChanged.connect(self._update_elevenlabs_setup_state)
        self.eleven_key_paste = QPushButton("Coller")
        self.eleven_key_paste.setToolTip("Colle le contenu du presse-papiers dans le champ de clé")
        self.eleven_key_paste.clicked.connect(self._paste_elevenlabs_key)
        self.eleven_key_toggle = QPushButton("Afficher")
        self.eleven_key_toggle.setCheckable(True)
        self.eleven_key_toggle.toggled.connect(self._toggle_elevenlabs_key_visibility)
        self.eleven_key_apply = QPushButton("Appliquer")
        self.eleven_key_apply.clicked.connect(self._apply_elevenlabs_key_and_refresh)
        key_row.addWidget(self.eleven_key_edit, 1)
        key_row.addWidget(self.eleven_key_paste)
        key_row.addWidget(self.eleven_key_toggle)
        key_row.addWidget(self.eleven_key_apply)
        form.addRow("Clé ElevenLabs", key_row)

        import_row = QHBoxLayout()
        self.eleven_import_jarvis = QPushButton("Importer un .env Jarvis…")
        self.eleven_import_jarvis.setToolTip("Importe uniquement ELEVENLABS_API_KEY et ELEVENLABS_VOICE_ID depuis un .env choisi")
        self.eleven_import_jarvis.clicked.connect(self._import_jarvis_env)
        import_row.addWidget(self.eleven_import_jarvis)
        import_row.addStretch()
        form.addRow("Import ElevenLabs", import_row)

        self.eleven_status_label = QLabel(
            "Clé API configurée · actualise la liste des voix"
            if settings.ELEVENLABS_API_KEY else
            "Clé API absente · colle-la ici pour activer la sélection de voix"
        )
        self.eleven_status_label.setWordWrap(True)
        form.addRow("ElevenLabs", self.eleven_status_label)

        self.eleven_quota_label = QLabel("Quota : non vérifié")
        self.eleven_quota_label.setWordWrap(True)
        form.addRow("Quota ElevenLabs", self.eleven_quota_label)

        # v0.7.1.3.5 multi-provider setup. Secrets remain in .env only;
        # voice identifiers are non-secret and may be persisted in voice_profile.json.
        grad_key_row = QHBoxLayout()
        self.gradium_key_edit = QLineEdit(); self.gradium_key_edit.setEchoMode(QLineEdit.Password); self.gradium_key_edit.textChanged.connect(self._update_provider_setup_state)
        self.gradium_key_edit.setPlaceholderText("Clé Gradium déjà configurée" if settings.GRADIUM_API_KEY else "Clé API Gradium")
        self.gradium_key_paste = QPushButton("Coller"); self.gradium_key_paste.clicked.connect(lambda: self._paste_provider_key("gradium"))
        self.gradium_key_apply = QPushButton("Appliquer"); self.gradium_key_apply.clicked.connect(lambda: self._apply_provider_key("gradium"))
        grad_key_row.addWidget(self.gradium_key_edit,1); grad_key_row.addWidget(self.gradium_key_paste); grad_key_row.addWidget(self.gradium_key_apply)
        form.addRow("Clé Gradium", grad_key_row)
        grad_voice_row = QHBoxLayout()
        self.gradium_voice_edit = QLineEdit(); self.gradium_voice_edit.setPlaceholderText("Voice ID Gradium (Studio / bibliothèque)")
        self.gradium_refresh_button = QPushButton("Voix compte"); self.gradium_refresh_button.clicked.connect(self._refresh_gradium_voices)
        self.gradium_voice_combo = QComboBox(); self.gradium_voice_combo.setMinimumWidth(180); self.gradium_voice_combo.currentIndexChanged.connect(self._select_gradium_voice_from_combo)
        grad_voice_row.addWidget(self.gradium_voice_edit,1); grad_voice_row.addWidget(self.gradium_voice_combo); grad_voice_row.addWidget(self.gradium_refresh_button)
        form.addRow("Voix Gradium", grad_voice_row)
        self.gradium_status_label = QLabel("Gradium : non vérifié"); self.gradium_status_label.setWordWrap(True); form.addRow("Gradium", self.gradium_status_label)
        grad_transport_row = QHBoxLayout()
        self.gradium_transport_label = QLabel(self._gradium_transport_text()); self.gradium_transport_label.setWordWrap(True)
        self.gradium_install_button = QPushButton("Installer WebSocket")
        self.gradium_install_button.clicked.connect(self._install_gradium_websocket)
        grad_transport_row.addWidget(self.gradium_transport_label, 1); grad_transport_row.addWidget(self.gradium_install_button)
        form.addRow("Transport Gradium", grad_transport_row)
        self._gradium_install_thread = None
        self._gradium_install_worker = None

        res_key_row = QHBoxLayout()
        self.resemble_key_edit = QLineEdit(); self.resemble_key_edit.setEchoMode(QLineEdit.Password); self.resemble_key_edit.textChanged.connect(self._update_provider_setup_state)
        self.resemble_key_edit.setPlaceholderText("Token Resemble déjà configuré" if settings.RESEMBLE_API_KEY else "Token API Resemble")
        self.resemble_key_paste = QPushButton("Coller"); self.resemble_key_paste.clicked.connect(lambda: self._paste_provider_key("resemble"))
        self.resemble_key_apply = QPushButton("Appliquer"); self.resemble_key_apply.clicked.connect(lambda: self._apply_provider_key("resemble"))
        res_key_row.addWidget(self.resemble_key_edit,1); res_key_row.addWidget(self.resemble_key_paste); res_key_row.addWidget(self.resemble_key_apply)
        form.addRow("Token Resemble", res_key_row)
        res_voice_row = QHBoxLayout()
        self.resemble_language_combo = QComboBox()
        self.resemble_language_combo.addItem("Français", "fr")
        self.resemble_language_combo.addItem("Toutes", "all")
        self.resemble_language_combo.currentIndexChanged.connect(self._populate_resemble_voice_combo)
        self.resemble_voice_combo = QComboBox(); self.resemble_voice_combo.setMinimumWidth(260)
        self.resemble_refresh_button = QPushButton("Actualiser"); self.resemble_refresh_button.clicked.connect(self._refresh_resemble_voices)
        res_voice_row.addWidget(self.resemble_language_combo); res_voice_row.addWidget(self.resemble_voice_combo,1); res_voice_row.addWidget(self.resemble_refresh_button)
        form.addRow("Voix Resemble", res_voice_row)
        self._resemble_voices = ()
        self.resemble_status_label = QLabel("Resemble : non vérifié"); self.resemble_status_label.setWordWrap(True); form.addRow("Resemble", self.resemble_status_label)

        self.chatterbox_status_label = QLabel(
            "Chatterbox local : prêt" if settings.CHATTERBOX_ENABLED and settings.CHATTERBOX_ALLOW_MODEL_LOAD else
            "Chatterbox local : désactivé par sécurité (aucun téléchargement/chargement automatique)"
        )
        self.chatterbox_status_label.setWordWrap(True); form.addRow("Chatterbox", self.chatterbox_status_label)

        ref_row = QHBoxLayout()
        self.reference_label = QLabel("Aucune référence")
        self.reference_label.setWordWrap(True)
        self.reference_button = QPushButton("Importer WAV…")
        self.reference_button.clicked.connect(self._choose_reference)
        ref_row.addWidget(self.reference_label, 1)
        ref_row.addWidget(self.reference_button)
        form.addRow("Référence", ref_row)

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(85, 105)
        self.speed_value = QLabel()
        self.speed_slider.valueChanged.connect(lambda value: self.speed_value.setText(f"{value/100:.2f}x"))
        speed_row = QHBoxLayout()
        speed_row.addWidget(self.speed_slider, 1)
        speed_row.addWidget(self.speed_value)
        form.addRow("Débit", speed_row)

        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(50, 85)
        self.temp_value = QLabel()
        self.temp_slider.valueChanged.connect(lambda value: self.temp_value.setText(f"{value/100:.2f}"))
        temp_row = QHBoxLayout()
        temp_row.addWidget(self.temp_slider, 1)
        temp_row.addWidget(self.temp_value)
        form.addRow("Expressivité XTTS", temp_row)
        root.addLayout(form)

        note = QLabel(
            "Conseil : pour une voix personnalisée, utilise 8 à 20 secondes de voix seule, claire, sans musique ni réverbération."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QHBoxLayout()
        self.test_button = QPushButton("Tester la voix")
        self.test_button.clicked.connect(self._test)
        self.lab_button = QPushButton("Laboratoire des 58 voix…")
        self.lab_button.clicked.connect(self.voice_lab_requested.emit)
        save_button = QPushButton("Enregistrer")
        save_button.clicked.connect(self._save)
        close_button = QPushButton("Fermer")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(self.test_button)
        buttons.addWidget(self.lab_button)
        buttons.addStretch()
        buttons.addWidget(save_button)
        buttons.addWidget(close_button)
        root.addLayout(buttons)

    def _load_profile(self):
        self.engine_combo.setCurrentIndex(max(0, self.engine_combo.findData(self.profile.engine)))
        self._populate_elevenlabs_saved_voice()
        model_index = self.eleven_model_combo.findData(self.profile.elevenlabs_model)
        self.eleven_model_combo.setCurrentIndex(max(0, model_index))
        self.eleven_stability_slider.setValue(round(self.profile.elevenlabs_stability * 100))
        self.eleven_similarity_slider.setValue(round(self.profile.elevenlabs_similarity * 100))
        self.eleven_speed_slider.setValue(round(self.profile.elevenlabs_speed * 100))
        self.gradium_voice_edit.setText(self.profile.gradium_voice_id)
        self.gradium_voice_combo.clear()
        if self.profile.gradium_voice_id:
            self.gradium_voice_combo.addItem(self.profile.gradium_voice_name or self.profile.gradium_voice_id, self.profile.gradium_voice_id)
        else:
            self.gradium_voice_combo.addItem("Voix compte…", "")
        self.resemble_voice_combo.clear()
        if self.profile.resemble_voice_uuid:
            self.resemble_voice_combo.addItem(self.profile.resemble_voice_name or self.profile.resemble_voice_uuid, self.profile.resemble_voice_uuid)
        else:
            self.resemble_voice_combo.addItem("Choisir une voix…", "")
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(self.profile.xtts_mode)))
        preset_index = self.preset_combo.findText(self.profile.xtts_preset)
        if preset_index < 0:
            preset_index = 0
        self.preset_combo.setCurrentIndex(max(0, preset_index))
        self.speed_slider.setValue(round(self.profile.xtts_speed * 100))
        self.temp_slider.setValue(round(self.profile.xtts_temperature * 100))
        self._update_reference_label()
        self._refresh_mode()
        self._update_elevenlabs_setup_state()
        self._update_provider_setup_state()

    def _update_reference_label(self):
        path = self.profile.xtts_reference_wav
        self.reference_label.setText(Path(path).name if path else "Aucune référence")

    def _refresh_mode(self):
        engine = str(self.engine_combo.currentData() or "")
        xtts = engine == "xtts"
        eleven = engine == "elevenlabs"
        custom = xtts and self.mode_combo.currentData() == "custom"
        self.mode_combo.setEnabled(xtts)
        self.preset_combo.setEnabled(xtts and not custom)
        self.reference_button.setEnabled(custom)
        self.reference_label.setEnabled(custom)
        # ElevenLabs is optional and can be configured independently from the
        # currently selected engine. This prevents first-run setup from being
        # locked behind an XTTS/Piper profile.
        self.eleven_key_edit.setEnabled(True)
        self.eleven_key_paste.setEnabled(True)
        self.eleven_key_toggle.setEnabled(True)
        self.eleven_key_apply.setEnabled(True)
        self.eleven_import_jarvis.setEnabled(True)
        self.eleven_model_combo.setEnabled(True)
        self.eleven_stability_slider.setEnabled(True)
        self.eleven_similarity_slider.setEnabled(True)
        self.eleven_speed_slider.setEnabled(True)
        self._update_elevenlabs_setup_state()
        self._update_provider_setup_state()


    def _update_provider_setup_state(self, *_args):
        """Keep Gradium/Resemble first-run setup usable for every active engine."""
        for provider in ("gradium", "resemble"):
            is_grad = provider == "gradium"
            edit = self.gradium_key_edit if is_grad else self.resemble_key_edit
            apply_button = self.gradium_key_apply if is_grad else self.resemble_key_apply
            refresh_button = self.gradium_refresh_button if is_grad else self.resemble_refresh_button
            combo = self.gradium_voice_combo if is_grad else self.resemble_voice_combo
            saved = bool(settings.GRADIUM_API_KEY if is_grad else settings.RESEMBLE_API_KEY)
            entered = str(edit.text() or "").strip()
            entered_valid = valid_cloud_api_token(entered) if entered else False
            edit.setEnabled(True)
            apply_button.setEnabled(saved or bool(entered))
            refresh_button.setEnabled(saved or entered_valid)
            has_voice = bool(self.profile.gradium_voice_id if is_grad else self.profile.resemble_voice_uuid)
            combo.setEnabled(saved or has_voice)


    def _update_elevenlabs_setup_state(self, *_args):
        """Keep first-time ElevenLabs setup usable regardless of active engine."""
        entered = str(self.eleven_key_edit.text() or "").strip() if hasattr(self, "eleven_key_edit") else ""
        has_saved_key = bool(settings.ELEVENLABS_API_KEY)
        entered_valid = valid_elevenlabs_api_key(entered) if entered else False
        can_query = has_saved_key or entered_valid
        if hasattr(self, "eleven_refresh_button"):
            self.eleven_refresh_button.setEnabled(can_query)
        if hasattr(self, "eleven_voice_combo"):
            has_saved_voice = bool(self.profile.elevenlabs_voice_id)
            self.eleven_voice_combo.setEnabled(can_query or has_saved_voice)
        if hasattr(self, "eleven_key_apply"):
            # Keep Apply available with a saved key too: an empty field means
            # "keep current" and must not trap the user in a disabled state.
            self.eleven_key_apply.setEnabled(has_saved_key or bool(entered))
        if hasattr(self, "eleven_status_label") and entered and not entered_valid:
            self.eleven_status_label.setText("Clé saisie non reconnue · vérifie la valeur avant d'appliquer")

    @staticmethod
    def _quota_text(quota: dict) -> str:
        used = int(quota.get("character_count") or 0)
        limit = int(quota.get("character_limit") or 0)
        if limit <= 0:
            return "Quota : limite incluse non mesurable · Piper restera le filet de sécurité"
        remaining = max(0, limit - used)
        pct = min(100.0, max(0.0, (used / limit) * 100.0)) if limit else 0.0
        return f"Quota : {remaining} crédits restants · {used}/{limit} utilisés ({pct:.1f} %)"

    def _paste_elevenlabs_key(self):
        clipboard = QApplication.clipboard()
        text = str(clipboard.text() or "").strip() if clipboard is not None else ""
        if not text:
            self.eleven_status_label.setText("Presse-papiers vide · copie d'abord la clé ElevenLabs")
            return
        self.eleven_key_edit.setText(text)
        self.eleven_key_edit.setFocus()
        self._update_elevenlabs_setup_state()
        if valid_elevenlabs_api_key(text):
            self.eleven_status_label.setText("Clé collée · clique sur Appliquer ou Actualiser")
        else:
            self.eleven_status_label.setText("Valeur collée, mais elle ne ressemble pas à une clé API valide")

    def _import_jarvis_env(self):
        source, _ = QFileDialog.getOpenFileName(
            self,
            "Importer la configuration ElevenLabs de Jarvis",
            "",
            "Fichiers environnement (.env *.env);;Tous les fichiers (*)",
        )
        if not source:
            return
        try:
            values = read_elevenlabs_env_import(source)
        except (OSError, UnicodeError, ValueError) as exc:
            QMessageBox.warning(self, "ElevenLabs", f"Import Jarvis impossible : {exc}")
            return
        key = values.get("ELEVENLABS_API_KEY", "")
        if not valid_elevenlabs_api_key(key):
            QMessageBox.warning(
                self,
                "ElevenLabs",
                "Ce .env Jarvis ne contient pas de vraie clé ELEVENLABS_API_KEY. "
                "Une valeur d'exemple comme sk_... n'est pas importable.",
            )
            return
        self.eleven_key_edit.setText(key)
        voice_id = values.get("ELEVENLABS_VOICE_ID", "").strip()
        if voice_id:
            label = f"Voix Jarvis · {voice_id}"
            idx = self.eleven_voice_combo.findData(voice_id)
            if idx < 0:
                self.eleven_voice_combo.addItem(label, voice_id)
                idx = self.eleven_voice_combo.findData(voice_id)
            self.eleven_voice_combo.setCurrentIndex(max(0, idx))
            self.eleven_voice_combo.setEnabled(True)
        model = values.get("ELEVENLABS_MODEL", "").strip()
        if model:
            idx = self.eleven_model_combo.findData(model)
            if idx >= 0:
                self.eleven_model_combo.setCurrentIndex(idx)
        try:
            speed = float(values.get("ELEVENLABS_SPEED", "") or self.profile.elevenlabs_speed)
            self.eleven_speed_slider.setValue(round(min(1.2, max(0.7, speed)) * 100))
        except ValueError:
            pass
        self.eleven_status_label.setText("Configuration Jarvis importée · clique sur Appliquer pour vérifier la clé")

    def _toggle_elevenlabs_key_visibility(self, visible: bool):
        self.eleven_key_edit.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)
        self.eleven_key_toggle.setText("Masquer" if visible else "Afficher")

    def _apply_elevenlabs_key(self, *, show_message: bool = False) -> bool:
        entered = self.eleven_key_edit.text().strip()
        if not entered:
            return bool(settings.ELEVENLABS_API_KEY)
        if not valid_elevenlabs_api_key(entered):
            QMessageBox.warning(
                self,
                "ElevenLabs",
                "Clé ElevenLabs invalide. Colle la clé API secrète complète commençant par 'sk_'. "
                "L'identifiant de clé affiché dans le tableau ElevenLabs n'est pas une clé API utilisable.",
            )
            return False
        try:
            persist_local_env_value("ELEVENLABS_API_KEY", entered)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "ElevenLabs", f"Impossible d'enregistrer la clé localement : {exc}")
            return False
        # Settings is a singleton populated at import time; update this one
        # field immediately so voice discovery works without restarting AURA.
        settings.ELEVENLABS_API_KEY = entered
        self.eleven_key_edit.clear()
        self._update_elevenlabs_setup_state()
        self.eleven_key_edit.setPlaceholderText("Clé déjà configurée · laisser vide pour la conserver")
        self.eleven_status_label.setText("Clé API configurée · récupération des voix possible")
        self._refresh_mode()
        if show_message:
            QMessageBox.information(self, "ElevenLabs", "Clé enregistrée dans le .env local d'AURA.")
        return True

    def _apply_elevenlabs_key_and_refresh(self):
        if self._apply_elevenlabs_key(show_message=False):
            self._refresh_elevenlabs_voices()
        else:
            QMessageBox.warning(self, "ElevenLabs", "Colle d'abord ta clé API ElevenLabs.")

    def _populate_elevenlabs_saved_voice(self):
        self.eleven_voice_combo.clear()
        if self.profile.elevenlabs_voice_id:
            label = self.profile.elevenlabs_voice_name or self.profile.elevenlabs_voice_id
            self.eleven_voice_combo.addItem(label, self.profile.elevenlabs_voice_id)
        else:
            self.eleven_voice_combo.addItem("Choisir une voix…", "")

    def _refresh_elevenlabs_voices(self):
        if self.eleven_key_edit.text().strip() and not self._apply_elevenlabs_key(show_message=False):
            return
        if not settings.ELEVENLABS_API_KEY:
            QMessageBox.warning(self, "ElevenLabs", "Colle d'abord ta clé API ElevenLabs puis clique sur Actualiser.")
            return
        try:
            voices = ElevenLabsTTS.list_voices(force_refresh=True)
        except SpeechSynthesisUnavailableError as exc:
            diagnostics_text = ""
            try:
                diag = ElevenLabsTTS.api_diagnostics()
                labels = {"user": "Authentification", "quota": "Quota", "voices": "Voix"}
                lines = []
                for key in ("user", "quota", "voices"):
                    item = diag.get(key) or {}
                    if item.get("ok"):
                        lines.append(f"{labels[key]} : OK")
                    else:
                        http = int(item.get("http") or 0)
                        detail = str(item.get("detail") or "").strip()
                        suffix = f" · {detail}" if detail else ""
                        lines.append(f"{labels[key]} : ERREUR HTTP {http}{suffix}")
                diagnostics_text = "\n\nDiagnostic lecture seule :\n" + "\n".join(lines)
            except Exception:
                diagnostics_text = ""
            QMessageBox.warning(self, "ElevenLabs", str(exc) + diagnostics_text)
            return
        selected = str(self.eleven_voice_combo.currentData() or self.profile.elevenlabs_voice_id or "")
        self.eleven_voice_combo.clear()
        for voice in voices:
            suffix = f" · {voice.category}" if voice.category else ""
            self.eleven_voice_combo.addItem(f"{voice.name}{suffix}", voice.voice_id)
        if not voices:
            self.eleven_voice_combo.addItem("Aucune voix accessible avec cette clé", "")
        self.eleven_voice_combo.setEnabled(bool(voices))
        index = self.eleven_voice_combo.findData(selected)
        if index >= 0:
            self.eleven_voice_combo.setCurrentIndex(index)
        try:
            quota = ElevenLabsTTS.quota_status(force_refresh=True)
            self.eleven_quota_label.setText(self._quota_text(quota))
            quota_text = " · quota vérifié"
        except SpeechSynthesisUnavailableError as exc:
            self.eleven_quota_label.setText(f"Quota : non vérifiable · {exc}")
            quota_text = " · quota non vérifiable (Piper sera utilisé)"
        self.eleven_status_label.setText(f"{len(voices)} voix disponibles · liste actualisée{quota_text}")

    # Legacy manual fallback remains available as INSTALL_GRADIUM_REALTIME.bat.
    @staticmethod
    def _gradium_transport_text() -> str:
        status = probe_websockets()
        if status.ready:
            return f"WebSocket temps réel prêt · websockets {status.version} · connexion persistante · REST en secours"
        return f"REST de secours actif · WebSocket absent dans le Python d'AURA : {status.interpreter}"

    def _install_gradium_websocket(self):
        if self._gradium_install_thread is not None and self._gradium_install_thread.isRunning():
            return
        self.gradium_install_button.setEnabled(False)
        self.gradium_install_button.setText("Installation…")
        self.gradium_transport_label.setText("Installation de websockets dans le Python exact d'AURA…")
        thread = QThread(self)
        worker = _GradiumDependencyWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._gradium_dependency_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._gradium_install_thread = thread
        self._gradium_install_worker = worker
        thread.start()

    def _gradium_dependency_finished(self, status):
        self._gradium_install_thread = None
        self._gradium_install_worker = None
        self.gradium_install_button.setEnabled(True)
        self.gradium_install_button.setText("Réinstaller WebSocket" if status.ready else "Réessayer")
        self.gradium_transport_label.setText(self._gradium_transport_text())
        if status.ready:
            self.gradium_status_label.setText(f"Gradium : WebSocket prêt · websockets {status.version}")
            QMessageBox.information(
                self,
                "Gradium temps réel",
                f"Installation réussie dans le Python utilisé par AURA.\n\n{status.interpreter}\nwebsockets {status.version}\n\nTu peux tester Gradium immédiatement.",
            )
        else:
            logger.warning("Gradium dependency auto-setup failed interpreter=%r detail=%s", status.interpreter, status.detail)
            self.gradium_status_label.setText("Gradium : installation WebSocket échouée · REST reste disponible")
            QMessageBox.warning(
                self,
                "Gradium temps réel",
                "Impossible d'installer websockets dans le Python d'AURA.\n\n"
                f"Interpréteur : {status.interpreter}\n\n{status.detail}\n\n"
                "Gradium continue automatiquement avec le transport REST.",
            )

    def _paste_provider_key(self, provider: str):
        text = str(QApplication.clipboard().text() or "").strip()
        edit = self.gradium_key_edit if provider == "gradium" else self.resemble_key_edit
        status = self.gradium_status_label if provider == "gradium" else self.resemble_status_label
        if not text:
            status.setText(f"{provider.title()} : presse-papiers vide")
            return
        edit.setText(text); edit.setFocus()

    def _apply_provider_key(self, provider: str, *, show_message: bool = True, refresh_after: bool = True) -> bool:
        is_grad = provider == "gradium"
        edit = self.gradium_key_edit if is_grad else self.resemble_key_edit
        current = settings.GRADIUM_API_KEY if is_grad else settings.RESEMBLE_API_KEY
        value = str(edit.text() or "").strip()
        if not value:
            return bool(current)
        if not valid_cloud_api_token(value):
            QMessageBox.warning(self, provider.title(), "Clé/token invalide ou incomplet.")
            return False
        env_name = "GRADIUM_API_KEY" if is_grad else "RESEMBLE_API_KEY"
        try:
            persist_local_env_value(env_name, value)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, provider.title(), f"Impossible d'enregistrer le secret localement : {exc}")
            return False
        if is_grad: settings.GRADIUM_API_KEY = value
        else: settings.RESEMBLE_API_KEY = value
        edit.clear(); edit.setPlaceholderText("Clé déjà configurée · laisser vide pour la conserver")
        status = self.gradium_status_label if is_grad else self.resemble_status_label
        status.setText(f"{provider.title()} : secret configuré · chargement des voix…" if refresh_after else f"{provider.title()} : secret configuré")
        self._update_provider_setup_state()
        if refresh_after:
            if is_grad:
                self._refresh_gradium_voices(secret_already_applied=True)
            else:
                self._refresh_resemble_voices(secret_already_applied=True)
        if show_message:
            QMessageBox.information(self, provider.title(), "Secret enregistré uniquement dans le .env local d'AURA. La liste des voix a été actualisée.")
        return True

    def _refresh_gradium_voices(self, *, secret_already_applied: bool = False):
        if not secret_already_applied and self.gradium_key_edit.text().strip() and not self._apply_provider_key("gradium", show_message=False, refresh_after=False): return
        if not settings.GRADIUM_API_KEY:
            QMessageBox.warning(self, "Gradium", "Configure d'abord la clé Gradium."); return
        try:
            voices = GradiumTTS.list_voices(force_refresh=True)
        except SpeechSynthesisUnavailableError as exc:
            logger.warning("Gradium voice refresh failed: %s", exc)
            self.gradium_voice_combo.clear(); self.gradium_voice_combo.addItem("Voix indisponibles", ""); self.gradium_voice_combo.setEnabled(False)
            self.gradium_status_label.setText(f"Gradium : {exc}")
            QMessageBox.warning(self, "Gradium", str(exc))
            return
        selected = str(self.gradium_voice_edit.text() or self.profile.gradium_voice_id or "").strip()
        self.gradium_voice_combo.clear()
        self.gradium_voice_combo.addItem("Choisir une voix Gradium…", "")
        for voice in voices:
            label = voice.name + (f" · {voice.language}" if voice.language else "")
            self.gradium_voice_combo.addItem(label, voice.voice_id)
        if not voices:
            self.gradium_voice_combo.addItem("Aucune voix accessible", "")
        self.gradium_voice_combo.setEnabled(bool(voices))
        idx=self.gradium_voice_combo.findData(selected)
        if idx>=0:self.gradium_voice_combo.setCurrentIndex(idx)
        self.gradium_status_label.setText(f"Gradium : {len(voices)} voix disponibles (catalogue inclus)")
        self.gradium_transport_label.setText(self._gradium_transport_text())
        logger.info("Gradium selector populated voices=%d", len(voices))
        self._update_provider_setup_state()

    def _select_gradium_voice_from_combo(self, *_args):
        uid=str(self.gradium_voice_combo.currentData() or "").strip()
        if uid:self.gradium_voice_edit.setText(uid)

    def _refresh_resemble_voices(self, *, secret_already_applied: bool = False):
        if not secret_already_applied and self.resemble_key_edit.text().strip() and not self._apply_provider_key("resemble", show_message=False, refresh_after=False): return
        if not settings.RESEMBLE_API_KEY:
            QMessageBox.warning(self, "Resemble", "Configure d'abord le token Resemble."); return
        try:
            voices=ResembleTTS.list_voices(force_refresh=True)
        except SpeechSynthesisUnavailableError as exc:
            logger.warning("Resemble voice refresh failed: %s", exc)
            self.resemble_voice_combo.clear(); self.resemble_voice_combo.addItem("Voix indisponibles", ""); self.resemble_voice_combo.setEnabled(False)
            self.resemble_status_label.setText(f"Resemble : {exc}")
            QMessageBox.warning(self, "Resemble AI", str(exc))
            return
        self._resemble_voices = tuple(voices)
        self._populate_resemble_voice_combo()
        french_count = sum(1 for voice in voices if voice.supports_french)
        self.resemble_status_label.setText(
            f"Resemble : {len(voices)} voix · {french_count} compatibles français"
            if french_count else
            f"Resemble : {len(voices)} voix · aucune voix marquée compatible français par l'API"
        )
        logger.info("Resemble selector populated voices=%d french_compatible=%d", len(voices), french_count)
        self._update_provider_setup_state()

    def _populate_resemble_voice_combo(self, *_args):
        voices = tuple(getattr(self, "_resemble_voices", ()) or ())
        selected = str(self.resemble_voice_combo.currentData() or self.profile.resemble_voice_uuid or "")
        mode = str(self.resemble_language_combo.currentData() or "fr") if hasattr(self, "resemble_language_combo") else "fr"
        visible = [voice for voice in voices if mode == "all" or voice.supports_french]
        self.resemble_voice_combo.clear()
        if not visible:
            text = "Aucune voix compatible français" if mode == "fr" else "Aucune voix accessible"
            self.resemble_voice_combo.addItem(text, "")
            self.resemble_voice_combo.setEnabled(False)
            return
        for voice in visible:
            langs = list(dict.fromkeys([voice.language, *voice.supported_languages]))
            langs = [lang for lang in langs if lang]
            language_label = ", ".join(langs[:4])
            prefix = "FR · " if voice.supports_french else ""
            label = prefix + voice.name + (f" · {language_label}" if language_label else "")
            self.resemble_voice_combo.addItem(label, voice.voice_uuid)
        self.resemble_voice_combo.setEnabled(True)
        idx = self.resemble_voice_combo.findData(selected)
        if idx >= 0:
            self.resemble_voice_combo.setCurrentIndex(idx)

    def _choose_reference(self):
        source, _ = QFileDialog.getOpenFileName(self, "Choisir une voix de référence", "", "Audio WAV (*.wav)")
        if not source:
            return
        answer = QMessageBox.question(
            self,
            "Autorisation de la voix",
            "Confirme que tu as le droit d'utiliser cette voix comme référence pour AURA. Continuer ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            destination = self.store.import_reference(source)
        except ValueError as exc:
            QMessageBox.warning(self, "Référence invalide", str(exc))
            return
        self.profile.xtts_reference_wav = str(destination)
        self._update_reference_label()

    def _current_profile(self) -> VoiceProfile:
        self.profile.engine = str(self.engine_combo.currentData())
        self.profile.xtts_mode = str(self.mode_combo.currentData())
        self.profile.xtts_preset = self.preset_combo.currentText()
        self.profile.xtts_speed = self.speed_slider.value() / 100.0
        self.profile.xtts_temperature = self.temp_slider.value() / 100.0
        self.profile.elevenlabs_voice_id = str(self.eleven_voice_combo.currentData() or "").strip()
        self.profile.elevenlabs_voice_name = self.eleven_voice_combo.currentText().split(" · ", 1)[0].strip() if self.profile.elevenlabs_voice_id else ""
        self.profile.elevenlabs_model = str(self.eleven_model_combo.currentData() or settings.ELEVENLABS_MODEL)
        self.profile.elevenlabs_stability = self.eleven_stability_slider.value() / 100.0
        self.profile.elevenlabs_similarity = self.eleven_similarity_slider.value() / 100.0
        self.profile.elevenlabs_speed = self.eleven_speed_slider.value() / 100.0
        self.profile.gradium_voice_id = str(self.gradium_voice_edit.text() or "").strip()
        grad_idx = self.gradium_voice_combo.findData(self.profile.gradium_voice_id)
        self.profile.gradium_voice_name = self.gradium_voice_combo.itemText(grad_idx).split(" · ",1)[0].strip() if grad_idx >= 0 else self.profile.gradium_voice_id
        self.profile.gradium_model = settings.GRADIUM_MODEL
        self.profile.resemble_voice_uuid = str(self.resemble_voice_combo.currentData() or "").strip()
        self.profile.resemble_voice_name = self.resemble_voice_combo.currentText().split(" · ",1)[0].strip() if self.profile.resemble_voice_uuid else ""
        if self.profile.engine in {"elevenlabs", "gradium", "resemble", "chatterbox"}:
            self.profile.fallback_engine = "piper"
        return self.profile.normalized()

    def _save(self, show_message: bool = True) -> bool:
        profile = self._current_profile()
        if profile.engine == "xtts" and profile.xtts_mode == "custom" and not profile.xtts_reference_wav:
            QMessageBox.warning(self, "Référence requise", "Importe d'abord un WAV de référence, ou choisis une voix prédéfinie.")
            return False
        if profile.engine == "elevenlabs":
            if self.eleven_key_edit.text().strip() and not self._apply_elevenlabs_key(show_message=False):
                return False
            if not settings.ELEVENLABS_API_KEY:
                QMessageBox.warning(self, "ElevenLabs", "Colle ta clé API ElevenLabs dans ce panneau, puis actualise et choisis une voix.")
                return False
            if not profile.elevenlabs_voice_id:
                QMessageBox.warning(self, "ElevenLabs", "Actualise la liste puis choisis une voix ElevenLabs.")
                return False
        if profile.engine == "gradium":
            if self.gradium_key_edit.text().strip() and not self._apply_provider_key("gradium", show_message=False): return False
            if not settings.GRADIUM_API_KEY or not profile.gradium_voice_id:
                QMessageBox.warning(self, "Gradium", "Configure la clé Gradium et saisis/choisis un Voice ID."); return False
        if profile.engine == "resemble":
            if self.resemble_key_edit.text().strip() and not self._apply_provider_key("resemble", show_message=False): return False
            if not settings.RESEMBLE_API_KEY or not profile.resemble_voice_uuid:
                QMessageBox.warning(self, "Resemble", "Configure le token Resemble puis actualise et choisis une voix."); return False
        if profile.engine == "chatterbox" and not (settings.CHATTERBOX_ENABLED and settings.CHATTERBOX_ALLOW_MODEL_LOAD):
            QMessageBox.warning(self, "Chatterbox", "Chatterbox reste désactivé tant que CHATTERBOX_ENABLED=1 et CHATTERBOX_ALLOW_MODEL_LOAD=1 ne sont pas explicitement configurés."); return False
        saved = self.store.save(profile)
        self.profile_saved.emit(saved)
        if show_message:
            QMessageBox.information(self, "Voix enregistrée", "Le profil vocal d'AURA a été enregistré.")
        return True

    def _test(self):
        if self._save(show_message=False):
            self.test_requested.emit("Bonjour, je suis AURA. Cette voix te convient-elle ?")
