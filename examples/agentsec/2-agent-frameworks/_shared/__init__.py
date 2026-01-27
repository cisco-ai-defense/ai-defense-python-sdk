"""
Shared provider infrastructure for agentsec examples.

This module provides a unified way to configure and use different LLM providers
(AWS Bedrock, Azure OpenAI, GCP Vertex AI, OpenAI) across all agent examples.

Usage:
    from _shared import load_config, create_provider
    
    config = load_config()  # Loads from CONFIG_FILE env var or config.yaml
    provider = create_provider(config)
    
    # Use provider with your framework
    llm = provider.get_langchain_llm()  # For LangGraph
    llm = provider.get_crewai_llm()     # For CrewAI
    model_id = provider.get_strands_model_id()  # For Strands
    client = provider.get_openai_client()  # For OpenAI/AutoGen
"""

from .config import load_config
from .providers import create_provider, PROVIDERS

__all__ = ['load_config', 'create_provider', 'PROVIDERS']

