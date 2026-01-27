"""
Provider factory for creating LLM provider instances.

Supports:
- AWS Bedrock (bedrock)
- Azure OpenAI (azure)
- GCP Vertex AI (vertex)
- OpenAI (openai)
"""

from typing import TYPE_CHECKING

from .base import BaseLLMProvider

if TYPE_CHECKING:
    pass

# Lazy imports to avoid requiring all provider dependencies
_provider_classes = {}


def _get_provider_class(name: str):
    """Lazily import provider classes to avoid dependency issues."""
    if name not in _provider_classes:
        if name == 'bedrock':
            from .bedrock import BedrockProvider
            _provider_classes['bedrock'] = BedrockProvider
        elif name == 'azure':
            from .azure import AzureOpenAIProvider
            _provider_classes['azure'] = AzureOpenAIProvider
        elif name == 'vertex':
            from .vertex import VertexAIProvider
            _provider_classes['vertex'] = VertexAIProvider
        elif name == 'openai':
            from .openai import OpenAIProvider
            _provider_classes['openai'] = OpenAIProvider
        else:
            raise ValueError(f"Unknown provider: {name}")
    
    return _provider_classes[name]


# Available providers
PROVIDERS = ['bedrock', 'azure', 'vertex', 'openai']


def create_provider(config: dict) -> BaseLLMProvider:
    """
    Factory function to create the appropriate provider based on config.
    
    Args:
        config: Configuration dict with 'provider' key and provider-specific settings.
    
    Returns:
        Initialized and authenticated provider instance.
    
    Raises:
        ValueError: If provider name is unknown.
        KeyError: If required config keys are missing.
    
    Example:
        config = {
            'provider': 'bedrock',
            'bedrock': {
                'model_id': 'anthropic.claude-3-haiku-20240307-v1:0',
                'region': 'us-east-1',
                'auth': {'method': 'session_token', ...}
            },
            'llm_settings': {'temperature': 0.7, 'max_tokens': 4096}
        }
        provider = create_provider(config)
    """
    provider_name = config.get('provider', 'openai')
    
    if provider_name not in PROVIDERS:
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            f"Available providers: {PROVIDERS}"
        )
    
    # Get provider-specific config
    provider_config = config.get(provider_name, {})
    
    # Get common LLM settings
    llm_settings = config.get('llm_settings', {})
    
    # Get provider class and instantiate
    provider_class = _get_provider_class(provider_name)
    provider = provider_class(provider_config, llm_settings)
    
    # Authenticate
    provider.authenticate()
    
    return provider


__all__ = ['BaseLLMProvider', 'create_provider', 'PROVIDERS']

