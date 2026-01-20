"""
OpenAI provider with API key authentication.

Supported auth methods:
- api_key (default): OpenAI API key
"""

from typing import Any, Optional

from .base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI provider with API key authentication.
    
    Config structure:
        openai:
          model: gpt-4-turbo
          organization: org-xxx  # Optional
          auth:
            method: api_key
            api_key: ${OPENAI_API_KEY}
    """
    
    AUTH_METHODS = ['api_key']
    
    def __init__(self, config: dict, llm_settings: Optional[dict] = None):
        super().__init__(config, llm_settings)
        self._openai_client = None
    
    @property
    def model_id(self) -> str:
        """Return the OpenAI model ID."""
        return self.config.get('model', 'gpt-4-turbo')
    
    @property
    def organization(self) -> Optional[str]:
        """Return the OpenAI organization ID."""
        return self.config.get('organization')
    
    def authenticate(self) -> None:
        """Set up OpenAI authentication."""
        from openai import OpenAI
        
        auth_config = self.config.get('auth', {})
        method = auth_config.get('method', 'api_key')
        
        if method not in self.AUTH_METHODS:
            raise ValueError(
                f"Unsupported auth method: {method}. "
                f"Supported: {self.AUTH_METHODS}"
            )
        
        api_key = self._resolve_env(auth_config.get('api_key'))
        if not api_key:
            raise ValueError("api_key auth requires 'api_key' in config")
        
        client_kwargs = {'api_key': api_key}
        
        if self.organization:
            client_kwargs['organization'] = self.organization
        
        self._openai_client = OpenAI(**client_kwargs)
        self._authenticated = True
    
    def get_client(self) -> Any:
        """Return the OpenAI client."""
        if not self._authenticated:
            self.authenticate()
        return self._openai_client
    
    # Framework adapters
    
    def get_openai_client(self) -> Any:
        """Return OpenAI client instance."""
        return self.get_client()
    
    def get_langchain_llm(self) -> Any:
        """Return ChatOpenAI instance for LangChain/LangGraph."""
        from langchain_openai import ChatOpenAI
        
        auth_config = self.config.get('auth', {})
        api_key = self._resolve_env(auth_config.get('api_key'))
        
        return ChatOpenAI(
            model=self.model_id,
            api_key=api_key,
            organization=self.organization,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
    
    def get_crewai_llm(self) -> Any:
        """Return CrewAI LLM instance using native OpenAI integration."""
        from crewai import LLM
        
        auth_config = self.config.get('auth', {})
        api_key = self._resolve_env(auth_config.get('api_key'))
        
        # CrewAI native OpenAI integration
        return LLM(
            model=self.model_id,
            api_key=api_key,
            temperature=self.temperature,
        )
    
    def get_strands_model_id(self) -> str:
        """Return model ID for Strands agents."""
        return self.model_id
    
    def get_strands_model(self) -> Any:
        """Return Strands OpenAIModel instance."""
        from strands.models.openai import OpenAIModel
        
        auth_config = self.config.get('auth', {})
        api_key = self._resolve_env(auth_config.get('api_key'))
        
        return OpenAIModel(
            client_args={"api_key": api_key},
            model_id=self.model_id,
            params={
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            },
        )
    
    def get_autogen_config(self) -> dict:
        """Return AutoGen model client configuration."""
        auth_config = self.config.get('auth', {})
        api_key = self._resolve_env(auth_config.get('api_key', ''))
        
        config = {
            'model': self.model_id,
            'api_key': api_key,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
        }
        
        if self.organization:
            config['organization'] = self.organization
        
        return config

