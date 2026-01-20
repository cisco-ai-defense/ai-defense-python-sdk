"""
GCP Vertex AI provider with multiple authentication methods.

Supported auth methods:
- adc (default): Application Default Credentials (uses vertexai)
- service_account: Service account key file or JSON (uses vertexai)
- workload_identity: GKE Workload Identity (uses vertexai)
- impersonation: Service account impersonation (uses vertexai)
"""

from typing import Any, Optional

from .base import BaseLLMProvider


class VertexAIProvider(BaseLLMProvider):
    """
    GCP Vertex AI provider supporting multiple authentication methods.
    
    Config structure:
        vertex:
          model_id: gemini-2.5-flash-lite
          project_id: your-gcp-project
          location: us-central1
          auth:
            method: adc  # or service_account, workload_identity, impersonation
            # For service_account:
            key_file: /path/to/service-account.json
            # or key_json: ${GCP_SERVICE_ACCOUNT_JSON}
            # For impersonation:
            target_service_account: sa@project.iam.gserviceaccount.com
            delegates: []  # Optional delegation chain
    """
    
    AUTH_METHODS = ['adc', 'service_account', 'workload_identity', 'impersonation']
    
    def __init__(self, config: dict, llm_settings: Optional[dict] = None):
        super().__init__(config, llm_settings)
        self._vertex_model = None
        self._credentials = None
    
    @property
    def model_id(self) -> str:
        """Return the Gemini model ID."""
        return self.config.get('model_id', 'gemini-2.5-flash-lite')
    
    @property
    def project_id(self) -> Optional[str]:
        """Return the GCP project ID (for Vertex AI)."""
        return self.config.get('project_id')
    
    @property
    def location(self) -> str:
        """Return the GCP location (for Vertex AI)."""
        return self.config.get('location', 'us-central1')
    
    def authenticate(self) -> None:
        """Set up GCP authentication based on config."""
        auth_config = self.config.get('auth', {})
        method = auth_config.get('method', 'adc')
        
        if method not in self.AUTH_METHODS:
            raise ValueError(
                f"Unsupported auth method: {method}. "
                f"Supported: {self.AUTH_METHODS}"
            )
        
        self._authenticate_vertexai(auth_config, method)
        self._authenticated = True
    
    def _authenticate_vertexai(self, auth_config: dict, method: str) -> None:
        """Authenticate using Vertex AI with various credential types."""
        try:
            import vertexai
            from google.auth import default as auth_default
            from google.auth import impersonated_credentials
            from google.oauth2 import service_account
        except ImportError:
            raise ImportError(
                "vertexai and google-auth packages required for Vertex AI auth. "
                "Install with: pip install google-cloud-aiplatform"
            )
        
        if not self.project_id:
            raise ValueError("Vertex AI methods require 'project_id' in config")
        
        credentials = None
        
        if method == 'adc':
            # Application Default Credentials
            credentials, _ = auth_default()
        
        elif method == 'service_account':
            key_file = auth_config.get('key_file')
            key_json = self._resolve_env(auth_config.get('key_json'))
            
            if key_file:
                credentials = service_account.Credentials.from_service_account_file(
                    key_file
                )
            elif key_json:
                import json
                key_data = json.loads(key_json)
                credentials = service_account.Credentials.from_service_account_info(
                    key_data
                )
            else:
                raise ValueError(
                    "service_account auth requires 'key_file' or 'key_json' in config"
                )
        
        elif method == 'workload_identity':
            # For GKE with Workload Identity - uses ADC
            credentials, _ = auth_default()
        
        elif method == 'impersonation':
            target_sa = auth_config.get('target_service_account')
            if not target_sa:
                raise ValueError(
                    "impersonation auth requires 'target_service_account' in config"
                )
            
            delegates = auth_config.get('delegates', [])
            source_credentials, _ = auth_default()
            
            credentials = impersonated_credentials.Credentials(
                source_credentials=source_credentials,
                target_principal=target_sa,
                delegates=delegates,
                target_scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
        
        self._credentials = credentials
        vertexai.init(
            project=self.project_id,
            location=self.location,
            credentials=credentials
        )
    
    def get_client(self) -> Any:
        """Return Vertex AI GenerativeModel client."""
        if not self._authenticated:
            self.authenticate()
        
        from vertexai.generative_models import GenerativeModel
        return GenerativeModel(self.model_id)
    
    # Framework adapters
    
    def get_langchain_llm(self) -> Any:
        """Return LangChain-compatible ChatVertexAI model."""
        from langchain_google_vertexai import ChatVertexAI
        
        if not self._authenticated:
            self.authenticate()
        
        return ChatVertexAI(
            model_name=self.model_id,
            project=self.project_id,
            location=self.location,
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )
    
    def get_crewai_llm(self) -> Any:
        """Return CrewAI LLM instance using Vertex AI integration."""
        from crewai import LLM
        
        if not self._authenticated:
            self.authenticate()
        
        # CrewAI Vertex AI integration uses vertex_ai/ prefix
        return LLM(
            model=f"vertex_ai/{self.model_id}",
            vertex_project=self.project_id,
            vertex_location=self.location,
            temperature=self.temperature,
        )
    
    def get_strands_model_id(self) -> str:
        """Return model ID for Strands agents."""
        return self.model_id
    
    def get_strands_model(self) -> Any:
        """Return Strands GeminiModel instance using Vertex AI with ADC."""
        # Strands GeminiModel can use Vertex AI via google-genai client
        # configured with vertexai=True and ADC credentials
        if not self._authenticated:
            self.authenticate()
        
        try:
            from strands.models.gemini import GeminiModel
            from google import genai
            
            # Create a google-genai client configured for Vertex AI with ADC
            client = genai.Client(
                vertexai=True,
                credentials=self._credentials,
                project=self.project_id,
                location=self.location,
            )
            
            return GeminiModel(
                client=client,
                model_id=self.model_id,
                params={
                    "temperature": self.temperature,
                    "max_output_tokens": self.max_tokens,
                },
            )
        except ImportError:
            # Fallback: return None to use model_id string
            return None
    
    def get_autogen_config(self) -> dict:
        """Return AutoGen model client configuration for Vertex AI."""
        if not self._authenticated:
            self.authenticate()
        
        return {
            'model': self.model_id,
            'api_type': 'vertex_ai',
            'project': self.project_id,
            'location': self.location,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
        }

