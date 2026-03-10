"""Security utilities for agentsec examples."""

import ipaddress
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class URLValidationError(ValueError):
    """Raised when URL validation fails."""
    pass


def validate_url(url: str) -> str:
    """
    Validate a URL to prevent SSRF attacks.
    
    This function checks that:
    - The URL uses http or https scheme
    - The hostname is not localhost or a loopback address
    - The hostname is not a private IP address
    
    Args:
        url: The URL to validate
        
    Returns:
        The validated URL (unchanged if valid)
        
    Raises:
        URLValidationError: If the URL is invalid or potentially dangerous
    """
    if not url:
        raise URLValidationError("URL cannot be empty")
    
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise URLValidationError(f"Failed to parse URL: {e}")
    
    # Check scheme
    if parsed.scheme not in ('http', 'https'):
        raise URLValidationError(f"Invalid URL scheme: '{parsed.scheme}'. Must be 'http' or 'https'")
    
    # Check hostname exists
    hostname = parsed.hostname
    if not hostname:
        raise URLValidationError("URL must have a hostname")
    
    hostname_lower = hostname.lower()
    
    # Block localhost and loopback addresses
    blocked_hostnames = {'localhost', '127.0.0.1', '::1', '[::1]', '0.0.0.0'}
    if hostname_lower in blocked_hostnames:
        raise URLValidationError(f"Cannot fetch localhost URLs: {hostname}")
    
    # Check for private IP addresses
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private:
            raise URLValidationError(f"Cannot fetch private IP addresses: {hostname}")
        if ip.is_loopback:
            raise URLValidationError(f"Cannot fetch loopback addresses: {hostname}")
        if ip.is_link_local:
            raise URLValidationError(f"Cannot fetch link-local addresses: {hostname}")
        if ip.is_reserved:
            raise URLValidationError(f"Cannot fetch reserved addresses: {hostname}")
    except ValueError:
        # Not an IP address, it's a hostname - that's fine
        pass
    
    # Block internal metadata endpoints (cloud provider metadata services)
    metadata_hostnames = {
        '169.254.169.254',  # AWS/GCP/Azure metadata
        'metadata.google.internal',
        'metadata.google.internal.',
    }
    if hostname_lower in metadata_hostnames:
        raise URLValidationError(f"Cannot fetch cloud metadata endpoints: {hostname}")
    
    logger.debug(f"URL validation passed: {url}")
    return url


def safe_fetch_url_wrapper(fetch_func):
    """
    Decorator to add URL validation to a fetch function.
    
    Usage:
        @safe_fetch_url_wrapper
        def fetch_url(url: str) -> str:
            # fetch implementation
            ...
    """
    def wrapper(url: str, *args, **kwargs):
        validate_url(url)
        return fetch_func(url, *args, **kwargs)
    wrapper.__name__ = fetch_func.__name__
    wrapper.__doc__ = fetch_func.__doc__
    return wrapper
