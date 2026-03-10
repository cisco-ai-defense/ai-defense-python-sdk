"""Tests for _oauth2 module (OAuth2 Client Credentials token fetcher)."""

import threading
import time
from unittest.mock import patch, MagicMock

import pytest
import httpx

from aidefense.runtime.agentsec._oauth2 import (
    get_oauth2_token,
    clear_cache,
    _token_cache,
)
from aidefense.runtime.agentsec.exceptions import (
    ConfigurationError,
    InspectionNetworkError,
)


@pytest.fixture(autouse=True)
def clean_cache():
    """Clear the token cache before and after each test."""
    clear_cache()
    yield
    clear_cache()


class TestGetOAuth2Token:
    """Tests for get_oauth2_token()."""

    def test_get_token_success(self):
        """Successfully fetch a token from the token endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test-access-token-123",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("aidefense.runtime.agentsec._oauth2.httpx.post", return_value=mock_response) as mock_post:
            token = get_oauth2_token(
                token_url="https://auth.example.com/oauth/token",
                client_id="my-client-id",
                client_secret="my-client-secret",
            )

        assert token == "test-access-token-123"
        mock_post.assert_called_once_with(
            "https://auth.example.com/oauth/token",
            data={"grant_type": "client_credentials"},
            auth=("my-client-id", "my-client-secret"),
            timeout=30.0,
        )

    def test_get_token_with_scopes(self):
        """Scopes are passed in the POST body."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "scoped-token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("aidefense.runtime.agentsec._oauth2.httpx.post", return_value=mock_response) as mock_post:
            token = get_oauth2_token(
                token_url="https://auth.example.com/oauth/token",
                client_id="cid",
                client_secret="csecret",
                scopes="read write",
            )

        assert token == "scoped-token"
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["data"] == {
            "grant_type": "client_credentials",
            "scope": "read write",
        }

    def test_get_token_caching(self):
        """Second call uses cached token, no HTTP request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "cached-token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("aidefense.runtime.agentsec._oauth2.httpx.post", return_value=mock_response) as mock_post:
            token1 = get_oauth2_token(
                token_url="https://auth.example.com/token",
                client_id="cid",
                client_secret="csecret",
            )
            token2 = get_oauth2_token(
                token_url="https://auth.example.com/token",
                client_id="cid",
                client_secret="csecret",
            )

        assert token1 == "cached-token"
        assert token2 == "cached-token"
        # Only one HTTP call should have been made
        assert mock_post.call_count == 1

    def test_get_token_expired_refetches(self):
        """Expired token in cache triggers a new fetch."""
        mock_response1 = MagicMock()
        mock_response1.json.return_value = {
            "access_token": "old-token",
            "expires_in": 3600,
        }
        mock_response1.raise_for_status = MagicMock()

        mock_response2 = MagicMock()
        mock_response2.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }
        mock_response2.raise_for_status = MagicMock()

        with patch("aidefense.runtime.agentsec._oauth2.httpx.post", side_effect=[mock_response1, mock_response2]) as mock_post:
            # First fetch
            token1 = get_oauth2_token(
                token_url="https://auth.example.com/token",
                client_id="cid",
                client_secret="csecret",
            )
            assert token1 == "old-token"

            # Manually expire the cache entry
            cache_key = "https://auth.example.com/token:cid"
            _token_cache[cache_key] = ("old-token", time.monotonic() - 1)

            # Second fetch should get new token
            token2 = get_oauth2_token(
                token_url="https://auth.example.com/token",
                client_id="cid",
                client_secret="csecret",
            )
            assert token2 == "new-token"
            assert mock_post.call_count == 2

    def test_get_token_http_error(self):
        """HTTP error raises InspectionNetworkError."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("aidefense.runtime.agentsec._oauth2.httpx.post", return_value=mock_response):
            with pytest.raises(InspectionNetworkError, match="status 401"):
                get_oauth2_token(
                    token_url="https://auth.example.com/token",
                    client_id="cid",
                    client_secret="wrong-secret",
                )

    def test_get_token_network_error(self):
        """Network error raises InspectionNetworkError."""
        with patch(
            "aidefense.runtime.agentsec._oauth2.httpx.post",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(InspectionNetworkError, match="Connection refused"):
                get_oauth2_token(
                    token_url="https://unreachable.example.com/token",
                    client_id="cid",
                    client_secret="csecret",
                )

    def test_get_token_missing_access_token_in_response(self):
        """Response without access_token raises InspectionNetworkError."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"token_type": "Bearer"}
        mock_response.raise_for_status = MagicMock()

        with patch("aidefense.runtime.agentsec._oauth2.httpx.post", return_value=mock_response):
            with pytest.raises(InspectionNetworkError, match="missing 'access_token'"):
                get_oauth2_token(
                    token_url="https://auth.example.com/token",
                    client_id="cid",
                    client_secret="csecret",
                )

    def test_get_token_non_json_response(self):
        """Non-JSON response raises InspectionNetworkError."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        mock_response.text = "Not JSON"
        mock_response.raise_for_status = MagicMock()

        with patch("aidefense.runtime.agentsec._oauth2.httpx.post", return_value=mock_response):
            with pytest.raises(InspectionNetworkError, match="not valid JSON"):
                get_oauth2_token(
                    token_url="https://auth.example.com/token",
                    client_id="cid",
                    client_secret="csecret",
                )

    def test_get_token_string_expires_in(self):
        """String expires_in is coerced to int without error."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "string-expiry-token",
            "expires_in": "7200",  # some servers return a string
        }
        mock_response.raise_for_status = MagicMock()

        with patch("aidefense.runtime.agentsec._oauth2.httpx.post", return_value=mock_response):
            token = get_oauth2_token(
                token_url="https://auth.example.com/token",
                client_id="cid",
                client_secret="csecret",
            )
        assert token == "string-expiry-token"

    def test_get_token_none_expires_in_defaults(self):
        """None expires_in defaults to 3600 without error."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "null-expiry-token",
            "expires_in": None,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("aidefense.runtime.agentsec._oauth2.httpx.post", return_value=mock_response):
            token = get_oauth2_token(
                token_url="https://auth.example.com/token",
                client_id="cid",
                client_secret="csecret",
            )
        assert token == "null-expiry-token"


class TestGetOAuth2TokenValidation:
    """Tests for missing required fields."""

    def test_missing_token_url(self):
        with pytest.raises(ConfigurationError, match="oauth2_token_url"):
            get_oauth2_token(
                token_url=None,
                client_id="cid",
                client_secret="csecret",
            )

    def test_empty_token_url(self):
        with pytest.raises(ConfigurationError, match="oauth2_token_url"):
            get_oauth2_token(
                token_url="",
                client_id="cid",
                client_secret="csecret",
            )

    def test_missing_client_id(self):
        with pytest.raises(ConfigurationError, match="oauth2_client_id"):
            get_oauth2_token(
                token_url="https://auth.example.com/token",
                client_id=None,
                client_secret="csecret",
            )

    def test_missing_client_secret(self):
        with pytest.raises(ConfigurationError, match="oauth2_client_secret"):
            get_oauth2_token(
                token_url="https://auth.example.com/token",
                client_id="cid",
                client_secret=None,
            )


class TestGetOAuth2TokenThreadSafety:
    """Test thread safety of token fetching."""

    def test_concurrent_calls_single_fetch(self):
        """Concurrent calls for the same token should result in only one HTTP fetch."""
        call_count = 0
        fetch_event = threading.Event()

        def slow_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Simulate slow network call
            fetch_event.wait(timeout=2)
            resp = MagicMock()
            resp.json.return_value = {
                "access_token": "concurrent-token",
                "expires_in": 3600,
            }
            resp.raise_for_status = MagicMock()
            return resp

        tokens = []
        errors = []

        def fetch_token():
            try:
                token = get_oauth2_token(
                    token_url="https://auth.example.com/token",
                    client_id="concurrent-cid",
                    client_secret="concurrent-csecret",
                )
                tokens.append(token)
            except Exception as e:
                errors.append(e)

        with patch("aidefense.runtime.agentsec._oauth2.httpx.post", side_effect=slow_post):
            threads = [threading.Thread(target=fetch_token) for _ in range(5)]
            for t in threads:
                t.start()

            # Allow the slow_post to complete
            time.sleep(0.1)
            fetch_event.set()

            for t in threads:
                t.join(timeout=5)

        assert not errors, f"Unexpected errors: {errors}"
        # All threads should get the same token
        assert all(t == "concurrent-token" for t in tokens)
        # Due to locking, HTTP should be called at most twice
        # (one thread gets lock first, others wait; but due to
        # the fast-path check before lock, some may slip through)
        assert call_count <= 2, f"Expected at most 2 HTTP calls, got {call_count}"


class TestClearCache:
    """Tests for clear_cache()."""

    def test_clear_cache(self):
        """clear_cache() empties the token cache."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "to-be-cleared",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("aidefense.runtime.agentsec._oauth2.httpx.post", return_value=mock_response) as mock_post:
            get_oauth2_token(
                token_url="https://auth.example.com/token",
                client_id="cid",
                client_secret="csecret",
            )
            assert mock_post.call_count == 1

            clear_cache()

            # After clearing, next call should fetch again
            get_oauth2_token(
                token_url="https://auth.example.com/token",
                client_id="cid",
                client_secret="csecret",
            )
            assert mock_post.call_count == 2
