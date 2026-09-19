"""
event_bus.py
Bus d'evenements central d'AURA, base sur les signaux Qt afin de garantir
un fonctionnement thread-safe entre le noyau, l'IA et l'interface.
"""
from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """Bus d'evenements central. Une seule instance est partagee par toute l'application."""

    # Etat general canonique Runtime v2. Les anciens PROCESSING/EXECUTING
    # restent normalises en ANALYZING/ACTING par runtime.state_manager.
    state_changed = Signal(str)

    # Runtime v2: canal générique de télémétrie UI/IPC. Le payload reste un
    # objet Python local; aucun envoi réseau implicite n'est effectué ici.
    runtime_event = Signal(str, object)
    provider_changed = Signal(str, str)
    operation_started = Signal(str, object)
    operation_finished = Signal(str, object)

    # Nouveau message utilisateur ajoute a la conversation
    user_message = Signal(str)

    # Nouvelle reponse d'AURA disponible
    aura_message = Signal(str)
    # AURA_V123_PERSONAL_RESULT_SIGNAL
    personal_result = Signal(object)

    # Erreur survenue quelque part dans l'application
    error_occurred = Signal(str)

    # Log d'activite (journal d'activite, section 23 du cahier des charges)
    activity_logged = Signal(str)

    # Voice subsystem v0.5. These signals expose state to the UI; they do not
    # constitute authorization to start recording.
    voice_status_changed = Signal(str)
    voice_transcription = Signal(str)


# Instance unique partagee par toute l'application
event_bus = EventBus()
