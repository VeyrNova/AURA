# AURA Developer Fabric — Native AURA Fabric Gateway

## Decision
AURA Developer Fabric no longer depends on Free Claude Code (FCC).
FCC is retained only as an external behavioral benchmark from public documentation.
No FCC source code, package, launcher, configuration or runtime file is required.

## Clean-room rule
The AURA Fabric Gateway (AFG) is designed from first principles around public protocol behavior and AURA requirements.

Forbidden dependencies:
- FCC packages/modules
- `.fcc` runtime/config inspection
- FCC launchers
- code copied or translated from FCC
- binary/runtime dependency on FCC

Allowed interoperability targets:
- documented Anthropic Messages-compatible traffic
- documented OpenAI Responses-compatible traffic
- documented OpenAI Chat Completions-compatible traffic
- local/provider-native adapters written independently

## AURA owns
1. Workspace and repository boundaries
2. Planning and context construction
3. Provider/model registry
4. Capability-aware routing
5. Health, latency and reliability scoring
6. Circuit breaking and bounded failover
7. Local-first/data-boundary policy
8. Cost ceilings and budget policy
9. Patch proposals, tests and diffs
10. Explicit approval before write
11. Transactional backup and rollback
12. Audit receipts and future UI

## Native improvements
AFG is a routing/policy fabric, not just a proxy:
- capability-aware model selection
- local/cloud policy
- reliability/latency history
- automatic unhealthy-route removal
- context/tool/vision/reasoning constraints
- cost ceilings
- ordered fallbacks
- provider-neutral contracts

## FCC-parity capability target, implemented independently
AURA Developer Fabric must provide:
- at least 50 ToS-aware provider integrations in the initial catalog, with dynamic enable/disable state
- an aggregated free-tier observatory; 1.3B tokens/month is a reference target, never a guarantee
- one searchable model catalog shared by 10 coding agents: Claude Code, Codex, Pi, OpenCode, Cline, Hermes, DeepSeek Harness, Grok Build, Muse Code and Aider
- transparent same-turn retry/failover to the next configured model
- AURA Terminal Reduction Kernel targeting up to 90% less low-value terminal-output tokens
- terminal, desktop, VS Code, JetBrains, Codex App, Discord, Telegram and native AURA surfaces
- voice-note input through local Whisper, with optional NVIDIA NIM
- preservation of streaming, tools, reasoning/interleaved-thinking semantics where supported, image input and structured output
- independent compatible-model routes for Fable, Opus, Sonnet and Haiku
- provider ToS metadata, last verification date and automatic disable/removal when an integration is no longer permitted

## Roadmap
ADF-A — Native clean-room foundation
ADF-B — HTTP protocol gateway, streaming, provider adapters, secrets boundary, live health
ADF-C — Repository scanner and Workspace context pack
ADF-D — Planner, patch proposal, tests, diff and transaction engine
ADF-E — Approval, rollback, self-development safety and audit receipts
ADF-F — Native Developer Workspace UI and live acceptance

Then return to canonical AURA product roadmap at v1.3.1.
