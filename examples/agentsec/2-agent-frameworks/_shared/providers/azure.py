"""
Azure OpenAI provider with multiple authentication methods.

Supported auth methods:
- api_key (default): Direct API key authentication
- managed_identity: Azure Managed Identity (system or user-assigned)
- service_principal: Azure AD service principal with client secret
- cli: Azure CLI credentials (az login)
"""

from typing import Any, Optional

from .base import BaseLLMProvider


class AzureOpenAIProvider(BaseLLMProvider):
    """
    Azure OpenAI provider supporting multiple authentication methods.
    
    Config structure:
        azure:
          endpoint: https://your-resource.openai.azure.com
          deployment_name: gpt-4-turbo
          api_version: "2024-02-15-preview"
          auth:
            method: api_key  # or managed_identity, service_principal, cli
            # For api_key:
            api_key: ${AZURE_OPENAI_API_KEY}
            # For managed_identity:
            client_id: optional-user-assigned-identity-client-id
            # For service_principal:
            tenant_id: ${AZURE_TENANT_ID}
            client_id: ${AZURE_CLIENT_ID}
            client_secret: ${AZURE_CLIENT_SECRET}
    """
    
    AUTH_METHODS = ['api_key', 'managed_identity', 'service_principal', 'cli']
    
    def __init__(self, config: dict, llm_settings: Optional[dict] = None):
        super().__init__(config, llm_settings)
        self._azure_client = None
        self._credential = None
    
    @property
    def model_id(self) -> str:
        """Return the Azure deployment name."""
        return self.config.get('deployment_name', 'gpt-4-turbo')
    
    @property
    def endpoint(self) -> str:
        """Return the Azure OpenAI endpoint."""
        return self.config.get('endpoint', '')
    
    @property
    def api_version(self) -> str:
        """Return the Azure OpenAI API version."""
        return self.config.get('api_version', '2024-02-15-preview')
    
    def authenticate(self) -> None:
        """Set up Azure authentication based on config."""
        from openai import AzureOpenAI
        
        auth_config = self.config.get('auth', {})
        method = auth_config.get('method', 'api_key')
        
        if method not in self.AUTH_METHODS:
            raise ValueError(
                f"Unsupported auth method: {method}. "
                f"Supported: {self.AUTH_METHODS}"
            )
        
        if not self.endpoint:
            raise ValueError("Azure OpenAI requires 'endpoint' in config")
        
        if method == 'api_key':
            # Direct API key authentication
            api_key = self._resolve_env(auth_config.get('api_key'))
            if not api_key:
                raise ValueError("api_key auth requires 'api_key' in config")
            
            self._azure_client = AzureOpenAI(
                api_key=api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint
            )
        
        elif method in ['managed_identity', 'service_principal', 'cli']:
            # Token-based authentication using azure-identity
            try:
                from azure.identity import (
                    DefaultAzureCredential,
                    ManagedIdentityCredential,
                    ClientSecretCredential
                )
            except ImportError:
                raise ImportError(
                    "azure-identity package required for token-based auth. "
                    "Install with: pip install azure-identity"
                )
            
            if method == 'managed_identity':
                # User-assigned identity needs client_id
                client_id = auth_config.get('client_id')
                self._credential = ManagedIdentityCredential(client_id=client_id)
            
            elif method == 'service_principal':
                tenant_id = self._resolve_env(auth_config.get('tenant_id'))
                client_id = self._resolve_env(auth_config.get('client_id'))
                client_secret = self._resolve_env(auth_config.get('client_secret'))
                
                if not all([tenant_id, client_id, client_secret]):
                    raise ValueError(
                        "service_principal auth requires 'tenant_id', 'client_id', "
                        "and 'client_secret' in config"
                    )
                
                self._credential = ClientSecretCredential(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=client_secret
                )
            
            else:  # cli
                self._credential = DefaultAzureCredential()
            
            # Get token for Azure OpenAI
            token = self._credential.get_token(
                "https://cognitiveservices.azure.com/.default"
            )
            
            self._azure_client = AzureOpenAI(
                api_key=token.token,
                api_version=self.api_version,
                azure_endpoint=self.endpoint
            )
        
        self._authenticated = True
    
    def get_client(self) -> Any:
        """Return the AzureOpenAI client."""
        if not self._authenticated:
            self.authenticate()
        return self._azure_client
    
    # Framework adapters
    
    def get_openai_client(self) -> Any:
        """Return AzureOpenAI client instance."""
        return self.get_client()
    
    def get_langchain_llm(self) -> Any:
        """Return AzureChatOpenAI instance for LangChain/LangGraph."""
        from langchain_openai import AzureChatOpenAI
        
        auth_config = self.config.get('auth', {})
        method = auth_config.get('method', 'api_key')
        
        if method == 'api_key':
            api_key = self._resolve_env(auth_config.get('api_key'))
            return AzureChatOpenAI(
                deployment_name=self.model_id,
                azure_endpoint=self.endpoint,
                api_version=self.api_version,
                api_key=api_key,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        else:
            # For token-based auth, ensure we're authenticated
            if not self._authenticated:
                self.authenticate()
            
            # Get fresh token
            token = self._credential.get_token(
                "https://cognitiveservices.azure.com/.default"
            )
            
            return AzureChatOpenAI(
                deployment_name=self.model_id,
                azure_endpoint=self.endpoint,
                api_version=self.api_version,
                api_key=token.token,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
    
    def get_crewai_llm(self) -> Any:
        """Return CrewAI LLM instance for Azure OpenAI.
        
        Uses CrewAI's native Azure integration (requires crewai[azure-ai-inference]).
        """
        from crewai import LLM
        
        auth_config = self.config.get('auth', {})
        api_key = self._resolve_env(auth_config.get('api_key'))
        
        # Build the Azure endpoint URL with deployment
        # Format: https://<resource>.openai.azure.com/openai/deployments/<deployment>
        endpoint = f"{self.endpoint.rstrip('/')}/openai/deployments/{self.model_id}"
        
        # CrewAI native Azure integration
        return LLM(
            model=f"azure/{self.model_id}",
            api_key=api_key,
            base_url=endpoint,
            api_version=self.api_version,
            temperature=self.temperature,
        )
    
    def get_strands_model(self) -> Any:
        """Return Strands OpenAIModel configured for Azure OpenAI."""
        from strands.models.openai import OpenAIModel
        
        auth_config = self.config.get('auth', {})
        api_key = self._resolve_env(auth_config.get('api_key'))
        
        # Azure OpenAI uses OpenAIModel with custom base_url
        # Format: https://<resource>.openai.azure.com/openai/deployments/<deployment>
        base_url = f"{self.endpoint.rstrip('/')}/openai/deployments/{self.model_id}"
        
        return OpenAIModel(
            client_args={
                "api_key": api_key,
                "base_url": base_url,
                "default_headers": {"api-key": api_key},
                "default_query": {"api-version": self.api_version},
            },
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
        
        return {
            'model': self.model_id,
            'api_type': 'azure',
            'api_key': api_key,
            'base_url': self.endpoint,
            'api_version': self.api_version,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
        }

