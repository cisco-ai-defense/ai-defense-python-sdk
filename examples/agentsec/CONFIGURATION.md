# agentsec Configuration Reference

Comprehensive reference for every configuration surface of the Cisco AI Defense
agentsec SDK: the `agentsec.yaml` file, the `.env` environment variables, and
the `protect()` Python API.

> **New here?** Start with [README.md](README.md) for concepts, quick start,
> and code examples. Use this document as a lookup reference when you need the
> exact parameter name, type, allowed values, or default for a specific setting.

---

## Table of Contents

- [Configuration Merge Order](#configuration-merge-order)
- [Environment Variable Substitution](#environment-variable-substitution)
- [1. agentsec.yaml Reference](#1-agentsecyaml-reference)
  - [Top-Level Parameters](#top-level-parameters)
  - [gateway_mode](#gateway_mode)
  - [api_mode](#api_mode)
  - [logging](#logging)
- [2. .env Variable Reference](#2-env-variable-reference)
  - [AI Defense API Mode](#ai-defense-api-mode)
  - [LLM Provider Keys and Gateway URLs](#llm-provider-keys-and-gateway-urls)
  - [AWS Bedrock (Global)](#aws-bedrock-global)
  - [AWS Bedrock Per-Gateway](#aws-bedrock-per-gateway)
  - [GCP Vertex AI (Global)](#gcp-vertex-ai-global)
  - [GCP Vertex AI Per-Gateway](#gcp-vertex-ai-per-gateway)
  - [Azure AI Foundry (Deployment)](#azure-ai-foundry-deployment)
  - [MCP Server and Gateway URLs](#mcp-server-and-gateway-urls)
  - [MCP Gateway Auth (Optional)](#mcp-gateway-auth-optional)
- [3. protect() Kwargs Reference](#3-protect-kwargs-reference)
- [4. Appendix: Environment Variable Overrides](#4-appendix-environment-variable-overrides)

---

## Configuration Merge Order

When `protect()` is called, configuration values are resolved using the
following priority (highest wins):

```
protect() kwargs  >  agentsec.yaml  >  hardcoded defaults
```

For nested dicts (`gateway_mode`, `api_mode`), values are **deep-merged** --
individual keys from a higher-priority source override the same key from a
lower-priority source, while unspecified keys are preserved.

---

## Environment Variable Substitution

Inside `agentsec.yaml`, use `${VAR_NAME}` syntax to reference environment
variables. Variables must be set (via `.env` file or the shell environment)
**before** `protect()` is called. When `auto_dotenv=True` (the default),
`protect()` automatically loads the nearest `.env` file via `python-dotenv`.

If a referenced variable is not set, a `ConfigurationError` is raised.

---

## 1. agentsec.yaml Reference

### Top-Level Parameters

| Key | Type | Allowed Values | Default | Description |
| --- | --- | --- | --- | --- |
| `llm_integration_mode` | string | `"api"`, `"gateway"` | `"api"` | How LLM calls are inspected. `"api"` sends a side-channel inspection request; `"gateway"` proxies LLM calls through a gateway. |
| `mcp_integration_mode` | string | `"api"`, `"gateway"` | `"api"` | How MCP tool calls are inspected. Same semantics as `llm_integration_mode`. |
| `pool_max_connections` | int | >= 1 | `100` | Maximum number of simultaneous HTTP connections in the pool used for Cisco AI Defense API calls. |
| `pool_max_keepalive` | int | >= 0 | `20` | Maximum number of idle keep-alive connections retained in the pool. |

---

### `gateway_mode`

Used when `llm_integration_mode` or `mcp_integration_mode` is `"gateway"`.

#### `gateway_mode.llm_mode` / `gateway_mode.mcp_mode`

On/off switches for gateway inspection. When `"on"` (default), traffic is routed through the AI Defense Gateway. When `"off"`, the gateway is bypassed and calls go directly to the LLM/MCP provider with no inspection. Enforcement is handled server-side by the gateway -- there is no local monitor/enforce distinction.

| Key | Type | Allowed Values | Default | Description |
| --- | --- | --- | --- | --- |
| `llm_mode` | string | `"on"`, `"off"` | `"on"` | Controls whether LLM calls are routed through the gateway. |
| `mcp_mode` | string | `"on"`, `"off"` | `"on"` | Controls whether MCP tool calls are routed through the gateway. |

#### `gateway_mode.llm_defaults`

Default settings inherited by **all** LLM gateways unless overridden per-gateway.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `fail_open` | bool | `true` | If `true`, allow the original LLM request to proceed when the gateway is unreachable or returns an error. If `false`, block the request. |
| `timeout` | int | `60` | Timeout in seconds for gateway calls. Gateway proxies to the LLM, so this needs time for model inference. |
| `retry.total` | int | `3` | Maximum number of retry attempts on transient failure. |
| `retry.backoff_factor` | float | `0.5` | Exponential backoff multiplier between retries (seconds). |
| `retry.status_codes` | list of int | `[429, 500, 502, 503, 504]` | HTTP status codes that trigger a retry. |

#### `gateway_mode.mcp_defaults`

Default settings inherited by **all** MCP gateways unless overridden per-gateway.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `fail_open` | bool | `true` | If `true`, allow the original MCP request on gateway failure. |
| `timeout` | int | `10` | Timeout in seconds for MCP gateway calls. |
| `retry.total` | int | `2` | Maximum retry attempts. |
| `retry.backoff_factor` | float | `1.0` | Backoff multiplier between retries. |
| `retry.status_codes` | list of int | `[429, 500, 502, 503, 504]` | HTTP status codes that trigger a retry. |

#### `gateway_mode.llm_gateways.<name>`

Named LLM gateway entries. Each key is a user-chosen name (e.g. `openai-1`,
`bedrock-2`). Set `default: true` on one gateway per provider to make it the
auto-selected gateway for that provider.

| Key | Type | Allowed Values | Default | Description |
| --- | --- | --- | --- | --- |
| `gateway_url` | string | URL | *(required)* | The AI Defense gateway URL to proxy LLM requests through. |
| `gateway_api_key` | string | | `null` | API key sent in the `api-key` header. Required when `auth_mode` is `"api_key"`. Typically a `${VAR}` reference. |
| `auth_mode` | string | `"api_key"`, `"aws_sigv4"`, `"google_adc"` | `"api_key"` | Authentication mode for the gateway. See below for details. |
| `provider` | string | `"openai"`, `"azure_openai"`, `"vertexai"`, `"bedrock"`, `"google_genai"`, `"cohere"`, `"mistral"` | *(none)* | LLM provider this gateway serves. Used for auto-matching patched clients to their default gateway. |
| `default` | bool | | `false` | If `true`, this is the auto-selected gateway for its `provider`. Only one gateway per provider should be marked default. |
| `gateway_model` | string | | `null` | Model name override. When set, the gateway request uses this model name instead of the one from the client. |
| `fail_open` | bool | | *(inherits from `llm_defaults`)* | Per-gateway override. |
| `timeout` | int | | *(inherits from `llm_defaults`)* | Per-gateway override. |
| `retry.total` | int | | *(inherits)* | Per-gateway override. |
| `retry.backoff_factor` | float | | *(inherits)* | Per-gateway override. |
| `retry.status_codes` | list of int | | *(inherits)* | Per-gateway override. |

**AWS SigV4 fields** (only when `auth_mode: aws_sigv4`):

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `aws_region` | string | `null` | AWS region for SigV4 signing (e.g. `us-east-1`). Falls back to default boto3 credential chain. |
| `aws_profile` | string | `null` | Named AWS profile from `~/.aws/credentials`. |
| `aws_access_key_id` | string | `null` | Explicit AWS access key ID (static/temporary credentials). |
| `aws_secret_access_key` | string | `null` | Explicit AWS secret access key. |
| `aws_session_token` | string | `null` | AWS session token (temporary credentials). |
| `aws_role_arn` | string | `null` | IAM role ARN for cross-account assume-role. |

**GCP ADC fields** (only when `auth_mode: google_adc`):

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `gcp_project` | string | `null` | GCP project ID for this gateway. Falls back to `google.auth.default()`. |
| `gcp_location` | string | `null` | GCP region/location (e.g. `us-central1`). |
| `gcp_service_account_key_file` | string | `null` | Path to a service account JSON key file. |
| `gcp_target_service_account` | string | `null` | Service account email for impersonation (cross-project). |

#### `gateway_mode.mcp_gateways.<server_url>`

MCP gateway entries, keyed by the **original MCP server URL** (e.g.
`https://remote.mcpservers.org/fetch/mcp`). The SDK uses this key to match
an outgoing MCP connection to its gateway.

| Key | Type | Allowed Values | Default | Description |
| --- | --- | --- | --- | --- |
| `gateway_url` | string | URL | *(required)* | The AI Defense MCP gateway URL. |
| `gateway_api_key` | string | | `null` | API key for `api_key` auth mode. |
| `auth_mode` | string | `"none"`, `"api_key"`, `"oauth2_client_credentials"` | Inferred: `"api_key"` if `gateway_api_key` is set, otherwise `"none"` | Authentication mode for this MCP gateway. |
| `fail_open` | bool | | *(inherits from `mcp_defaults`)* | Per-gateway override. |
| `timeout` | int | | *(inherits from `mcp_defaults`)* | Per-gateway override. |
| `retry.total` | int | | *(inherits)* | Per-gateway override. |
| `retry.backoff_factor` | float | | *(inherits)* | Per-gateway override. |
| `retry.status_codes` | list of int | | *(inherits)* | Per-gateway override. |

**OAuth2 Client Credentials fields** (only when `auth_mode: oauth2_client_credentials`):

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `oauth2_token_url` | string | `null` | Token endpoint URL (e.g. `https://auth.example.com/oauth/token`). |
| `oauth2_client_id` | string | `null` | OAuth2 client ID. |
| `oauth2_client_secret` | string | `null` | OAuth2 client secret. |
| `oauth2_scopes` | string | `null` | Space-separated scopes (e.g. `"read write"`). |

---

### `api_mode`

Used when `llm_integration_mode` or `mcp_integration_mode` is `"api"`.

#### `api_mode.llm_defaults`

Default settings for LLM API inspection calls.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `fail_open` | bool | `false` | If `true`, allow the LLM request when the inspection API is unreachable. Default is `false` (fail-closed) for LLM API mode. |
| `timeout` | int | `5` | Timeout in seconds for inspection API calls. |
| `retry.total` | int | `2` | Maximum retry attempts. |
| `retry.backoff_factor` | float | `0.5` | Backoff multiplier. |
| `retry.status_codes` | list of int | `[429, 500, 502, 503, 504]` | HTTP status codes that trigger a retry. |

#### `api_mode.mcp_defaults`

Default settings for MCP API inspection calls.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `fail_open` | bool | `true` | If `true`, allow the MCP request when the inspection API is unreachable. |
| `timeout` | int | `5` | Timeout in seconds. |
| `retry.total` | int | `2` | Maximum retry attempts. |
| `retry.backoff_factor` | float | `0.5` | Backoff multiplier. |
| `retry.status_codes` | list of int | `[429, 500, 502, 503, 504]` | HTTP status codes that trigger a retry. |

#### `api_mode.llm`

Configuration for LLM inspection via the API.

| Key | Type | Allowed Values | Default | Description |
| --- | --- | --- | --- | --- |
| `mode` | string | `"off"`, `"monitor"`, `"enforce"` | *(none -- must be set if using API mode)* | Inspection mode (applies only when `llm_integration_mode: api`). `"off"` disables inspection. `"monitor"` inspects but never blocks. `"enforce"` inspects and raises `SecurityPolicyError` on policy violations. For gateway mode, use `gateway_mode.llm_mode` instead. |
| `endpoint` | string | URL | *(none)* | AI Defense inspection API URL. |
| `api_key` | string | | *(none)* | API key for the inspection API. Typically a `${VAR}` reference. |
| `rules` | list | See [Custom Inspection Rules](#custom-inspection-rules) | `null` (all rules) | List of inspection rules to evaluate. When omitted, **all** rules are evaluated (server default). When specified, **only** the listed rules are evaluated. See [Custom Inspection Rules](#custom-inspection-rules) for formats and supported rule names. |
| `entity_types` | list of string | e.g. `["Email Address", "Phone Number"]` | `null` | Global entity type filter applied to all rules that support entity types (PII, PCI, PHI). When a rule also specifies its own `entity_types`, the rule-level value takes precedence. |

#### Custom Inspection Rules

By default, the AI Defense inspection API evaluates **all** rules. You can
restrict evaluation to a subset by specifying `rules` under `api_mode.llm`.
This is useful for reducing false positives or focusing on specific threats.

> **Important**: When `rules` is specified, rules **not** in the list are
> completely skipped -- they will not appear in the inspection response.

**Supported rule names:**

| Rule Name | Description |
| --- | --- |
| `Prompt Injection` | Detects prompt injection and jailbreak attempts |
| `PII` | Detects personally identifiable information (supports `entity_types`) |
| `PCI` | Detects payment card industry data (supports `entity_types`) |
| `PHI` | Detects protected health information (supports `entity_types`) |
| `Code Detection` | Detects code in prompts or responses |
| `Harassment` | Detects harassment content |
| `Hate Speech` | Detects hate speech |
| `Profanity` | Detects profanity |
| `Toxicity` | Detects toxic content |
| `Sexual Content & Exploitation` | Detects sexual content |
| `Social Division & Polarization` | Detects socially divisive content |
| `Violence & Public Safety Threats` | Detects violence and safety threats |

**YAML format** (in `agentsec.yaml`):

```yaml
api_mode:
  llm:
    mode: enforce
    endpoint: ${AI_DEFENSE_API_MODE_LLM_ENDPOINT}
    api_key: ${AI_DEFENSE_API_MODE_LLM_API_KEY}
    rules:
      - rule_name: "PII"
        entity_types: ["Email Address", "Phone Number"]
      - rule_name: "Code Detection"
      - rule_name: "Prompt Injection"
```

**protect() kwargs format** (overrides YAML):

```python
agentsec.protect(
    config="agentsec.yaml",
    api_mode={
        "llm": {
            "rules": [
                {"rule_name": "PII", "entity_types": ["Email Address"]},
                {"rule_name": "Code Detection"},
            ]
        }
    },
)
```

**Simple string format** (rule names only, no entity types):

```python
agentsec.protect(
    api_mode={"llm": {"rules": ["PII", "Code Detection", "Prompt Injection"]}},
)
```

Rule names are normalized: `"prompt_injection"`, `"Prompt Injection"`, and
`"PROMPT_INJECTION"` all resolve to the same rule.

See `1-simple/custom_rules_example.py` for a working example.

#### `api_mode.mcp`

Configuration for MCP inspection via the API.

| Key | Type | Allowed Values | Default | Description |
| --- | --- | --- | --- | --- |
| `mode` | string | `"off"`, `"monitor"`, `"enforce"` | *(none -- must be set if using API mode)* | Inspection mode (applies only when `mcp_integration_mode: api`). Same semantics as `api_mode.llm.mode`. For gateway mode, use `gateway_mode.mcp_mode` instead. |
| `endpoint` | string | URL | *(none -- must be set if using MCP API mode)* | AI Defense inspection API URL for MCP. Must be configured independently; there is no fallback to `api_mode.llm.endpoint`. |
| `api_key` | string | | *(none -- must be set if using MCP API mode)* | API key for MCP inspection. Must be configured independently; there is no fallback to `api_mode.llm.api_key`. |

---

### `logging`

| Key | Type | Allowed Values | Default | Description |
| --- | --- | --- | --- | --- |
| `level` | string | `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"` | `"WARNING"` | Log verbosity level. Can be overridden by the `AGENTSEC_LOG_LEVEL` env var. |
| `format` | string | `"text"`, `"json"` | `"text"` | Log output format. Can be overridden by `AGENTSEC_LOG_FORMAT` env var or `protect(log_format=)`. |
| `file` | string | file path | `null` | Path to a log file. Can be overridden by `AGENTSEC_LOG_FILE` env var or `protect(log_file=)`. |

---

## 2. .env Variable Reference

The `.env` file holds secrets, credentials, and URLs that are referenced from
`agentsec.yaml` via `${VAR_NAME}` substitution. Copy `.env.example` to `.env`
and fill in the values.

### AI Defense API Mode

| Variable | Description | Example Placeholder | Referenced By |
| --- | --- | --- | --- |
| `AI_DEFENSE_API_MODE_LLM_API_KEY` | API key for LLM inspection API | `your-ai-defense-llm-api-key` | `${AI_DEFENSE_API_MODE_LLM_API_KEY}` in `api_mode.llm.api_key` |
| `AI_DEFENSE_API_MODE_MCP_API_KEY` | API key for MCP inspection API | `your-ai-defense-mcp-api-key` | `${AI_DEFENSE_API_MODE_MCP_API_KEY}` in `api_mode.mcp.api_key` |
| `AI_DEFENSE_API_MODE_LLM_ENDPOINT` | LLM inspection API endpoint URL | `https://your-ai-defense-llm-api-endpoint` | `${AI_DEFENSE_API_MODE_LLM_ENDPOINT}` in `api_mode.llm.endpoint` |
| `AI_DEFENSE_API_MODE_MCP_ENDPOINT` | MCP inspection API endpoint URL | `https://your-ai-defense-mcp-api-endpoint` | `${AI_DEFENSE_API_MODE_MCP_ENDPOINT}` in `api_mode.mcp.endpoint` |

### LLM Provider Keys and Gateway URLs

| Variable | Description | Example Placeholder | Referenced By |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | OpenAI API key | `sk-your-openai-api-key` | `${OPENAI_API_KEY}` in `openai-1.gateway_api_key` |
| `OPENAI_1_GATEWAY_URL` | OpenAI gateway URL | `https://your-openai-gateway-url` | `${OPENAI_1_GATEWAY_URL}` in `openai-1.gateway_url` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource endpoint | `https://your-resource.openai.azure.com/` | Used by examples directly |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | `your-azure-openai-key` | `${AZURE_OPENAI_API_KEY}` in `azure-openai-1.gateway_api_key` |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Azure OpenAI deployment name | `gpt-4o` | Used by examples directly |
| `AZURE_OPENAI_API_VERSION` | Azure OpenAI API version | `2024-08-01-preview` | Used by examples directly |
| `AZURE_OPENAI_1_GATEWAY_URL` | Azure OpenAI gateway URL | `https://your-azure-openai-gateway-url` | `${AZURE_OPENAI_1_GATEWAY_URL}` in `azure-openai-1.gateway_url` |
| `COHERE_API_KEY` | Cohere API key | *(empty)* | `${COHERE_API_KEY}` in `cohere-1.gateway_api_key` |
| `COHERE_1_GATEWAY_URL` | Cohere gateway URL | `https://your-cohere-gateway-url` | `${COHERE_1_GATEWAY_URL}` in `cohere-1.gateway_url` |
| `MISTRAL_API_KEY` | Mistral AI API key | *(empty)* | `${MISTRAL_API_KEY}` in `mistral-1.gateway_api_key` |
| `MISTRAL_1_GATEWAY_URL` | Mistral AI gateway URL | `https://your-mistral-gateway-url` | `${MISTRAL_1_GATEWAY_URL}` in `mistral-1.gateway_url` |

### AWS Bedrock (Global)

Used by deploy scripts, boto3 client creation in examples, and agent-framework templates.

| Variable | Description | Example Placeholder | Referenced By |
| --- | --- | --- | --- |
| `AWS_AUTH_METHOD` | AWS authentication method | `profile` | Deploy scripts / examples |
| `AWS_REGION` | AWS region | `us-east-1` | Deploy scripts / examples |
| `AWS_PROFILE` | AWS CLI profile name | `default` | Deploy scripts / examples |

### AWS Bedrock Per-Gateway

Per-gateway AWS credentials for Bedrock gateways in `agentsec.yaml`. Falls back
to the default boto3 credential chain when not set.

| Variable | Description | Example Placeholder | Referenced By |
| --- | --- | --- | --- |
| `BEDROCK_1_AWS_REGION` | AWS region for bedrock-1 | `us-east-1` | `${BEDROCK_1_AWS_REGION}` in `bedrock-1.aws_region` |
| `BEDROCK_1_AWS_PROFILE` | AWS profile for bedrock-1 | `default` | `${BEDROCK_1_AWS_PROFILE}` in `bedrock-1.aws_profile` |
| `BEDROCK_1_GATEWAY_URL` | Gateway URL for bedrock-1 | `https://your-bedrock-1-gateway-url` | `${BEDROCK_1_GATEWAY_URL}` in `bedrock-1.gateway_url` |
| `BEDROCK_2_AWS_REGION` | AWS region for bedrock-2 | `eu-west-1` | `${BEDROCK_2_AWS_REGION}` in `bedrock-2.aws_region` |
| `BEDROCK_2_AWS_PROFILE` | AWS profile for bedrock-2 | `team-b` | `${BEDROCK_2_AWS_PROFILE}` in `bedrock-2.aws_profile` |
| `BEDROCK_2_GATEWAY_URL` | Gateway URL for bedrock-2 | `https://your-bedrock-2-gateway-url` | `${BEDROCK_2_GATEWAY_URL}` in `bedrock-2.gateway_url` |

**Optional -- explicit keys (uncomment in `.env` if using static/temporary credentials):**

| Variable | Description | Referenced By |
| --- | --- | --- |
| `BEDROCK_1_AWS_ACCESS_KEY_ID` | Explicit access key for bedrock-1 | `${BEDROCK_1_AWS_ACCESS_KEY_ID}` in `bedrock-1.aws_access_key_id` |
| `BEDROCK_1_AWS_SECRET_ACCESS_KEY` | Explicit secret key for bedrock-1 | `${BEDROCK_1_AWS_SECRET_ACCESS_KEY}` in `bedrock-1.aws_secret_access_key` |
| `BEDROCK_1_AWS_SESSION_TOKEN` | Session token for bedrock-1 | `${BEDROCK_1_AWS_SESSION_TOKEN}` in `bedrock-1.aws_session_token` |
| `BEDROCK_2_AWS_ACCESS_KEY_ID` | Explicit access key for bedrock-2 | `${BEDROCK_2_AWS_ACCESS_KEY_ID}` in `bedrock-2.aws_access_key_id` |
| `BEDROCK_2_AWS_SECRET_ACCESS_KEY` | Explicit secret key for bedrock-2 | `${BEDROCK_2_AWS_SECRET_ACCESS_KEY}` in `bedrock-2.aws_secret_access_key` |
| `BEDROCK_2_AWS_SESSION_TOKEN` | Session token for bedrock-2 | `${BEDROCK_2_AWS_SESSION_TOKEN}` in `bedrock-2.aws_session_token` |

### GCP Vertex AI (Global)

Used for authenticating to Vertex AI and deploying to Agent Engine / Cloud Run / GKE.

| Variable | Description | Example Placeholder | Referenced By |
| --- | --- | --- | --- |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | `your-gcp-project-id` | Deploy scripts / examples |
| `GOOGLE_CLOUD_LOCATION` | GCP region | `us-central1` | Deploy scripts / examples |
| `GOOGLE_AI_SDK` | Google AI SDK to use: `google_genai` (ChatGoogleGenerativeAI, default) or `vertexai` (ChatVertexAI). Resolved by `agentsec.yaml` via `${GOOGLE_AI_SDK}` | `google_genai` | agentsec.yaml gateway `sdk` field |
| `GOOGLE_AI_SDK_DEPLOYMENT` | SDK passed to deployed containers by deploy scripts. Overrides `GOOGLE_AI_SDK` for deployments | `vertexai` | Deploy scripts |
| `GKE_AUTHORIZED_NETWORKS` | GKE authorized networks (CIDR) | `YOUR_PUBLIC_IP/32` | GKE deployment only |

### GCP Vertex AI Per-Gateway

Per-gateway GCP credentials for Vertex AI gateways. Falls back to
`google.auth.default()` when not set.

| Variable | Description | Example Placeholder | Referenced By |
| --- | --- | --- | --- |
| `VERTEXAI_1_GCP_PROJECT` | GCP project for vertexai-1 | `your-gcp-project-id` | `${VERTEXAI_1_GCP_PROJECT}` in `vertexai-1.gcp_project` |
| `VERTEXAI_1_GCP_LOCATION` | GCP location for vertexai-1 | `us-central1` | `${VERTEXAI_1_GCP_LOCATION}` in `vertexai-1.gcp_location` |
| `VERTEXAI_1_GATEWAY_URL` | Gateway URL for vertexai-1 | `https://your-vertexai-gateway-url` | `${VERTEXAI_1_GATEWAY_URL}` in `vertexai-1.gateway_url` |

**Optional -- explicit service account (uncomment in `.env`):**

| Variable | Description | Referenced By |
| --- | --- | --- |
| `VERTEXAI_1_SA_KEY_FILE` | Path to service account JSON key file | `${VERTEXAI_1_SA_KEY_FILE}` in `vertexai-1.gcp_service_account_key_file` |
| `VERTEXAI_1_TARGET_SA` | SA email for impersonation | `${VERTEXAI_1_TARGET_SA}` in `vertexai-1.gcp_target_service_account` |

### Azure AI Foundry (Deployment)

Used for deploying to Azure AI Foundry (agent-app, functions, container).
These are not referenced from `agentsec.yaml` -- they are used by deploy scripts.

| Variable | Description |
| --- | --- |
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_CLIENT_ID` | Azure service principal client ID |
| `AZURE_CLIENT_SECRET` | Azure service principal client secret |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `AZURE_RESOURCE_GROUP` | Azure resource group name |
| `AZURE_AI_FOUNDRY_PROJECT` | Azure AI Foundry project name |
| `AZURE_AI_FOUNDRY_ENDPOINT` | Azure AI Foundry endpoint URL |
| `AZURE_ACR_NAME` | Azure Container Registry name |
| `AZURE_ACR_LOGIN_SERVER` | Azure Container Registry login server |
| `AZURE_FUNCTION_APP_NAME` | Azure Function App name |
| `AZURE_STORAGE_ACCOUNT` | Azure Storage account name |

### MCP Server and Gateway URLs

| Variable | Description | Example Placeholder | Referenced By |
| --- | --- | --- | --- |
| `MCP_SERVER_URL` | MCP server URL (for examples) | `https://remote.mcpservers.org/fetch/mcp` | Used by examples directly |
| `MCP_FETCH_GATEWAY_URL` | Gateway URL for the fetch MCP server | `https://your-mcp-fetch-gateway-url` | `${MCP_FETCH_GATEWAY_URL}` in `mcp_gateways` |
| `MCP_TIME_GATEWAY_URL` | Gateway URL for the time MCP server | `https://your-mcp-time-gateway-url` | `${MCP_TIME_GATEWAY_URL}` in `mcp_gateways` |

### MCP Gateway Auth (Optional)

Uncomment in `.env` when `agentsec.yaml` MCP gateway entries need authentication.

| Variable | Description | Referenced By |
| --- | --- | --- |
| `MCP_GATEWAY_API_KEY` | API key for MCP gateway with `auth_mode: api_key` | `${MCP_GATEWAY_API_KEY}` in `mcp_gateways.*.gateway_api_key` |
| `MCP_OAUTH_CLIENT_ID` | OAuth2 client ID for `auth_mode: oauth2_client_credentials` | `${MCP_OAUTH_CLIENT_ID}` in `mcp_gateways.*.oauth2_client_id` |
| `MCP_OAUTH_CLIENT_SECRET` | OAuth2 client secret | `${MCP_OAUTH_CLIENT_SECRET}` in `mcp_gateways.*.oauth2_client_secret` |

---

## 3. protect() Kwargs Reference

```python
from aidefense.runtime import agentsec

agentsec.protect(
    patch_clients=True,
    *,
    auto_dotenv=True,
    config=None,
    llm_integration_mode=None,
    mcp_integration_mode=None,
    gateway_mode=None,
    api_mode=None,
    pool_max_connections=None,
    pool_max_keepalive=None,
    custom_logger=None,
    log_file=None,
    log_format=None,
)
```

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `patch_clients` | `bool` | `True` | Whether to auto-patch LLM client libraries (OpenAI, Bedrock, Vertex AI, Cohere, Mistral, LiteLLM, MCP). Set to `False` to manage patching manually. |
| `auto_dotenv` | `bool` | `True` | Automatically load the nearest `.env` file via `python-dotenv` before parsing the YAML config. Disable if you manage env vars yourself. |
| `config` | `str` | `None` | Path to an `agentsec.yaml` configuration file. If `None`, only kwargs and hardcoded defaults are used. |
| `llm_integration_mode` | `str` | `None` | `"api"` or `"gateway"`. Overrides the YAML value. When `None`, the YAML value is used (or default `"api"`). |
| `mcp_integration_mode` | `str` | `None` | `"api"` or `"gateway"`. Overrides the YAML value. When `None`, the YAML value is used (or default `"api"`). |
| `gateway_mode` | `dict` | `None` | Dict matching the `gateway_mode` YAML section. Deep-merged over the YAML value. |
| `api_mode` | `dict` | `None` | Dict matching the `api_mode` YAML section. Deep-merged over the YAML value. |
| `pool_max_connections` | `int` | `None` | Maximum number of HTTP connections in the pool. Must be >= 1. When `None`, the YAML value is used (or built-in default `100`). |
| `pool_max_keepalive` | `int` | `None` | Maximum number of idle keep-alive connections in the pool. Must be >= 0. When `None`, the YAML value is used (or built-in default `20`). |
| `custom_logger` | `logging.Logger` | `None` | Provide your own Python `logging.Logger` instance instead of the built-in agentsec logger. |
| `log_file` | `str` | `None` | Path to a file where log output is written. Overrides `logging.file` from YAML. |
| `log_format` | `str` | `None` | `"text"` or `"json"`. Overrides `logging.format` from YAML. |

**Notes:**

- `protect()` is **idempotent** -- calling it multiple times has no effect after the first successful call.
- It is recommended to call `protect()` early in your application, ideally before creating LLM clients. However, `wrapt`-based patching works at the class level, so import order is not strictly required for standard usage.

---

## 4. Appendix: Environment Variable Overrides

### Integration Mode Overrides

The example scripts pass these environment variables to `protect()` kwargs,
allowing you to switch between API and Gateway mode at runtime without editing
the YAML file:

| Environment Variable | Overrides | Allowed Values | Default |
| --- | --- | --- | --- |
| `AGENTSEC_LLM_INTEGRATION_MODE` | `llm_integration_mode` in YAML | `api`, `gateway` | *(YAML value or `api`)* |
| `AGENTSEC_MCP_INTEGRATION_MODE` | `mcp_integration_mode` in YAML | `api`, `gateway` | *(YAML value or `api`)* |

> **Note**: These are not built-in SDK overrides — the example scripts read
> them explicitly (e.g. `os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api")`)
> and pass the value to `protect(llm_integration_mode=...)`. Adopt the same
> pattern in your own code if you want runtime-switchable integration modes.

### Logging Overrides

These environment variables override logging settings regardless of YAML or
`protect()` kwargs:

| Environment Variable | Overrides | Allowed Values | Default |
| --- | --- | --- | --- |
| `AGENTSEC_LOG_LEVEL` | `logging.level` in YAML | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `WARNING` |
| `AGENTSEC_LOG_FORMAT` | `logging.format` in YAML | `text`, `json` | `text` |
| `AGENTSEC_LOG_FILE` | `logging.file` in YAML / `protect(log_file=)` | file path | *(none)* |

The full precedence for logging settings is:

```
AGENTSEC_LOG_* env var  >  protect() kwarg  >  agentsec.yaml logging section  >  hardcoded default
```

