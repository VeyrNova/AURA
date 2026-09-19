# Etat actuel : AURA v0.5 — Voice Foundation

AURA v0.5 conserve les fondations Security + Consciousness et ajoute une couche vocale locale optionnelle.

## Composants actifs

- SecurityPolicyEngine déterministe.
- AuraIdentity, PersonalityEngine, SelfModel et ConsciousnessContextBuilder.
- Notes, tâches et rappels SQLite.
- Chat texte avec Ollama local.
- VoiceEngine optionnel : push-to-talk, faster-whisper local, Piper TTS local.

## Documentation v0.5

- `voice_v05.md` : architecture vocale.
- `../MANUAL_TEST_PLAN_v0.5.md` : batterie de tests Windows.
- `../BUG_REPORT_TEMPLATE_v0.5.md` : format de retour de bugs.
- `../UPGRADE_v0.5.md` : mise à niveau depuis v0.4.2.

La mémoire persistante, l'accès Internet général, le wake word et le contrôle système ne font pas encore partie de cette version.
