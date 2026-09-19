# AURA Developer Fabric — ADF-B

## HTTP Protocol Gateway + Streaming + Model Catalog + Live Health

ADF-B installs the first executable AURA Fabric Gateway server.

### Clean-room compatibility targets

The implementation is AURA-native and is designed from public protocol behavior. It does not import, execute, inspect, or copy FCC.

Local compatibility endpoints:

- `GET /health`
- `GET /ready`
- `GET /v1/models`
- `POST /v1/responses`
- `POST /v1/chat/completions`
- `POST /v1/messages`
- `GET /aura/v1/catalog`
- `GET /aura/v1/health`
- `POST /aura/v1/health/probe`
- `POST /aura/v1/responses`

### Canonical AURA request layer

Client-specific requests are normalized into one internal request contract that preserves:

- text/messages
- system/developer instructions
- tools
- tool choice
- streaming
- reasoning/thinking metadata
- image-bearing content
- model selection
- output-token limits
- temperature
- metadata

The selected provider adapter receives this canonical request. Its response is converted back into the protocol expected by the client.

### Streaming

ADF-B supports Server-Sent Events (SSE) for:

- OpenAI Responses-compatible streams
- OpenAI Chat Completions-compatible streams
- Anthropic Messages-compatible streams
- AURA native streams

### Unified model catalog

`/v1/models` and `/aura/v1/catalog` expose the same `ModelCatalog` authority.
ADF-C will populate it with the 50+ ToS-aware provider registry.

### Resilience

The gateway already contains a first same-turn resilience path:

1. route selection
2. bounded retries per model
3. health recording
4. circuit breaker
5. automatic fallback to the next candidate
6. response returned to the original client without restarting the turn

ADF-E will extend this into the full production outage and token-efficiency layer.

### Security

- loopback bind by default (`127.0.0.1`)
- non-loopback bind denied unless explicitly enabled
- optional bearer token via `AURA_FABRIC_LOCAL_TOKEN`
- request-size limit
- no request bodies, headers, credentials, or secrets logged
- no external provider call during ADF-B certification

### Runtime

Default address:

`http://127.0.0.1:8766`

Launcher:

`python launch_aura_fabric_gateway.py`

ADF-C will add the ToS-aware provider registry and real provider adapters.
