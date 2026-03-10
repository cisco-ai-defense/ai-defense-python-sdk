"""Tests for VertexAI patcher."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from aidefense.runtime.agentsec.patchers.vertexai import (
    patch_vertexai,
    _wrap_generate_content,
)
from aidefense.runtime.agentsec.exceptions import SecurityPolicyError
from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec import _state
from aidefense.runtime.agentsec._context import clear_inspection_context
from aidefense.runtime.agentsec.patchers import reset_registry


@pytest.fixture(autouse=True)
def reset_state():
    """Reset agentsec state before each test."""
    _state.reset()
    reset_registry()
    clear_inspection_context()
    # Reset global inspector
    import aidefense.runtime.agentsec.patchers.vertexai as vertexai_module
    vertexai_module._inspector = None
    yield
    _state.reset()
    reset_registry()
    clear_inspection_context()
    vertexai_module._inspector = None


class TestVertexAIPatcherInspection:
    """Test inspection integration."""

    @patch("aidefense.runtime.agentsec.patchers.vertexai._get_inspector")
    def test_sync_generate_content_calls_inspector(self, mock_get_inspector):
        """Test that sync generate_content triggers inspection."""
        # Setup
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.allow(reasons=[])
        mock_get_inspector.return_value = mock_inspector
        
        # Setup state
        _state.set_state(
            initialized=True,
            api_mode={"llm": {"mode": "monitor"}, "llm_defaults": {"fail_open": True}},
        )
        clear_inspection_context()
        
        # Mock wrapped function
        mock_wrapped = MagicMock()
        mock_response = MagicMock()
        mock_response.candidates = []
        mock_wrapped.return_value = mock_response
        
        # Mock instance
        mock_instance = MagicMock()
        mock_instance.model_name = "gemini-pro"
        
        # Call wrapper
        result = _wrap_generate_content(
            mock_wrapped,
            mock_instance,
            ("Hello",),
            {}
        )
        
        # Verify inspector was called
        mock_inspector.inspect_conversation.assert_called()
        # Verify provider metadata
        call_args = mock_inspector.inspect_conversation.call_args
        metadata = call_args[0][1]  # Second positional arg
        assert metadata.get("provider") == "vertexai"

    @patch("aidefense.runtime.agentsec.patchers.vertexai._get_inspector")
    def test_enforce_mode_raises_on_block(self, mock_get_inspector):
        """Test that enforce mode raises SecurityPolicyError on block."""
        # Setup
        mock_inspector = MagicMock()
        mock_inspector.inspect_conversation.return_value = Decision.block(reasons=["policy_violation"])
        mock_get_inspector.return_value = mock_inspector
        
        # Setup state in enforce mode
        _state.set_state(
            initialized=True,
            api_mode={"llm": {"mode": "enforce"}, "llm_defaults": {"fail_open": True}},
        )
        clear_inspection_context()
        
        # Mock wrapped function
        mock_wrapped = MagicMock()
        
        # Mock instance
        mock_instance = MagicMock()
        mock_instance.model_name = "gemini-pro"
        
        # Call wrapper - should raise
        with pytest.raises(SecurityPolicyError):
            _wrap_generate_content(
                mock_wrapped,
                mock_instance,
                ("Hello",),
                {}
            )


class TestVertexAIPatcherAsync:
    """Test async inspection."""

    @pytest.mark.asyncio
    @patch("aidefense.runtime.agentsec.patchers.vertexai._get_inspector")
    async def test_async_generate_content_calls_inspector(self, mock_get_inspector):
        """Test that async generate_content triggers inspection."""
        from aidefense.runtime.agentsec.patchers.vertexai import _wrap_generate_content_async
        
        # Setup
        mock_inspector = MagicMock()
        mock_inspector.ainspect_conversation = AsyncMock(return_value=Decision.allow(reasons=[]))
        mock_get_inspector.return_value = mock_inspector
        
        # Setup state
        _state.set_state(
            initialized=True,
            api_mode={"llm": {"mode": "monitor"}, "llm_defaults": {"fail_open": True}},
        )
        clear_inspection_context()
        
        # Mock wrapped async function
        mock_response = MagicMock()
        mock_response.candidates = []
        mock_wrapped = AsyncMock(return_value=mock_response)
        
        # Mock instance
        mock_instance = MagicMock()
        mock_instance.model_name = "gemini-pro"
        
        # Call wrapper
        result = await _wrap_generate_content_async(
            mock_wrapped,
            mock_instance,
            ("Hello",),
            {}
        )
        
        # Verify async inspector was called
        mock_inspector.ainspect_conversation.assert_called()
        assert mock_wrapped.called


class TestVertexAIPatcherSkipConditions:
    """Test conditions where patching is skipped."""

    def test_skips_when_library_not_installed(self):
        """Test graceful skip when vertexai not installed."""
        with patch("aidefense.runtime.agentsec.patchers.vertexai.safe_import", return_value=None):
            result = patch_vertexai()
            assert result is False

    def test_skips_when_already_patched(self):
        """Test skip when already patched."""
        with patch("aidefense.runtime.agentsec.patchers.vertexai.is_patched", return_value=True):
            result = patch_vertexai()
            assert result is True


class TestBuildGoogleAuthHeader:
    """Tests for _build_google_auth_header in _google_common.py."""

    def _setup_google_mocks(self):
        """Create mock google.auth/google.oauth2 modules for tests.

        Returns a dict suitable for ``patch.dict(sys.modules, ...)``.
        The top-level ``google`` mock is included so that
        ``import google.auth`` works even if ``google-auth`` isn't
        installed.
        """
        mock_google = MagicMock()
        mock_google_auth = MagicMock()
        mock_google_auth_transport = MagicMock()
        mock_google_auth_transport_requests = MagicMock()
        mock_google_oauth2 = MagicMock()
        mock_google_oauth2_service_account = MagicMock()
        mock_google_auth_impersonated = MagicMock()

        # Wire up attribute access on the top-level mock
        mock_google.auth = mock_google_auth
        mock_google.auth.transport = mock_google_auth_transport
        mock_google.auth.transport.requests = mock_google_auth_transport_requests
        mock_google.auth.impersonated_credentials = mock_google_auth_impersonated
        mock_google.oauth2 = mock_google_oauth2
        mock_google.oauth2.service_account = mock_google_oauth2_service_account

        return {
            "google": mock_google,
            "google.auth": mock_google_auth,
            "google.auth.transport": mock_google_auth_transport,
            "google.auth.transport.requests": mock_google_auth_transport_requests,
            "google.oauth2": mock_google_oauth2,
            "google.oauth2.service_account": mock_google_oauth2_service_account,
            "google.auth.impersonated_credentials": mock_google_auth_impersonated,
        }

    def test_default_adc(self):
        """No GCP fields: calls google.auth.default()."""
        from aidefense.runtime.agentsec.gateway_settings import GatewaySettings
        import sys

        gw = GatewaySettings(url="https://gw.example.com", auth_mode="google_adc")
        mocks = self._setup_google_mocks()

        mock_creds = MagicMock()
        mock_creds.token = "adc-token-123"
        mocks["google.auth"].default.return_value = (mock_creds, "project")

        with patch.dict(sys.modules, mocks):
            # Re-import to pick up mocked modules
            from aidefense.runtime.agentsec.patchers._google_common import _build_google_auth_header
            result = _build_google_auth_header(gw)

        mocks["google.auth"].default.assert_called_once()
        assert result == {"Authorization": "Bearer adc-token-123"}

    def test_explicit_sa_key_file(self):
        """Uses service_account.Credentials.from_service_account_file."""
        from aidefense.runtime.agentsec.gateway_settings import GatewaySettings
        import sys

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="google_adc",
            gcp_service_account_key_file="/path/to/key.json",
        )
        mocks = self._setup_google_mocks()

        mock_creds = MagicMock()
        mock_creds.token = "sa-token-456"
        mocks["google.oauth2.service_account"].Credentials.from_service_account_file.return_value = mock_creds

        with patch.dict(sys.modules, mocks):
            from aidefense.runtime.agentsec.patchers._google_common import _build_google_auth_header
            result = _build_google_auth_header(gw)

        mocks["google.oauth2.service_account"].Credentials.from_service_account_file.assert_called_once_with(
            "/path/to/key.json",
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        assert result == {"Authorization": "Bearer sa-token-456"}

    def test_sa_impersonation(self):
        """Uses impersonated_credentials.Credentials with ADC base."""
        from aidefense.runtime.agentsec.gateway_settings import GatewaySettings
        import sys

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="google_adc",
            gcp_target_service_account="target-sa@project.iam.gserviceaccount.com",
        )
        mocks = self._setup_google_mocks()

        mock_base_creds = MagicMock()
        mocks["google.auth"].default.return_value = (mock_base_creds, "project")

        mock_impersonated = MagicMock()
        mock_impersonated.token = "impersonated-token-789"
        mocks["google.auth.impersonated_credentials"].Credentials.return_value = mock_impersonated

        with patch.dict(sys.modules, mocks):
            from aidefense.runtime.agentsec.patchers._google_common import _build_google_auth_header
            result = _build_google_auth_header(gw)

        mocks["google.auth.impersonated_credentials"].Credentials.assert_called_once_with(
            source_credentials=mock_base_creds,
            target_principal="target-sa@project.iam.gserviceaccount.com",
            target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        assert result == {"Authorization": "Bearer impersonated-token-789"}

    def test_impersonation_with_explicit_key(self):
        """SA key + impersonation chained together."""
        from aidefense.runtime.agentsec.gateway_settings import GatewaySettings
        import sys

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="google_adc",
            gcp_service_account_key_file="/path/to/key.json",
            gcp_target_service_account="target-sa@project.iam.gserviceaccount.com",
        )
        mocks = self._setup_google_mocks()

        mock_sa_creds = MagicMock()
        mocks["google.oauth2.service_account"].Credentials.from_service_account_file.return_value = mock_sa_creds

        mock_impersonated = MagicMock()
        mock_impersonated.token = "chained-token"
        mocks["google.auth.impersonated_credentials"].Credentials.return_value = mock_impersonated

        with patch.dict(sys.modules, mocks):
            from aidefense.runtime.agentsec.patchers._google_common import _build_google_auth_header
            result = _build_google_auth_header(gw)

        mocks["google.auth.impersonated_credentials"].Credentials.assert_called_once_with(
            source_credentials=mock_sa_creds,
            target_principal="target-sa@project.iam.gserviceaccount.com",
            target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        assert result == {"Authorization": "Bearer chained-token"}


class TestVertexAIGatewayAuth:
    """Tests for auth mode dispatch in gateway handlers."""

    @patch("httpx.Client")
    def test_gateway_google_adc_uses_build_header(self, mock_httpx_client):
        """Verify _build_google_auth_header is called when auth_mode == google_adc."""
        from aidefense.runtime.agentsec.patchers.vertexai import _handle_vertexai_gateway_call
        from aidefense.runtime.agentsec.gateway_settings import GatewaySettings

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="google_adc",
            gcp_project="my-project",
            gcp_location="us-central1",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{"content": {"role": "model", "parts": [{"text": "hi"}]}}]
        }
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_httpx_client.return_value.__exit__ = MagicMock(return_value=False)

        with patch("aidefense.runtime.agentsec.patchers._google_common._build_google_auth_header",
                    return_value={"Authorization": "Bearer adc-tok"}) as mock_build:
            _handle_vertexai_gateway_call("gemini-pro", "Hello", gw)

        mock_build.assert_called_once_with(gw)
        call_kwargs = mock_client_instance.post.call_args
        headers = call_kwargs[1]["headers"] if "headers" in call_kwargs[1] else call_kwargs.kwargs["headers"]
        assert headers["Authorization"] == "Bearer adc-tok"

    @patch("httpx.Client")
    def test_gateway_api_key_uses_bearer(self, mock_httpx_client):
        """Verify Bearer api_key when auth_mode is api_key."""
        from aidefense.runtime.agentsec.patchers.vertexai import _handle_vertexai_gateway_call
        from aidefense.runtime.agentsec.gateway_settings import GatewaySettings

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="api_key",
            api_key="my-api-key",
            gcp_project="my-project",
            gcp_location="us-central1",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{"content": {"role": "model", "parts": [{"text": "hi"}]}}]
        }
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_httpx_client.return_value.__exit__ = MagicMock(return_value=False)

        _handle_vertexai_gateway_call("gemini-pro", "Hello", gw)

        call_kwargs = mock_client_instance.post.call_args
        headers = call_kwargs[1]["headers"] if "headers" in call_kwargs[1] else call_kwargs.kwargs["headers"]
        assert headers["Authorization"] == "Bearer my-api-key"


class TestVertexAIGatewayStreaming:
    """Tests for streaming gateway support."""

    def test_gateway_streaming_does_not_fallback_to_api(self):
        """Verify streaming calls go through gateway, not API mode."""
        from aidefense.runtime.agentsec.patchers.vertexai import (
            _handle_vertexai_gateway_call_streaming,
            _VertexAIResponseWrapper,
        )
        from aidefense.runtime.agentsec.gateway_settings import GatewaySettings

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="google_adc",
            gcp_project="my-project",
            gcp_location="us-central1",
        )

        mock_wrapper = _VertexAIResponseWrapper({
            "candidates": [{"content": {"role": "model", "parts": [{"text": "streamed"}]}}]
        })

        with patch("aidefense.runtime.agentsec.patchers.vertexai._handle_vertexai_gateway_call",
                    return_value=mock_wrapper) as mock_gw_call:
            result = _handle_vertexai_gateway_call_streaming("gemini-pro", "Hello", gw)

        # Should have called the non-streaming gateway handler
        mock_gw_call.assert_called_once()
        # Result should be iterable (fake stream wrapper)
        assert hasattr(result, "__iter__")

    def test_gateway_streaming_returns_iterable(self):
        """Verify streaming response is iterable with chunks."""
        from aidefense.runtime.agentsec.patchers.vertexai import (
            _handle_vertexai_gateway_call_streaming,
            _VertexAIResponseWrapper,
        )
        from aidefense.runtime.agentsec.gateway_settings import GatewaySettings

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="google_adc",
            gcp_project="my-project",
            gcp_location="us-central1",
        )

        mock_wrapper = _VertexAIResponseWrapper({
            "candidates": [{"content": {"role": "model", "parts": [{"text": "hello from gateway"}]}}]
        })

        with patch("aidefense.runtime.agentsec.patchers.vertexai._handle_vertexai_gateway_call",
                    return_value=mock_wrapper):
            result = _handle_vertexai_gateway_call_streaming("gemini-pro", "Hello", gw)

        # Iterate the fake stream
        chunks = list(result)
        assert len(chunks) == 1
        # The single chunk should be the response wrapper
        assert chunks[0].text == "hello from gateway"

    @pytest.mark.asyncio
    async def test_gateway_streaming_async_returns_async_iterable(self):
        """Verify async streaming response is an async iterable with chunks."""
        from aidefense.runtime.agentsec.patchers.vertexai import (
            _handle_vertexai_gateway_call_streaming_async,
            _VertexAIResponseWrapper,
        )
        from aidefense.runtime.agentsec.gateway_settings import GatewaySettings

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="google_adc",
            gcp_project="my-project",
            gcp_location="us-central1",
        )

        mock_wrapper = _VertexAIResponseWrapper({
            "candidates": [{"content": {"role": "model", "parts": [{"text": "async gateway"}]}}]
        })

        with patch("aidefense.runtime.agentsec.patchers.vertexai._handle_vertexai_gateway_call_async",
                    new_callable=AsyncMock, return_value=mock_wrapper):
            result = await _handle_vertexai_gateway_call_streaming_async("gemini-pro", "Hello", gw)

        # Async iterate the fake stream
        chunks = []
        async for chunk in result:
            chunks.append(chunk)
        assert len(chunks) == 1
        assert chunks[0].text == "async gateway"


class TestVertexAIGatewayErrorCases:
    """Tests for error paths in gateway auth."""

    def test_gateway_api_key_missing_raises_error(self):
        """SecurityPolicyError when auth_mode=api_key but api_key is None."""
        from aidefense.runtime.agentsec.patchers.vertexai import _handle_vertexai_gateway_call
        from aidefense.runtime.agentsec.gateway_settings import GatewaySettings

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="api_key",
            api_key=None,
        )
        with pytest.raises(SecurityPolicyError):
            _handle_vertexai_gateway_call("gemini-pro", "Hello", gw)

    def test_gateway_empty_url_raises_error(self):
        """SecurityPolicyError when gateway URL is empty."""
        from aidefense.runtime.agentsec.patchers.vertexai import _handle_vertexai_gateway_call
        from aidefense.runtime.agentsec.gateway_settings import GatewaySettings

        gw = GatewaySettings(
            url="",
            auth_mode="google_adc",
        )
        with pytest.raises(SecurityPolicyError):
            _handle_vertexai_gateway_call("gemini-pro", "Hello", gw)

    @pytest.mark.asyncio
    async def test_gateway_async_api_key_missing_raises_error(self):
        """Async: SecurityPolicyError when auth_mode=api_key but api_key is None."""
        from aidefense.runtime.agentsec.patchers.vertexai import _handle_vertexai_gateway_call_async
        from aidefense.runtime.agentsec.gateway_settings import GatewaySettings

        gw = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="api_key",
            api_key=None,
        )
        with pytest.raises(SecurityPolicyError):
            await _handle_vertexai_gateway_call_async("gemini-pro", "Hello", gw)

    @pytest.mark.asyncio
    async def test_gateway_async_empty_url_raises_error(self):
        """Async: SecurityPolicyError when gateway URL is empty."""
        from aidefense.runtime.agentsec.patchers.vertexai import _handle_vertexai_gateway_call_async
        from aidefense.runtime.agentsec.gateway_settings import GatewaySettings

        gw = GatewaySettings(
            url="",
            auth_mode="google_adc",
        )
        with pytest.raises(SecurityPolicyError):
            await _handle_vertexai_gateway_call_async("gemini-pro", "Hello", gw)





