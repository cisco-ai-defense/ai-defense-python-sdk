"""
Tests for provider factory and base provider functionality.
"""

import sys
from pathlib import Path

# Add _shared to path for imports
_shared_dir = Path(__file__).parent.parent
if str(_shared_dir) not in sys.path:
    sys.path.insert(0, str(_shared_dir))

import pytest
from unittest.mock import patch, MagicMock

from providers import create_provider, PROVIDERS
from providers.base import BaseLLMProvider


class TestProviderFactory:
    """Tests for the provider factory function."""
    
    def test_available_providers_list(self):
        """Test PROVIDERS list contains expected providers."""
        assert 'bedrock' in PROVIDERS
        assert 'azure' in PROVIDERS
        assert 'vertex' in PROVIDERS
        assert 'openai' in PROVIDERS
        assert len(PROVIDERS) == 4
    
    def test_unknown_provider_raises_error(self):
        """Test ValueError for unknown provider name."""
        config = {'provider': 'unknown_provider'}
        
        with pytest.raises(ValueError) as exc_info:
            create_provider(config)
        
        assert "Unknown provider: unknown_provider" in str(exc_info.value)
        assert "Available providers:" in str(exc_info.value)
    
    def test_default_provider_is_openai(self):
        """Test that missing provider key defaults to openai."""
        with patch('providers._get_provider_class') as mock_get:
            mock_provider_class = MagicMock()
            mock_provider_instance = MagicMock()
            mock_provider_class.return_value = mock_provider_instance
            mock_get.return_value = mock_provider_class
            
            config = {'openai': {'api_key': 'test'}}  # No 'provider' key
            create_provider(config)
            
            mock_get.assert_called_with('openai')
    
    @patch('providers.bedrock.BedrockProvider')
    def test_bedrock_provider_created(self, mock_bedrock):
        """Test Bedrock provider is instantiated correctly."""
        mock_instance = MagicMock()
        mock_bedrock.return_value = mock_instance
        
        config = {
            'provider': 'bedrock',
            'bedrock': {
                'model_id': 'anthropic.claude-3-haiku-20240307-v1:0',
                'region': 'us-east-1',
                'auth': {'method': 'default'}
            },
            'llm_settings': {'temperature': 0.5}
        }
        
        # Reset the cache to ensure fresh import
        from providers import _provider_classes
        _provider_classes.clear()
        
        with patch('providers.bedrock.BedrockProvider', mock_bedrock):
            from providers import _provider_classes
            _provider_classes['bedrock'] = mock_bedrock
            
            provider = create_provider(config)
            
            mock_bedrock.assert_called_once()
            mock_instance.authenticate.assert_called_once()
    
    def test_llm_settings_passed_to_provider(self):
        """Test LLM settings are passed to provider constructor."""
        with patch('providers._get_provider_class') as mock_get:
            mock_provider_class = MagicMock()
            mock_provider_instance = MagicMock()
            mock_provider_class.return_value = mock_provider_instance
            mock_get.return_value = mock_provider_class
            
            config = {
                'provider': 'openai',
                'openai': {'api_key': 'test'},
                'llm_settings': {'temperature': 0.9, 'max_tokens': 2048}
            }
            
            create_provider(config)
            
            # Check llm_settings was passed
            call_args = mock_provider_class.call_args
            assert call_args[0][1] == {'temperature': 0.9, 'max_tokens': 2048}


class TestBaseLLMProvider:
    """Tests for the BaseLLMProvider abstract base class."""
    
    def test_cannot_instantiate_directly(self):
        """Test BaseLLMProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseLLMProvider({}, {})
    
    def test_resolve_env_simple(self, monkeypatch):
        """Test _resolve_env resolves ${VAR} syntax."""
        # Create a concrete implementation for testing
        class TestProvider(BaseLLMProvider):
            AUTH_METHODS = ['api_key']
            
            def authenticate(self):
                self._authenticated = True
            
            @property
            def model_id(self):
                return 'test-model'
        
        monkeypatch.setenv("TEST_KEY", "secret_value")
        provider = TestProvider({}, {})
        
        result = provider._resolve_env("${TEST_KEY}")
        assert result == "secret_value"
    
    def test_resolve_env_with_default(self, monkeypatch):
        """Test _resolve_env handles ${VAR:-default} syntax."""
        class TestProvider(BaseLLMProvider):
            AUTH_METHODS = ['api_key']
            
            def authenticate(self):
                self._authenticated = True
            
            @property
            def model_id(self):
                return 'test-model'
        
        monkeypatch.delenv("MISSING_KEY", raising=False)
        provider = TestProvider({}, {})
        
        result = provider._resolve_env("${MISSING_KEY:-fallback}")
        assert result == "fallback"
    
    def test_resolve_env_passthrough(self):
        """Test _resolve_env passes through non-env-var strings."""
        class TestProvider(BaseLLMProvider):
            AUTH_METHODS = ['api_key']
            
            def authenticate(self):
                self._authenticated = True
            
            @property
            def model_id(self):
                return 'test-model'
        
        provider = TestProvider({}, {})
        
        assert provider._resolve_env("plain_string") == "plain_string"
        assert provider._resolve_env(None) is None
        assert provider._resolve_env(123) == 123
    
    def test_default_temperature(self):
        """Test temperature defaults to 0.7."""
        class TestProvider(BaseLLMProvider):
            AUTH_METHODS = ['api_key']
            
            def authenticate(self):
                self._authenticated = True
            
            @property
            def model_id(self):
                return 'test-model'
        
        provider = TestProvider({}, {})
        assert provider.temperature == 0.7
    
    def test_custom_temperature(self):
        """Test temperature from llm_settings."""
        class TestProvider(BaseLLMProvider):
            AUTH_METHODS = ['api_key']
            
            def authenticate(self):
                self._authenticated = True
            
            @property
            def model_id(self):
                return 'test-model'
        
        provider = TestProvider({}, {'temperature': 0.3})
        assert provider.temperature == 0.3
    
    def test_default_max_tokens(self):
        """Test max_tokens defaults to 4096."""
        class TestProvider(BaseLLMProvider):
            AUTH_METHODS = ['api_key']
            
            def authenticate(self):
                self._authenticated = True
            
            @property
            def model_id(self):
                return 'test-model'
        
        provider = TestProvider({}, {})
        assert provider.max_tokens == 4096
    
    def test_framework_adapters_raise_not_implemented(self):
        """Test unimplemented framework adapters raise NotImplementedError."""
        class TestProvider(BaseLLMProvider):
            AUTH_METHODS = ['api_key']
            
            def authenticate(self):
                self._authenticated = True
            
            @property
            def model_id(self):
                return 'test-model'
        
        provider = TestProvider({}, {})
        
        with pytest.raises(NotImplementedError):
            provider.get_langchain_llm()
        
        with pytest.raises(NotImplementedError):
            provider.get_crewai_llm()
        
        with pytest.raises(NotImplementedError):
            provider.get_strands_model_id()
        
        with pytest.raises(NotImplementedError):
            provider.get_openai_client()
        
        with pytest.raises(NotImplementedError):
            provider.get_autogen_config()
    
    def test_repr(self):
        """Test __repr__ shows useful info."""
        class TestProvider(BaseLLMProvider):
            AUTH_METHODS = ['api_key']
            
            def authenticate(self):
                self._authenticated = True
            
            @property
            def model_id(self):
                return 'gpt-4'
        
        provider = TestProvider({'auth': {'method': 'api_key'}}, {})
        repr_str = repr(provider)
        
        assert 'TestProvider' in repr_str
        assert 'gpt-4' in repr_str
        assert 'api_key' in repr_str


class TestBedrockProviderAuthMethods:
    """Tests for Bedrock provider authentication methods."""
    
    def test_auth_methods_defined(self):
        """Test Bedrock provider has expected auth methods."""
        from providers.bedrock import BedrockProvider
        
        expected = ['session_token', 'default', 'profile', 'iam_role', 'access_key']
        for method in expected:
            assert method in BedrockProvider.AUTH_METHODS
    
    @patch('boto3.client')
    def test_default_auth_creates_client(self, mock_boto_client):
        """Test default auth method creates boto3 client."""
        from providers.bedrock import BedrockProvider
        
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        
        config = {
            'model_id': 'anthropic.claude-3-haiku-20240307-v1:0',
            'region': 'us-east-1',
            'auth': {'method': 'default'}
        }
        
        provider = BedrockProvider(config, {})
        provider.authenticate()
        
        mock_boto_client.assert_called_once()
        assert 'bedrock-runtime' in str(mock_boto_client.call_args)


class TestAzureProviderAuthMethods:
    """Tests for Azure provider authentication methods."""
    
    def test_auth_methods_defined(self):
        """Test Azure provider has expected auth methods."""
        from providers.azure import AzureOpenAIProvider
        
        expected = ['api_key', 'managed_identity', 'service_principal', 'cli']
        for method in expected:
            assert method in AzureOpenAIProvider.AUTH_METHODS


class TestVertexProviderAuthMethods:
    """Tests for Vertex AI provider authentication methods."""
    
    def test_auth_methods_defined(self):
        """Test Vertex provider has expected auth methods."""
        from providers.vertex import VertexAIProvider
        
        # Vertex AI uses ADC and other GCP auth methods (Google GenAI api_key removed)
        expected = ['adc', 'service_account', 'workload_identity', 'impersonation']
        for method in expected:
            assert method in VertexAIProvider.AUTH_METHODS


class TestOpenAIProviderAuthMethods:
    """Tests for OpenAI provider authentication methods."""
    
    def test_auth_methods_defined(self):
        """Test OpenAI provider has expected auth methods."""
        from providers.openai import OpenAIProvider
        
        assert 'api_key' in OpenAIProvider.AUTH_METHODS
    
    def test_api_key_auth_creates_client(self):
        """Test API key auth creates OpenAI client."""
        try:
            import openai
        except ImportError:
            pytest.skip("openai not installed")
        
        from providers.openai import OpenAIProvider
        
        with patch.object(openai, 'OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            
            config = {
                'model': 'gpt-4',
                'auth': {
                    'method': 'api_key',
                    'api_key': 'sk-test123'
                }
            }
            
            provider = OpenAIProvider(config, {})
            provider.authenticate()
            
            mock_openai.assert_called_once()
            # OpenAIProvider stores client in _openai_client, not _client
            assert provider._openai_client == mock_client

