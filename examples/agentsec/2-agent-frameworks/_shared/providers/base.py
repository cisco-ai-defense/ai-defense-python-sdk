"""
Base class for LLM providers.

All provider implementations must inherit from BaseLLMProvider and implement
the required abstract methods.
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseLLMProvider(ABC):
    """
    Abstract base class for all LLM providers.
    
    Subclasses must implement:
    - authenticate(): Set up authentication based on config
    - model_id (property): Return the model identifier
    
    Subclasses should implement framework adapters as needed:
    - get_langchain_llm(): For LangGraph/LangChain
    - get_crewai_llm(): For CrewAI
    - get_strands_model_id(): For Strands
    - get_openai_client(): For OpenAI SDK / Azure OpenAI
    - get_autogen_config(): For AutoGen
    """
    
    # List of supported auth methods (override in subclasses)
    AUTH_METHODS: list[str] = []
    
    def __init__(self, config: dict, llm_settings: Optional[dict] = None):
        """
        Initialize the provider.
        
        Args:
            config: Provider-specific configuration dict.
            llm_settings: Common LLM settings (temperature, max_tokens, etc.)
        """
        self.config = config
        self.llm_settings = llm_settings or {}
        self._client = None
        self._authenticated = False
    
    def _resolve_env(self, value: Optional[str]) -> Optional[str]:
        """
        Resolve environment variable references in a value.
        
        Handles ${VAR} syntax that might not have been resolved during config loading
        (e.g., if the value was added programmatically).
        
        Args:
            value: String that may contain ${VAR} reference.
        
        Returns:
            Resolved value or original value if not an env var reference.
        """
        if value is None:
            return None
        
        if not isinstance(value, str):
            return value
        
        # Check if it's a simple ${VAR} reference
        if value.startswith('${') and value.endswith('}'):
            # Extract var name, handling default syntax
            inner = value[2:-1]
            if ':-' in inner:
                var_name, default = inner.split(':-', 1)
                return os.environ.get(var_name, default)
            else:
                return os.environ.get(inner, '')
        
        return value
    
    @abstractmethod
    def authenticate(self) -> None:
        """
        Set up authentication based on config.
        
        This method should:
        1. Read auth config from self.config['auth']
        2. Set up credentials based on auth method
        3. Create any necessary clients
        4. Set self._authenticated = True on success
        
        Raises:
            ValueError: If auth method is unsupported.
            Exception: If authentication fails.
        """
        pass
    
    @property
    @abstractmethod
    def model_id(self) -> str:
        """
        Return the model identifier.
        
        Returns:
            Model ID string (e.g., 'anthropic.claude-3-haiku-20240307-v1:0')
        """
        pass
    
    @property
    def temperature(self) -> float:
        """Return configured temperature or default."""
        return self.llm_settings.get('temperature', 0.7)
    
    @property
    def max_tokens(self) -> int:
        """Return configured max_tokens or default."""
        return self.llm_settings.get('max_tokens', 4096)
    
    # Framework adapter methods - override in subclasses as needed
    
    def get_langchain_llm(self) -> Any:
        """
        Return a LangChain-compatible chat model instance.
        
        Returns:
            LangChain BaseChatModel instance (ChatBedrock, AzureChatOpenAI, etc.)
        
        Raises:
            NotImplementedError: If provider doesn't support LangChain.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support LangChain. "
            f"Use a different provider or implement get_langchain_llm()."
        )
    
    def get_crewai_llm(self) -> Any:
        """
        Return a CrewAI-compatible LLM instance.
        
        Returns:
            CrewAI LLM instance
        
        Raises:
            NotImplementedError: If provider doesn't support CrewAI.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support CrewAI. "
            f"Use a different provider or implement get_crewai_llm()."
        )
    
    def get_strands_model_id(self) -> str:
        """
        Return model ID for Strands agents.
        
        Returns:
            Model ID string for Strands Agent(model=...)
        
        Raises:
            NotImplementedError: If provider doesn't support Strands.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support Strands. "
            f"Use a different provider or implement get_strands_model_id()."
        )
    
    def get_openai_client(self) -> Any:
        """
        Return an OpenAI-compatible client instance.
        
        Returns:
            OpenAI or AzureOpenAI client instance
        
        Raises:
            NotImplementedError: If provider doesn't support OpenAI client.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support OpenAI client. "
            f"Use a different provider or implement get_openai_client()."
        )
    
    def get_autogen_config(self) -> dict:
        """
        Return configuration dict for AutoGen model client.
        
        Returns:
            Dict with model client configuration for AutoGen
        
        Raises:
            NotImplementedError: If provider doesn't support AutoGen.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support AutoGen. "
            f"Use a different provider or implement get_autogen_config()."
        )
    
    def __repr__(self) -> str:
        auth_method = self.config.get('auth', {}).get('method', 'default')
        return f"<{self.__class__.__name__} model={self.model_id} auth={auth_method}>"

