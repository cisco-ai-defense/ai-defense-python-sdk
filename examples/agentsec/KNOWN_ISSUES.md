# Known Issues

## MCP StreamableHTTP: 405 on GET Stream Reconnect (Mitigated)

**Status:** Mitigated in agentsec (graceful handling added)
**Affects:** MCP StreamableHTTP transport when connecting to servers that do not support GET stream reconnection
**MCP Servers:** `remote.mcpservers.org`, AI Defense MCP gateway
**Impact:** None — tool calls succeed; agentsec now suppresses noisy retries

### Summary

When the MCP client uses StreamableHTTP transport, it maintains a GET connection for
server-sent events (SSE). If that connection disconnects, the client attempts to
reconnect. Some MCP servers (including `remote.mcpservers.org` and the AI Defense
gateway) return **405 Method Not Allowed** on GET reconnection attempts — they only
accept the initial GET stream per session.

### Previous Behavior

- Log noise: `GET stream error: Client error '405 Method Not Allowed'`
- `GET stream disconnected, reconnecting in 1000ms...`
- `GET stream max reconnection attempts (2) exceeded`
- Tool calls still succeeded (responses come via POST path)

### Mitigation (agentsec v1.x+)

The agentsec MCP patcher now detects 405 on GET stream reconnection and exits
gracefully without retrying, logging only at DEBUG. No functional impact.

## AI Defense Gateway: Multi-Turn Vertex AI Conversations Return 500

**Status:** Open (server-side bug in AI Defense Gateway)
**Affects:** Agent frameworks using Vertex AI in gateway mode (Strands, LangGraph, LangChain, AutoGen)
**Does NOT affect:** CrewAI (single-turn flow), API mode, OpenAI provider, Azure provider, Bedrock provider

### Summary

The AI Defense Gateway returns HTTP 500 Internal Server Error when processing
**any** multi-turn Vertex AI conversation, including plain text-only exchanges
with no function calls. Single-turn requests work correctly.

### Affected Endpoint

```
POST https://gateway.preview.aidefense.aiteam.cisco.com/{org_id}/connections/{connection_id}/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent
```

Also affects the `streamGenerateContent` variant.

### Impact

| Scenario | Result |
|---|---|
| Single-turn user message | 200 OK |
| Multi-turn text-only conversation (user -> model -> user) | **500 Internal Server Error** |
| Multi-turn with function call/response history | **500 Internal Server Error** |

This means any agent framework that performs tool use (which requires multi-turn
conversations) cannot complete successfully through the Vertex AI gateway. The
first LLM call (single-turn) succeeds, but the follow-up call (multi-turn with
conversation history) fails.

### Reproduction

**Prerequisites:**
- A valid GCP auth token: `API_TOKEN=$(gcloud auth print-access-token)`
- A configured Vertex AI gateway connection in AI Defense

**Test 1: Single-turn (PASSES)**
```bash
curl -s -w "\nHTTP_CODE:%{http_code}" \
  'https://gateway.preview.aidefense.aiteam.cisco.com/{org_id}/connections/{connection_id}/v1/projects/{project}/locations/{location}/publishers/google/models/gemini-2.5-flash-lite:generateContent' \
  --header "Authorization: Bearer $API_TOKEN" \
  --header 'Content-Type: application/json' \
  --data '{
    "contents": [
      {"role": "user", "parts": [{"text": "What is 2+2?"}]}
    ]
  }'
```
Result: **200 OK** with valid response.

**Test 2: Multi-turn text-only (FAILS)**
```bash
curl -s -w "\nHTTP_CODE:%{http_code}" \
  'https://gateway.preview.aidefense.aiteam.cisco.com/{org_id}/connections/{connection_id}/v1/projects/{project}/locations/{location}/publishers/google/models/gemini-2.5-flash-lite:generateContent' \
  --header "Authorization: Bearer $API_TOKEN" \
  --header 'Content-Type: application/json' \
  --data '{
    "contents": [
      {"role": "user", "parts": [{"text": "Hi, what is 2+2?"}]},
      {"role": "model", "parts": [{"text": "2+2 = 4"}]},
      {"role": "user", "parts": [{"text": "And what is 3+3?"}]}
    ]
  }'
```
Result: **500 Internal Server Error**.

**Test 3: Same multi-turn payload direct to Vertex AI (PASSES)**
```bash
curl -s -w "\nHTTP_CODE:%{http_code}" \
  'https://us-central1-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/gemini-2.5-flash-lite:generateContent' \
  --header "Authorization: Bearer $API_TOKEN" \
  --header 'Content-Type: application/json' \
  --data '{
    "contents": [
      {"role": "user", "parts": [{"text": "Hi, what is 2+2?"}]},
      {"role": "model", "parts": [{"text": "2+2 = 4"}]},
      {"role": "user", "parts": [{"text": "And what is 3+3?"}]}
    ]
  }'
```
Result: **200 OK** with valid response ("3+3 = 6").

### Root Cause

The gateway fails when the `contents` array contains more than one message.
The same payload succeeds when sent directly to the Vertex AI API, confirming
the issue is in the gateway's request processing, not in the payload format.

### Integration Test Impact

The following integration tests fail due to this issue:

**Agent Frameworks (`2-agent-frameworks`):**

| Framework | Test | Failure |
|---|---|---|
| Strands Agent | vertex-gateway | 500 on 2nd LLM call |
| LangGraph Agent | vertex-gateway | 500 on 2nd LLM call |
| LangChain Agent | vertex-gateway | 500 on 2nd LLM call |
| AutoGen Agent | vertex-gateway | 500 on 2nd LLM call |

**Note:** CrewAI vertex-gateway passes because CrewAI's conversation flow
does not trigger the multi-turn condition that causes the gateway 500.

**Agent Runtimes (`3-agent-runtimes/gcp-vertex-ai-agent-engine`):**

| Deploy Mode | Test | Failure |
|---|---|---|
| Agent Engine | gateway | 500 on 2nd LLM call (multi-turn with functionCall/functionResponse) |
| Cloud Run | gateway | 500 on 2nd LLM call (multi-turn with functionCall/functionResponse) |
| GKE | gateway | 500 on 2nd LLM call (multi-turn with functionCall/functionResponse) |

**Note:** All GCP Vertex AI API-mode tests pass (agent-engine, cloud-run, gke).
MCP-only gateway tests also pass (MCP uses a separate gateway path).

All other provider/mode combinations pass. All Vertex AI API-mode tests pass.

### Workaround

Use `api` integration mode instead of `gateway` for Vertex AI until this is
fixed:

```yaml
# In agentsec.yaml
llm_integration_mode: api
```

Or when using the SDK directly:

```python
agentsec.protect(config="agentsec.yaml", llm_integration_mode="api")
```

### SDK Mitigations (as of Issue #4 fix)

The SDK cannot fix this gateway bug. However, the following mitigations were added:

1. **Retry on 500**: Gateway HTTP calls now honor `gateway_mode.llm_defaults.retry`
   (total: 3, backoff_factor: 0.5, status_codes: [429, 500, 502, 503, 504]).
   Transient 500s may succeed on retry (though this bug is deterministic).

2. **Improved error logging**: When a 500 occurs on a multi-turn request, the SDK
   logs a clear message pointing to this KNOWN_ISSUES.md and the workaround.
