"""Tests for GatewaySettings dataclass."""

import pytest
from aidefense.runtime.agentsec.gateway_settings import GatewaySettings


class TestGatewaySettings:
    """Tests for GatewaySettings dataclass construction and defaults."""

    def test_minimal_construction(self):
        """Only url is required; everything else has defaults."""
        gs = GatewaySettings(url="https://gw.example.com")
        assert gs.url == "https://gw.example.com"
        assert gs.api_key is None
        assert gs.auth_mode == "api_key"
        assert gs.fail_open is True
        assert gs.timeout == 60
        assert gs.retry_total == 3
        assert gs.retry_backoff == 0.5
        assert gs.retry_status_codes == [429, 500, 502, 503, 504]

    def test_full_construction(self):
        """All fields can be set explicitly."""
        gs = GatewaySettings(
            url="https://gw.example.com",
            api_key="secret",
            auth_mode="aws_sigv4",
            fail_open=False,
            timeout=10,
            retry_total=5,
            retry_backoff=2.0,
            retry_status_codes=[500],
        )
        assert gs.url == "https://gw.example.com"
        assert gs.api_key == "secret"
        assert gs.auth_mode == "aws_sigv4"
        assert gs.fail_open is False
        assert gs.timeout == 10
        assert gs.retry_total == 5
        assert gs.retry_backoff == 2.0
        assert gs.retry_status_codes == [500]

    def test_retry_status_codes_mutable_default(self):
        """Each instance gets its own copy of retry_status_codes."""
        gs1 = GatewaySettings(url="a")
        gs2 = GatewaySettings(url="b")
        gs1.retry_status_codes.append(999)
        assert 999 not in gs2.retry_status_codes

    def test_google_adc_auth_mode(self):
        gs = GatewaySettings(url="https://gw.example.com", auth_mode="google_adc")
        assert gs.auth_mode == "google_adc"

    def test_aws_fields_default_none(self):
        """All six AWS fields default to None on minimal construction."""
        gs = GatewaySettings(url="https://gw.example.com")
        assert gs.aws_region is None
        assert gs.aws_profile is None
        assert gs.aws_access_key_id is None
        assert gs.aws_secret_access_key is None
        assert gs.aws_session_token is None
        assert gs.aws_role_arn is None

    def test_aws_sigv4_full_construction(self):
        """All six AWS fields can be set explicitly."""
        gs = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="aws_sigv4",
            aws_region="eu-west-1",
            aws_profile="team-b",
            aws_access_key_id="AKIAEXAMPLE",
            aws_secret_access_key="secret123",
            aws_session_token="token456",
            aws_role_arn="arn:aws:iam::123456789012:role/test-role",
        )
        assert gs.aws_region == "eu-west-1"
        assert gs.aws_profile == "team-b"
        assert gs.aws_access_key_id == "AKIAEXAMPLE"
        assert gs.aws_secret_access_key == "secret123"
        assert gs.aws_session_token == "token456"
        assert gs.aws_role_arn == "arn:aws:iam::123456789012:role/test-role"

    def test_aws_profile_construction(self):
        """Construct with just aws_region + aws_profile."""
        gs = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="aws_sigv4",
            aws_region="us-west-2",
            aws_profile="prod-account",
        )
        assert gs.aws_region == "us-west-2"
        assert gs.aws_profile == "prod-account"
        assert gs.aws_access_key_id is None
        assert gs.aws_secret_access_key is None

    def test_aws_explicit_keys_construction(self):
        """Construct with explicit keys and optional session token."""
        gs = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="aws_sigv4",
            aws_region="us-east-1",
            aws_access_key_id="AKIAEXAMPLE",
            aws_secret_access_key="secret",
            aws_session_token="tok",
        )
        assert gs.aws_access_key_id == "AKIAEXAMPLE"
        assert gs.aws_secret_access_key == "secret"
        assert gs.aws_session_token == "tok"
        assert gs.aws_profile is None

    def test_aws_role_arn_construction(self):
        """Construct with aws_role_arn for cross-account assume-role."""
        gs = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="aws_sigv4",
            aws_role_arn="arn:aws:iam::999999999999:role/cross-role",
        )
        assert gs.aws_role_arn == "arn:aws:iam::999999999999:role/cross-role"

    # ---- GCP fields ----

    def test_gcp_fields_default_none(self):
        """All four GCP fields default to None on minimal construction."""
        gs = GatewaySettings(url="https://gw.example.com")
        assert gs.gcp_project is None
        assert gs.gcp_location is None
        assert gs.gcp_service_account_key_file is None
        assert gs.gcp_target_service_account is None

    def test_gcp_adc_full_construction(self):
        """All four GCP fields can be set explicitly."""
        gs = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="google_adc",
            gcp_project="my-project",
            gcp_location="us-central1",
            gcp_service_account_key_file="/path/to/key.json",
            gcp_target_service_account="sa@project.iam.gserviceaccount.com",
        )
        assert gs.gcp_project == "my-project"
        assert gs.gcp_location == "us-central1"
        assert gs.gcp_service_account_key_file == "/path/to/key.json"
        assert gs.gcp_target_service_account == "sa@project.iam.gserviceaccount.com"

    def test_gcp_project_location_construction(self):
        """Construct with just gcp_project + gcp_location."""
        gs = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="google_adc",
            gcp_project="my-project",
            gcp_location="europe-west4",
        )
        assert gs.gcp_project == "my-project"
        assert gs.gcp_location == "europe-west4"
        assert gs.gcp_service_account_key_file is None
        assert gs.gcp_target_service_account is None

    def test_gcp_service_account_key_construction(self):
        """Construct with service account key file."""
        gs = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="google_adc",
            gcp_service_account_key_file="/path/to/key.json",
        )
        assert gs.gcp_service_account_key_file == "/path/to/key.json"
        assert gs.gcp_project is None

    def test_gcp_impersonation_construction(self):
        """Construct with target service account for impersonation."""
        gs = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="google_adc",
            gcp_target_service_account="sa@project.iam.gserviceaccount.com",
        )
        assert gs.gcp_target_service_account == "sa@project.iam.gserviceaccount.com"

    # ---- auth_mode: none ----

    def test_auth_mode_none(self):
        """auth_mode='none' is accepted."""
        gs = GatewaySettings(url="https://gw.example.com", auth_mode="none")
        assert gs.auth_mode == "none"
        assert gs.api_key is None

    # ---- OAuth2 Client Credentials fields ----

    def test_oauth2_fields_default_none(self):
        """All four OAuth2 fields default to None on minimal construction."""
        gs = GatewaySettings(url="https://gw.example.com")
        assert gs.oauth2_token_url is None
        assert gs.oauth2_client_id is None
        assert gs.oauth2_client_secret is None
        assert gs.oauth2_scopes is None

    def test_oauth2_full_construction(self):
        """All four OAuth2 fields can be set explicitly."""
        gs = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="oauth2_client_credentials",
            oauth2_token_url="https://auth.example.com/oauth/token",
            oauth2_client_id="my-client-id",
            oauth2_client_secret="my-client-secret",
            oauth2_scopes="read write",
        )
        assert gs.auth_mode == "oauth2_client_credentials"
        assert gs.oauth2_token_url == "https://auth.example.com/oauth/token"
        assert gs.oauth2_client_id == "my-client-id"
        assert gs.oauth2_client_secret == "my-client-secret"
        assert gs.oauth2_scopes == "read write"

    def test_auth_mode_oauth2(self):
        """auth_mode='oauth2_client_credentials' is accepted."""
        gs = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="oauth2_client_credentials",
        )
        assert gs.auth_mode == "oauth2_client_credentials"

    def test_oauth2_partial_construction(self):
        """OAuth2 fields can be set partially (e.g. no scopes)."""
        gs = GatewaySettings(
            url="https://gw.example.com",
            auth_mode="oauth2_client_credentials",
            oauth2_token_url="https://auth.example.com/token",
            oauth2_client_id="cid",
            oauth2_client_secret="csecret",
        )
        assert gs.oauth2_token_url == "https://auth.example.com/token"
        assert gs.oauth2_scopes is None
