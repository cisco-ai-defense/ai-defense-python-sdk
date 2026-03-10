"""Gateway settings dataclass for agentsec gateway configuration."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GatewaySettings:
    """Resolved settings for a single gateway connection.

    This is the final, fully-resolved configuration used by patchers
    to make gateway calls. All inheritance and defaults have been applied
    before creating this object.

    Attributes:
        url: The gateway URL to proxy requests through.
        api_key: API key for auth (used when auth_mode="api_key").
            YAML key: ``api_key`` (MCP), ``gateway_api_key`` (LLM).
        api_key_header: Header name used to send the API key (default: "api-key").
            YAML key: ``api_key_header`` (MCP), ``gateway_api_key_header`` (LLM).
        auth_mode: Authentication mode - one of:
            "none" - no authentication (default for MCP gateways)
            "api_key" - API key sent in configurable header (default for LLM gateways)
            "aws_sigv4" - AWS Signature V4 signing
            "google_adc" - Google Application Default Credentials
            "oauth2_client_credentials" - OAuth 2.0 Client Credentials grant
            "client" - forward the client's own auth headers to the gateway as-is
        fail_open: If True, allow the original request on gateway failure.
        timeout: Timeout in seconds for gateway calls.
        retry_total: Total number of retries on failure.
        retry_backoff: Backoff factor between retries.
        retry_status_codes: HTTP status codes that trigger a retry.
        aws_region: AWS region for SigV4 signing (e.g. "us-east-1").
        aws_profile: Named AWS profile from ~/.aws/credentials.
        aws_access_key_id: Explicit AWS access key ID.
        aws_secret_access_key: Explicit AWS secret access key.
        aws_session_token: Explicit AWS session token (temporary credentials).
        aws_role_arn: IAM role ARN for cross-account assume-role.
        gcp_project: GCP project ID for this gateway.
        gcp_location: GCP region/location (e.g. "us-central1").
        gcp_service_account_key_file: Path to a service account JSON key file.
        gcp_target_service_account: SA email for impersonation (cross-project).
        oauth2_token_url: Token endpoint URL for OAuth2 Client Credentials.
        oauth2_client_id: Client ID for OAuth2 Client Credentials.
        oauth2_client_secret: Client secret for OAuth2 Client Credentials.
        oauth2_scopes: Space-separated scopes for OAuth2 Client Credentials.
    """

    url: str
    api_key: Optional[str] = None
    api_key_header: str = "api-key"
    auth_mode: str = "api_key"  # "none" | "api_key" | "aws_sigv4" | "google_adc" | "oauth2_client_credentials" | "client"
    fail_open: bool = True
    timeout: int = 60
    retry_total: int = 3
    retry_backoff: float = 0.5
    retry_status_codes: List[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )

    # AWS SigV4 per-gateway credentials (only used when auth_mode="aws_sigv4")
    aws_region: Optional[str] = None
    aws_profile: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    aws_role_arn: Optional[str] = None

    # Google ADC per-gateway credentials (only used when auth_mode="google_adc")
    gcp_project: Optional[str] = None
    gcp_location: Optional[str] = None
    gcp_service_account_key_file: Optional[str] = None
    gcp_target_service_account: Optional[str] = None

    # Model name override - when set, the gateway request uses this model name
    # instead of the one from the client.  Useful when the gateway connection
    # is configured for a specific model (e.g. Azure deployment "gpt-3.5-turbo")
    # but the application client uses a different model name (e.g. "gpt-4o").
    gateway_model: Optional[str] = None

    # OAuth2 Client Credentials (only used when auth_mode="oauth2_client_credentials")
    oauth2_token_url: Optional[str] = None
    oauth2_client_id: Optional[str] = None
    oauth2_client_secret: Optional[str] = None
    oauth2_scopes: Optional[str] = None
