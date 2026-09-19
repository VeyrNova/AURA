# AURA Developer Fabric — ADF-E

ADF-E wires a production resilience policy into AURA Fabric Gateway, adds the AURA Terminal Reduction Kernel (TRK), five deterministic provider-free optimizations, and a local-first voice transcription bridge.

## Resilience
Retryable capacity/transport failures use bounded retry/backoff, then same-turn fallback. Non-retryable auth/request failures skip wasted retries and move to the next configured route. Existing AFG health/circuit-breaker signals remain authoritative.

## Terminal Reduction Kernel
AURA implements its own clean-room output reducer. The 90% figure is a potential reduction in terminal-output bytes on noisy commands, not a promise of 90% lower total tokens or cost. Small outputs and compact error traces pass through; signal lines are preserved; secrets matching common assignment patterns are redacted. Raw-mode is always available with `aura_trk.py --raw -- <command>`.

## Provider-free local optimizations
Quota probe, command-prefix detection, session title, next-action suggestion and filepath normalization are deterministic local functions and do not invoke a model/provider.

## Voice
Local Whisper is preferred. NVIDIA NIM is optional. A non-loopback NIM URL requires explicit remote approval before audio can be sent. ADF-E certification never transcribes or uploads audio.

## HTTP
`GET /aura/v1/efficiency`
`GET /aura/v1/voice`

## Certification boundary
No external network, provider call, third-party agent execution, audio upload or model installation occurs in ADF-E certification.
