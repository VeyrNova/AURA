# AURA

**AURA** is a local-first Windows AI assistant designed around a modular runtime, persistent memory, voice interaction, secure desktop actions, connected services, and a Chromium-based product interface.

> Public source repository. Source visibility does **not** grant an open-source license; see [LICENSE](LICENSE).

## Current product line

This repository contains the current AURA source snapshot with the modern runtime architecture, including:

- **Intelligence runtime v3** with provider routing and failover foundations
- **AURA Skills v2.3** for research, weather, navigation, files, productivity, memory, system, voice and developer workflows
- **Persistent memory** and controlled learning components
- **Voice stack** with XTTS / Chatterbox / Piper integration paths
- **Push-to-talk microphone policy** — microphone activation is explicit and button-driven, not always-on
- **Maps / GPS / routing** integrations
- **Windows PC control** guarded by AURA security policy
- **Developer Fabric** and coding-agent integration foundations
- **Chromium UI** with the current 0.7.2.2-rc4.2 application surface
- **FR / EN localization foundations**
- Productivity, files, notifications, browser, contacts, calendar/tasks and media integration modules

## Security and privacy

AURA is designed so that every user supplies their **own provider credentials locally**.

The repository intentionally excludes:

- real API keys and provider tokens
- OAuth tokens, cookies and sessions
- local `.env`
- personal memory databases and conversation history
- private voice samples / reference audio
- user-specific authorized-folder lists
- runtime state, local media indexes and usage counters
- large AI / STT / TTS model binaries

Use [`.env.example`](.env.example) as the public configuration template. Never commit your real `.env`.

See [SECURITY.md](SECURITY.md) for the repository security rules.

## Voice

Voice identity and language are separate settings.

The public source contains the voice-engine logic, while private developer voice material is excluded. Users can configure supported engines and authorized voices locally.

AURA's microphone policy remains **BUTTON ONLY / push-to-talk**.

See [docs/USER_CONFIGURATION.md](docs/USER_CONFIGURATION.md).

## Repository structure

| Area | Purpose |
| --- | --- |
| `core/` | Core orchestration, routing, version and event foundations |
| `runtime/` | Intelligence, provider, automation and integration runtime |
| `skills/` | AURA Skills registry, manifests and handlers |
| `voice/` | Voice engine, microphone, XTTS and fallback backends |
| `memory/` | Memory and relationship/learning components |
| `security/` | Security policy, risk and audit foundations |
| `integrations/` | Connected product integrations |
| `services/` | Shared application services |
| `tools/` | Maps, weather, search and utility tooling |
| `ui/` | Desktop and Chromium user interfaces |
| `tests/` | Invariant, regression and integration tests |
| `docs/` | Architecture, security and subsystem documentation |

## Configuration

AURA supports local provider configuration through environment variables and product configuration surfaces.

The public `.env.example` contains blank entries for supported provider credentials. A configured installation should keep all real credentials outside Git history.

## Models

Large model binaries are **not stored in this Git repository**. Voice, STT and local-model assets must be installed or provisioned separately according to the relevant setup scripts and subsystem requirements.

## Installation status

The repository contains the complete source tree and setup tooling, but the standalone product installer line is **not presented here as a fully certified clean-Windows release**.

For development/source use, review the root setup scripts, requirements files and subsystem documentation before running AURA on a new machine.

## Development

AURA includes a substantial invariant/regression test suite under `tests/` and CI tooling under `ci/`.

The repository also includes Developer Fabric components for supervised development workflows, provider routing, patching and validation.

## Product roadmap

Current repository work is centered on the v2.x product line. The source contains historical milestone files and compatibility surfaces from earlier development phases; these are retained where they still support the running product or regression coverage.

Version metadata consolidation is ongoing across legacy surfaces, so a historical identifier in a subsystem does not necessarily represent the overall product version.

## License

Copyright (c) 2026 Veyr.

AURA is distributed under an **All Rights Reserved** proprietary license. Public availability of the source code does not grant permission to copy, modify, redistribute, sublicense or sell the software.

See [LICENSE](LICENSE) for the full terms.
