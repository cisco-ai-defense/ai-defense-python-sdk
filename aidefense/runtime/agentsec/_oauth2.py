"""Thread-safe OAuth2 Client Credentials token fetcher with caching.

Used by MCP gateway mode when ``auth_mode`` is ``"oauth2_client_credentials"``.
Tokens are cached in-memory and refreshed automatically when they expire.
"""

import logging
import threading
import time
from typing import Dict, Optional, Tuple

import httpx

from .exceptions import ConfigurationError, InspectionNetworkError

logger = logging.getLogger("aidefense.runtime.agentsec._oauth2")

# Cache: key = "(token_url, client_id)" -> (access_token, expiry_timestamp)
_token_cache: Dict[str, Tuple[str, float]] = {}
_token_lock = threading.Lock()


def get_oauth2_token(
    token_url: Optional[str],
    client_id: Optional[str],
    client_secret: Optional[str],
    scopes: Optional[str] = None,
) -> str:
    """Fetch an OAuth2 access token using the Client Credentials grant.

    Tokens are cached in-memory and reused until they expire (with a 60-second
    safety buffer).  The implementation is thread-safe — concurrent callers will
    wait for the first fetch to complete rather than issuing duplicate requests.

    Args:
        token_url: The OAuth2 token endpoint URL.
        client_id: The client ID.
        client_secret: The client secret.
        scopes: Optional space-separated scopes string.

    Returns:
        The access token string.

    Raises:
        ConfigurationError: If any required field is missing.
        InspectionNetworkError: If the HTTP request to the token endpoint fails.
    """
    # Validate required fields
    if not token_url:
        raise ConfigurationError(
            "oauth2_token_url is required when auth_mode is 'oauth2_client_credentials'"
        )
    if not client_id:
        raise ConfigurationError(
            "oauth2_client_id is required when auth_mode is 'oauth2_client_credentials'"
        )
    if not client_secret:
        raise ConfigurationError(
            "oauth2_client_secret is required when auth_mode is 'oauth2_client_credentials'"
        )

    cache_key = f"{token_url}:{client_id}"

    # Fast path: check cache without lock
    cached = _token_cache.get(cache_key)
    if cached is not None:
        token, expiry = cached
        if time.monotonic() < expiry:
            return token

    # Slow path: acquire lock and fetch
    with _token_lock:
        # Double-check after acquiring lock (another thread may have fetched)
        cached = _token_cache.get(cache_key)
        if cached is not None:
            token, expiry = cached
            if time.monotonic() < expiry:
                return token

        # Fetch a new token
        return _fetch_and_cache_token(cache_key, token_url, client_id, client_secret, scopes)


def _fetch_and_cache_token(
    cache_key: str,
    token_url: str,
    client_id: str,
    client_secret: str,
    scopes: Optional[str],
) -> str:
    """Perform the actual HTTP POST to fetch a token and store it in cache.

    Must be called while holding ``_token_lock``.
    """
    data: Dict[str, str] = {"grant_type": "client_credentials"}
    if scopes:
        data["scope"] = scopes

    try:
        logger.debug(f"Fetching OAuth2 token from {token_url}")
        resp = httpx.post(
            token_url,
            data=data,
            auth=(client_id, client_secret),
            timeout=30.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise InspectionNetworkError(
            f"OAuth2 token request failed with status {exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        raise InspectionNetworkError(
            f"OAuth2 token request failed: {exc}"
        ) from exc

    try:
        body = resp.json()
    except Exception as exc:
        raise InspectionNetworkError(
            "OAuth2 token response is not valid JSON"
        ) from exc

    access_token = body.get("access_token")
    if not access_token:
        raise InspectionNetworkError(
            f"OAuth2 token response missing 'access_token' (keys: {list(body.keys())})"
        )

    # Coerce expires_in to int — some servers return a string or None
    raw_expires_in = body.get("expires_in", 3600)
    try:
        expires_in = int(raw_expires_in) if raw_expires_in is not None else 3600
    except (TypeError, ValueError):
        logger.warning(f"Invalid expires_in value '{raw_expires_in}', defaulting to 3600s")
        expires_in = 3600
    # Cache with a 60-second buffer before actual expiry
    expiry = time.monotonic() + max(expires_in - 60, 0)

    _token_cache[cache_key] = (access_token, expiry)
    logger.debug(f"OAuth2 token cached (expires_in={expires_in}s)")

    return access_token


def clear_cache() -> None:
    """Clear the token cache. Useful for testing."""
    with _token_lock:
        _token_cache.clear()
