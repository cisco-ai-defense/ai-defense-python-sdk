# =============================================================================
# Dockerfile for Azure AI Foundry Agent Application
# =============================================================================
# This Dockerfile builds a container image for the SRE agent.
# Azure ML managed endpoints inject their own inference server (azmlinfsrv),
# so we must use /var/azureml-app and provide main.py with init()/run().
#
# Build context should be the microsoft-foundry example root directory:
#   docker build -f foundry-agent-app/Dockerfile -t foundry-agent-app .
#
# Note: agentsec is not on PyPI, so we copy it from source.
# =============================================================================

FROM python:3.10-slim

USER root

# Azure ML expects the app at /var/azureml-app
WORKDIR /var/azureml-app

# Set Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/var/azureml-app \
    AZUREML_APP_ROOT=/var/azureml-app

# Install pip dependencies
COPY foundry-agent-app/requirements.txt /var/azureml-app/requirements.txt
RUN pip install --no-cache-dir -r /var/azureml-app/requirements.txt

# Copy aidefense SDK from the repository (since it's not on PyPI)
COPY aidefense /var/azureml-app/aidefense

# Copy shared code (agent_factory, tools)
COPY _shared /var/azureml-app/_shared

# Copy the main.py entry script (required by Azure ML inference server)
COPY foundry-agent-app/main.py /var/azureml-app/main.py

# Set default log level
ENV AGENTSEC_LOG_LEVEL=DEBUG

# Azure ML inference server uses port 5001
EXPOSE 5001

# Start the Azure ML inference server which calls main.py init()/run()
# Use full module path to ensure the server is found (azmlinfsrv may not be in PATH after pip install)
CMD ["python", "-m", "azureml_inference_server_http.amlserver", "--entry_script", "main.py", "--port", "5001"]
