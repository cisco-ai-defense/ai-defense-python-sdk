# AWS AgentCore Examples with agentsec Protection

This example demonstrates how to protect AWS Bedrock AgentCore agents with **Cisco AI Defense** via the `agentsec` SDK.

## Features

- **Three deployment modes**: Direct code deploy, Container deploy, Lambda deploy
- **Full protection**: Both request AND response inspection by AI Defense
- **API mode or Gateway mode**: Inspect via AI Defense API or route through AI Defense Gateway
- **Strands Agent**: Uses the Strands framework with demo SRE tools
- **Poetry-based**: All examples use Poetry for dependency management
- **Shared configuration**: Uses the shared `examples/.env` file for AI Defense credentials

## Deployment Modes Comparison

| Mode | How it works | Protection Location | Request | Response |
|------|--------------|---------------------|---------|----------|
| **Direct Deploy** | Agent runs in AgentCore, client calls `InvokeAgentRuntime` via boto3 SDK | Client-side (patches `InvokeAgentRuntime`) | ✅ | ✅ |
| **Container Deploy** | Agent runs in Docker container on AgentCore | Server-side (patches Bedrock calls in container) | ✅ | ✅ |
| **Lambda Deploy** | Standard Lambda function using Bedrock directly | Server-side (patches Bedrock calls in Lambda) | ✅ | ✅ |

All three modes support **both request AND response inspection** via AI Defense.

> **Note**: Direct Deploy uses the boto3 SDK directly (not the AgentCore CLI) to ensure full response inspection. The CLI bypasses the patched client path for responses.

## Directory Structure

```
amazon-bedrock-agentcore/
├── pyproject.toml            # Poetry configuration
├── README.md                 # This file
├── _shared/                  # Shared code across all deploy modes
│   ├── __init__.py
│   ├── agent_factory.py      # Agent creation with explicit agentsec config
│   └── tools.py              # Demo tools (add, check_service_health, summarize_log)
├── direct-deploy/            # Direct code deployment
│   ├── agentcore_app.py
│   ├── requirements.txt
│   ├── test_with_protection.py  # Client-side protection test
│   └── scripts/
│       ├── deploy.sh
│       └── invoke.sh
├── container-deploy/         # Docker container deployment
│   ├── agentcore_app.py
│   ├── Dockerfile
│   ├── dockerignore
│   ├── requirements.txt
│   └── scripts/
│       ├── deploy.sh
│       └── invoke.sh
├── lambda-deploy/            # AWS Lambda deployment
│   ├── lambda_handler.py
│   ├── lambda_trust_policy.json
│   ├── requirements.txt
│   └── scripts/
│       ├── deploy.sh
│       └── invoke.sh
└── tests/                    # Test suite
    ├── unit/
    │   └── test_agentcore_example.py  # 44 unit tests
    └── integration/
        ├── test-all-modes.sh  # Integration test runner
        └── logs/              # Test output logs
```

## Prerequisites

1. **AWS CLI** configured with appropriate credentials:
   ```bash
   aws configure
   # or
   aws sso login
   ```

2. **Poetry** installed:
   ```bash
   pip install poetry
   ```

3. **Docker** (for container deploy mode)

4. **ECR Repository** (for container deploy mode):
   ```bash
   aws ecr create-repository --repository-name bedrock-agentcore-my_agent
   ```

## Quick Start

### 1. Install Dependencies

```bash
cd examples/3-agent-runtimes/amazon-bedrock-agentcore
poetry install
```

### 2. Configure Environment

The AgentCore examples use the shared `examples/.env` file (same as other examples in the repository). Make sure it contains your AI Defense credentials:

```bash
# Edit the shared .env file (from the agentcore directory)
vim ../../.env

# Or from the repository root
vim examples/.env
```

**Required environment variables for agentsec:**

| Variable | Description | Example |
|----------|-------------|---------|
| `AI_DEFENSE_API_MODE_LLM_ENDPOINT` | AI Defense API endpoint | `https://preview.api.inspect.aidefense.aiteam.cisco.com/api` |
| `AI_DEFENSE_API_MODE_LLM_API_KEY` | AI Defense API key | `your-api-key` |
| `AGENTSEC_LLM_INTEGRATION_MODE` | Integration mode | `api` or `gateway` |

**Optional AWS-specific variables:**

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_REGION` | AWS region | `us-west-2` |
| `BEDROCK_MODEL_ID` | Bedrock model ID | `anthropic.claude-3-sonnet-20240229-v1:0` |
| `ECR_URI` | ECR repository URI (container deploy) | - |
| `FUNCTION_NAME` | Lambda function name | `agentcore-sre-lambda` |

### 3. Run an Example

#### Direct Code Deploy
```bash
# Deploy
./direct-deploy/scripts/deploy.sh

# Invoke
./direct-deploy/scripts/invoke.sh "Check payments health"
```

#### Container Deploy
```bash
# Update ECR_URI in .env first
./container-deploy/scripts/deploy.sh
./container-deploy/scripts/invoke.sh "Check payments health"
```

#### Lambda Deploy
```bash
./lambda-deploy/scripts/deploy.sh
./lambda-deploy/scripts/invoke.sh "Check payments health"
```

## agentsec Configuration

The `agentsec.protect()` call is configured in `_shared/agent_factory.py` with explicit URLs for both LLM and MCP:

```python
import agentsec

agentsec.protect(
    # Integration mode: "api" (inspection) or "gateway" (proxy)
    llm_integration_mode=os.getenv("AGENTSEC_LLM_INTEGRATION_MODE", "api"),
    mcp_integration_mode=os.getenv("AGENTSEC_MCP_INTEGRATION_MODE", "api"),
    
    # API Mode Configuration
    api_mode_llm=os.getenv("AGENTSEC_API_MODE_LLM", "on_monitor"),
    api_mode_llm_endpoint=os.getenv("AI_DEFENSE_API_MODE_LLM_ENDPOINT"),
    api_mode_llm_api_key=os.getenv("AI_DEFENSE_API_MODE_LLM_API_KEY"),
    
    # Gateway Mode Configuration
    providers={
        "bedrock": {
            "gateway_url": os.getenv("AGENTSEC_BEDROCK_GATEWAY_URL"),
            "gateway_api_key": os.getenv("AGENTSEC_BEDROCK_GATEWAY_API_KEY"),
        },
        "agentcore": {
            "gateway_url": os.getenv("AGENTSEC_AGENTCORE_GATEWAY_URL"),
            # No API key - uses AWS Sig V4 authentication
        },
    },
    
    auto_dotenv=False,  # We load .env manually
)
```

## Environment Variables Reference

All environment variables are loaded from the shared `examples/.env` file.

### agentsec Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENTSEC_LLM_INTEGRATION_MODE` | Integration mode: `api` or `gateway` | `api` |
| `AGENTSEC_MCP_INTEGRATION_MODE` | MCP integration mode: `api` or `gateway` | `api` |

#### API Mode Variables (when `AGENTSEC_LLM_INTEGRATION_MODE=api`)

| Variable | Description | Required |
|----------|-------------|----------|
| `AI_DEFENSE_API_MODE_LLM_ENDPOINT` | AI Defense API endpoint | Yes |
| `AI_DEFENSE_API_MODE_LLM_API_KEY` | AI Defense API key | Yes |
| `AGENTSEC_API_MODE_LLM` | Mode: `off`, `on_monitor`, `on_enforce` | No (default: `on_monitor`) |
| `AGENTSEC_API_MODE_FAIL_OPEN_LLM` | Allow requests if API unavailable | No (default: `true`) |

#### Gateway Mode Variables (when `AGENTSEC_LLM_INTEGRATION_MODE=gateway`)

| Variable | Description | Required |
|----------|-------------|----------|
| `AGENTSEC_BEDROCK_GATEWAY_URL` | AI Defense Gateway URL for Bedrock | Yes |
| `AGENTSEC_BEDROCK_GATEWAY_API_KEY` | Gateway API key for Bedrock | Yes |
| `AGENTSEC_AGENTCORE_GATEWAY_URL` | AI Defense Gateway URL for AgentCore | Yes |
| `AGENTSEC_MCP_GATEWAY_URL` | AI Defense Gateway URL for MCP | No |

### AWS Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_REGION` | AWS region | `us-west-2` |
| `BEDROCK_MODEL_ID` | Bedrock model to use | `anthropic.claude-3-sonnet-20240229-v1:0` |
| `ECR_URI` | ECR repository URI (container deploy) | - |
| `FUNCTION_NAME` | Lambda function name | `agentcore-sre-lambda` |
| `ROLE_NAME` | Lambda IAM role name | `agentcore-lambda-role` |

## How agentsec Protection Works

### Protection by Deployment Mode

**Direct Code Deploy:**
- Protection happens **client-side** when calling `InvokeAgentRuntime` via boto3 SDK
- agentsec patches the boto3 `bedrock-agentcore` client
- **Both request AND response are inspected** (uses boto3 SDK, not CLI)
- Best for testing and development
- Note: Uses boto3 SDK directly to ensure full protection (CLI doesn't support response inspection)

**Container Deploy:**
- Protection happens **server-side** inside the container
- agentsec patches Bedrock calls made by the Strands agent
- Each LLM call (including tool use) is inspected
- Production-ready deployment

**Lambda Deploy:**
- Protection happens **server-side** inside the Lambda function
- agentsec patches Bedrock calls made by the Strands agent
- Note: Uses streaming (`ConverseStream`), response inspection deferred
- Serverless deployment option

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Application                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ agentsec.protect()                                   │   │
│  │ - Patches botocore._make_api_call                    │   │
│  │ - Intercepts InvokeAgentRuntime calls                │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ AI Defense Inspection                                │   │
│  │ - Inspects request payload (user prompt)             │   │
│  │ - Checks for PII, prompt injection, etc.             │   │
│  │ - Returns Allow/Block decision                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ boto3 bedrock-agentcore client                       │   │
│  │ - InvokeAgentRuntime(agentRuntimeArn, payload)       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    AWS AgentCore Runtime                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Your Agent Code (agentcore_app.py)                   │   │
│  │ - Strands Agent with tools                           │   │
│  │ - Calls Bedrock LLM                                  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Protection Flow

1. Client calls `agentsec.protect()` before importing boto3
2. This patches `botocore.client.BaseClient._make_api_call` to intercept AgentCore calls
3. When `InvokeAgentRuntime` is called:
   
   **Request Inspection:**
   - agentsec extracts the user prompt from the payload
   - Sends it to AI Defense API for inspection
   - AI Defense checks for PII, prompt injection, jailbreak, etc.
   - Returns Allow/Block decision
   
   **Response Inspection:**
   - After the call completes, agentsec extracts the assistant response
   - Sends both request + response to AI Defense for inspection
   - Checks for sensitive data leakage, harmful content, etc.
   - Returns Allow/Block decision

4. If allowed, the response is returned to the caller
5. If blocked (in enforce mode), a `SecurityPolicyError` is raised

## Demo Tools

The agent includes three demo tools:

| Tool | Description |
|------|-------------|
| `add(a, b)` | Add two numbers |
| `check_service_health(service)` | Simulate checking service health |
| `summarize_log(text)` | Simulate log summarization |

## Troubleshooting

### "agentcore: command not found"
```bash
pip install bedrock-agentcore-starter-toolkit
```

### "ModuleNotFoundError: No module named '_shared'"
Make sure you're running from the `amazon-bedrock-agentcore/` directory:
```bash
cd examples/3-agent-runtimes/amazon-bedrock-agentcore
```

### Lambda timeout
Increase the timeout in `lambda-deploy/scripts/deploy.sh` (default: 60s)

### ECR authentication
```bash
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin <your-account-id>.dkr.ecr.us-west-2.amazonaws.com
```

### .env not found
Make sure you have a `.env` file in the `examples/` directory:
```bash
# From the repository root
cp examples/.env.example examples/.env
# Edit with your credentials
vim examples/.env
```

## Testing

### Unit Tests

Run the example unit tests (44 tests) from the repository root:

```bash
cd /path/to/agentsec
poetry run pytest examples/3-agent-runtimes/amazon-bedrock-agentcore/tests/unit/ -v
```

Tests cover:
- File structure (all deployment files exist)
- Agent factory configuration (agentsec.protect, providers, endpoints)
- Lambda handler setup (protect before boto3, handler function)
- Direct deploy structure (BedrockAgentCoreApp, entrypoint)
- Container deploy structure (Dockerfile, app.run)
- Syntax validation (all Python files parse)
- Tools definition (add, check_service_health, summarize_log)

### Integration Tests

Run integration tests across deployment modes:

```bash
cd examples/3-agent-runtimes/amazon-bedrock-agentcore
./tests/integration/test-all-modes.sh              # Test all modes
./tests/integration/test-all-modes.sh --verbose    # With detailed output
./tests/integration/test-all-modes.sh direct       # Direct deploy only
./tests/integration/test-all-modes.sh lambda       # Lambda deploy only
```

**Prerequisites for integration tests:**
- Deploy the agent first using the respective `scripts/deploy.sh`
- Have valid AWS credentials configured
- Have AI Defense credentials in `examples/.env`

### Test with agentsec Protection (boto3 SDK Direct)

After deploying, test that agentsec protection is working using the boto3 SDK directly (not CLI):

```bash
cd examples/3-agent-runtimes/amazon-bedrock-agentcore
poetry run python direct-deploy/test_with_protection.py "What is 5+5?"
```

> **Why boto3 SDK?** The `test_with_protection.py` script uses boto3's `invoke_agent_runtime()` directly
> instead of the AgentCore CLI. This ensures both request AND response go through the patched client,
> enabling full AI Defense inspection of both directions.

You should see logs showing **both request AND response inspection**:

```
# Request Inspection
[PATCHED CALL] AgentCore.InvokeAgentRuntime - Request inspection (1 messages)
AI Defense request payload: {'messages': [{'role': 'user', 'content': 'What is 5+5?'}]}
AI Defense response: {...'action': 'Allow'}
[PATCHED CALL] AgentCore.InvokeAgentRuntime - Request decision: allow

# Response Inspection  
[PATCHED CALL] AgentCore.InvokeAgentRuntime - Response inspection (response: 38 chars)
AI Defense request payload: {'messages': [
  {'role': 'user', 'content': 'What is 5+5?'},
  {'role': 'assistant', 'content': 'The result is 10.'}
]}
AI Defense response: {...'action': 'Allow'}
[PATCHED CALL] AgentCore.InvokeAgentRuntime - Response decision: allow
```

### Unit Tests

The AgentCore integration is covered by 38 unit tests in the main test suite:

```bash
# From the repository root
cd /path/to/agentsec
poetry run pytest tests/unit/test_agentcore.py -v
```

Tests cover:
- Service detection (`_is_agentcore_client`, `_is_agentcore_operation`)
- Payload parsing (Bedrock Converse format, simple prompts, query, input, text)
- Response parsing (result, response, completion, content, StreamingBody)
- Gateway mode with AWS Sig V4 authentication
- API mode inspection and enforcement
- State configuration
