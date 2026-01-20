# =============================================================================
# Dockerfile for AgentCore Container Deploy
# =============================================================================
# This Dockerfile builds a container image for the AgentCore agent.
# It uses Python 3.11 slim as the base image.
#
# Build context should be the agentcore example root directory:
#   docker build -f container-deploy/Dockerfile -t agentcore-sre .
#
# Note: cisco-aidefense-sdk is not on PyPI, so we copy it from source.
# =============================================================================

FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# Set Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PYTHONPATH=/app

# Install pip dependencies (excluding cisco-aidefense-sdk which isn't on PyPI)
COPY container-deploy/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir strands-agents bedrock-agentcore python-dotenv httpx wrapt pyyaml aiohttp pydantic

# Copy aidefense SDK from the repository (since it's not on PyPI)
# The deploy.sh script copies aidefense to the root directory before build
COPY aidefense /app/aidefense

# Copy shared code (agent_factory, tools)
COPY _shared /app/_shared

# Copy the app entrypoint
COPY container-deploy/agentcore_app.py /app/agentcore_app.py

# Set log level for debugging (AI Defense credentials should be set via AgentCore env vars)
ENV AGENTSEC_LOG_LEVEL=DEBUG

# Expose the default AgentCore port
EXPOSE 8080

# Run the AgentCore app
CMD ["python", "-m", "agentcore_app"]
