# Dockerfile for GKE deployment
# Builds a container with the SRE agent protected by Cisco AI Defense
#
# Build context should be the gcp-vertex-ai-agent-engine directory

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
	gcc \
	&& rm -rf /var/lib/apt/lists/*

# Copy requirements and install all dependencies
COPY gke-deploy/requirements.txt /app/requirements.txt
# Install SDK dependencies + app dependencies (excluding cisco-aidefense-sdk since we copy source)
RUN grep -v "^cisco-aidefense-sdk" /app/requirements.txt > /tmp/requirements.txt && \
	pip install --no-cache-dir -r /tmp/requirements.txt && \
	pip install --no-cache-dir wrapt httpx pyyaml python-dotenv aiohttp pydantic

# Copy Cisco AI Defense SDK source directly (avoids Poetry build issues)
COPY agentsec_package/aidefense /app/aidefense

# Copy shared modules and application
COPY _shared /app/_shared
COPY gke-deploy/app.py /app/app.py

# Create non-root user for security
RUN useradd -m -u 1000 agent && chown -R agent:agent /app
USER agent

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "app.py"]
