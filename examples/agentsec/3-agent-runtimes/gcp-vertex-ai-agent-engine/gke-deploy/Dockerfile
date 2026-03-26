# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

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
