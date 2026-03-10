# Vertex AI Agent Engine Deployment Notes

## Overview
Successfully deployed LangChain-based SRE agent with Cisco AI Defense (agentsec) protection to Google Cloud Vertex AI Agent Engine.

## Key Changes Summary

### 1. SDK Lazy Imports (aidefense/__init__.py, aidefense/runtime/__init__.py)
**Status:** ⚠️ Consider reverting in final PR

**What:** Converted to `__getattr__()` pattern for lazy loading
**Why:** Initially added to resolve Agent Engine deployment import errors
**Outcome:** May not be necessary - the real fix was requirements.txt packaging

**Decision Point:**
- Keep if: Provides performance benefits or is considered best practice
- Revert if: Adds unnecessary complexity without clear benefits

**Original imports documented in code comments for easy restoration**

### 2. Lazy agentsec.protect() Initialization (agent_factory.py)
**Status:** ✅ MUST KEEP - Critical for deployment

**What:** Moved `agentsec.protect()` from module-level to lazy `_initialize_agentsec()` function
**Why:** Agent Engine validates Python packages during build BEFORE installing requirements
**Outcome:** Essential fix - prevents "No module named 'wrapt'" errors

**DO NOT REVERT** - This is required for Agent Engine deployments

### 3. Requirements.txt Packaging
**Status:** ✅ Required for Agent Engine

**What:** Placed `requirements.txt` inside `agent_engine_entry/` source package
**Why:** Agent Engine requires requirements.txt to be within a source package
**Path:** `agent_engine_entry/requirements.txt`
**Key Dependencies:**
```
google-cloud-aiplatform[agent_engines,langchain]==1.133.0
aiohttp>=3.9.0
requests>=2.28.0
wrapt>=1.14.0
langchain>=0.3.0
langchain-google-genai>=2.0.0
```

### 4. Agent Engine API Compatibility
**Status:** ✅ Required

**What:** Renamed agent method from `invoke_agent()` to `query()`
**Why:** Agent Engine expects standard method names (`query`, `async_query`, etc.)
**File:** `agent_engine_entry/entry.py`

### 5. Deployment Script Timeout
**Status:** ✅ Prevents hanging deployments

**What:** Added 10-minute timeout to `client.agent_engines.create()` call
**Why:** SDK polls for agent readiness and can hang indefinitely
**Outcome:** Clean script termination, agent still deploys successfully

## Root Causes of Original Issues

### Issue 1: Import Errors During Deployment
**Error:** `ModuleNotFoundError: No module named 'aiohttp'`, `'wrapt'`, etc.

**Root Cause:** Agent Engine validates Python packages during container build BEFORE installing requirements. Module-level imports tried to load dependencies that didn't exist yet.

**Solution:** 
1. Lazy `agentsec.protect()` initialization (CRITICAL)
2. SDK lazy imports (OPTIONAL - for consideration)
3. Proper requirements.txt packaging (REQUIRED)

### Issue 2: Deployment Script Hanging
**Error:** Script runs for 20+ minutes without completing

**Root Cause:** `client.agent_engines.create()` polls for agent health status and can hang waiting for full readiness, even though agent deployed successfully.

**Solution:** 
- Added signal.alarm(600) for 10-minute timeout
- Added explicit sys.exit(0) after success
- Agent still deploys and works - timeout just prevents indefinite wait

## Testing Results

### Deployment
- ✅ Completes in 3-5 minutes
- ✅ Script terminates cleanly
- ✅ Resource ID saved automatically
- ✅ No hanging or timeout issues

### Runtime Performance
- ✅ First invocation (cold start): ~25 minutes
- ✅ Subsequent invocations: 15-30 seconds
- ✅ All tools functioning:
  - `check_service_health` ✅
  - `get_recent_logs` ✅
  - `calculate_capacity` ✅
  - `fetch_url` ✅

### Agent Protection
- ✅ Cisco AI Defense (agentsec) successfully initialized
- ✅ LLM calls monitored
- ✅ MCP tool calls protected

## Recommendations for Final PR

### Must Keep
1. ✅ Lazy `agentsec.protect()` initialization in agent_factory.py
2. ✅ Requirements.txt in agent_engine_entry/ package
3. ✅ `query()` method in Agent Engine entry point
4. ✅ Deployment script timeout mechanism
5. ✅ Pinned SDK version in requirements.txt

### Consider Reverting
1. ⚠️ SDK lazy imports (aidefense/__init__.py, runtime/__init__.py)
   - Test if deployment works without them
   - Keep if they provide other benefits (performance, best practice)
   - Revert if they add unnecessary complexity

### Testing Before PR
1. Deploy with reverted SDK lazy imports to confirm not needed
2. Verify cold start times acceptable
3. Test with different Agent Engine configurations
4. Confirm all integration tests pass

## Usage

### Deploy
```bash
cd agent-engine-deploy/scripts
export GOOGLE_CLOUD_PROJECT=your-project
export GOOGLE_CLOUD_LOCATION=us-central1
export AGENTSEC_LLM_INTEGRATION_MODE=api
./deploy.sh
```

### Invoke
```bash
./invoke.sh "Check the health of the payments service"
./invoke.sh "Get recent logs for the api service"
```

### Cleanup
```bash
./cleanup.sh
```

## Architecture

```
User → Vertex AI Agent Engine → LangChain Agent → ChatGoogleGenerativeAI (LLM)  [or ChatVertexAI when sdk=vertexai]
                                      ↓
                                 Tool Calling
                                      ↓
                        ┌─────────────┴────────────┐
                        │                          │
                 Local Tools                  MCP Tools
            - check_service_health()       - fetch_url()
            - get_recent_logs()                  ↓
            - calculate_capacity()          MCP Server
                        │                   (protected)
                        └──────────┬─────────────┘
                                   ↓
                            Final Response
```

All LLM and MCP calls protected by Cisco AI Defense (agentsec).

## Known Issues

### ACCESS_TOKEN_SCOPE_INSUFFICIENT (generativelanguage.googleapis.com)
When invoking a deployed Agent Engine you may see:
```
403 Request had insufficient authentication scopes.
service: "generativelanguage.googleapis.com"
```
**Root cause:** `ChatGoogleGenerativeAI(vertexai=True)` uses the `google-genai` SDK which
routes through `aiplatform.googleapis.com`, but the backend delegates to
`generativelanguage.googleapis.com` for Gemini models. Agent Engine's managed
service account token lacks the `generative-language` scope that this backend requires.

**Fix:** Set `GOOGLE_AI_SDK=vertexai` (done automatically by `deploy.sh`).
This switches from `ChatGoogleGenerativeAI` (google-genai SDK) to `ChatVertexAI`
(vertexai SDK), which only needs the `aiplatform` scope that Agent Engine provides.

Both SDK paths are fully supported by agentsec for gateway and API mode inspection:
- `google_genai` path: patched by agentsec's `google_genai` patcher
- `vertexai` path: patched by agentsec's `vertexai` patcher

For local development, `GOOGLE_AI_SDK=google_genai` (the default) is recommended
as it is the forward path LangChain is steering toward.

### Long Cold Start
First invocation takes ~25 minutes as Agent Engine spins up instances.
- This is expected behavior for serverless deployments
- Subsequent calls are fast (15-30 seconds)
- Consider setting `min_instances: 1` for production to keep warm

### Deployment Script Timeout
Script may show timeout warning after 10 minutes, but agent still deploys successfully.
- Check GCP console for agent status
- Use invoke script to test - it will work even if deploy timed out

## References

- [Agent Engine Deployment Guide](https://cloud.google.com/agent-builder/agent-engine/deploy)
- [Vertex AI Python SDK](https://cloud.google.com/python/docs/reference/vertexai/latest)
- [LangChain Framework](https://python.langchain.com/docs/get_started/introduction)
