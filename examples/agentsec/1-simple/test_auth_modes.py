#!/usr/bin/env python3
# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""
Integration test for AWS and GCP authentication modes.

Tests each auth configuration in both API and gateway mode to verify
that agentsec correctly handles credentials end-to-end.

Usage:
    python test_auth_modes.py                              # Run all
    python test_auth_modes.py --provider bedrock            # AWS only
    python test_auth_modes.py --provider vertex             # GCP only
    python test_auth_modes.py --mode gateway                # Gateway only
    python test_auth_modes.py --mode api                    # API only
    python test_auth_modes.py --auth bedrock_sigv4_default  # Single case
    python test_auth_modes.py -v                            # Verbose

Environment variables (set in .env or export):

  AWS Bedrock:
    BEDROCK_1_GATEWAY_URL              required for all Bedrock tests
    BEDROCK_1_AWS_REGION / AWS_REGION  region (default: us-east-1)
    BEDROCK_1_AWS_PROFILE / AWS_PROFILE  named profile
    BEDROCK_1_AWS_ACCESS_KEY_ID        explicit IAM access key
    BEDROCK_1_AWS_SECRET_ACCESS_KEY    explicit IAM secret key
    BEDROCK_1_AWS_SESSION_TOKEN        STS session token (optional)
    BEDROCK_1_AWS_ROLE_ARN             cross-account assume-role ARN
    BEDROCK_GATEWAY_API_KEY            Bearer API key (non-SigV4 gateway)

  GCP Vertex AI:
    VERTEXAI_1_GATEWAY_URL                          required for all Vertex tests
    VERTEXAI_1_GCP_PROJECT / GOOGLE_CLOUD_PROJECT   GCP project ID
    VERTEXAI_1_GCP_LOCATION / GOOGLE_CLOUD_LOCATION location (default: us-central1)
    VERTEXAI_1_SA_KEY_FILE             service account key file path
    VERTEXAI_1_TARGET_SA               target SA for impersonation
    VERTEXAI_GATEWAY_API_KEY           Bearer API key (non-ADC gateway)
    GOOGLE_AI_SDK                      "vertexai" or "google_genai"
"""

import argparse
import logging
import os
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and val:
                os.environ.setdefault(key, val)


@dataclass
class AuthTestCase:
    name: str
    provider: str  # "bedrock" or "vertex"
    auth_mode: str  # "aws_sigv4", "google_adc", "api_key"
    gateway_config: dict
    model_id: str
    prompt: str = "Say hello in one word."
    skip_reason: Optional[str] = None


def _env(key: str) -> Optional[str]:
    return os.environ.get(key)


def _first_env(*keys: str) -> Optional[str]:
    """Return the first env var that is set, or None."""
    for k in keys:
        v = os.environ.get(k)
        if v:
            return v
    return None


def _require_any_env(*key_groups) -> Optional[str]:
    """Return skip reason if any group has no set var, else None.

    Each argument is either a string (single required var) or a tuple of
    alternatives (at least one must be set).
    """
    missing = []
    for group in key_groups:
        if isinstance(group, str):
            if not _env(group):
                missing.append(group)
        else:
            if not any(_env(k) for k in group):
                missing.append(" or ".join(group))
    if missing:
        return "Missing env: " + ", ".join(missing)
    return None


def build_test_cases() -> list:
    """Build all auth test cases from environment."""
    cases = []

    bedrock_gw_url = _env("BEDROCK_1_GATEWAY_URL")
    bedrock_model = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_region = _first_env("BEDROCK_1_AWS_REGION", "AWS_REGION") or "us-east-1"

    # 1. AWS Bedrock: SigV4 with default credential chain
    cases.append(AuthTestCase(
        name="bedrock_sigv4_default",
        provider="bedrock",
        auth_mode="aws_sigv4",
        model_id=bedrock_model,
        gateway_config={
            "gateway_url": bedrock_gw_url or "",
            "auth_mode": "aws_sigv4",
            "provider": "bedrock",
            "default": True,
            "aws_region": bedrock_region,
        },
        skip_reason=_require_any_env("BEDROCK_1_GATEWAY_URL"),
    ))

    # 2. AWS Bedrock: SigV4 with named profile
    aws_profile = _first_env("BEDROCK_1_AWS_PROFILE", "AWS_PROFILE")
    cases.append(AuthTestCase(
        name="bedrock_sigv4_profile",
        provider="bedrock",
        auth_mode="aws_sigv4",
        model_id=bedrock_model,
        gateway_config={
            "gateway_url": bedrock_gw_url or "",
            "auth_mode": "aws_sigv4",
            "provider": "bedrock",
            "default": True,
            "aws_region": bedrock_region,
            "aws_profile": aws_profile or "",
        },
        skip_reason=(
            _require_any_env("BEDROCK_1_GATEWAY_URL")
            or (None if aws_profile else "Missing env: BEDROCK_1_AWS_PROFILE or AWS_PROFILE")
        ),
    ))

    # 3. AWS Bedrock: SigV4 with explicit keys
    aws_key = _first_env("BEDROCK_1_AWS_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID")
    aws_secret = _first_env("BEDROCK_1_AWS_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY")
    aws_token = _first_env("BEDROCK_1_AWS_SESSION_TOKEN", "AWS_SESSION_TOKEN")
    cases.append(AuthTestCase(
        name="bedrock_sigv4_explicit_keys",
        provider="bedrock",
        auth_mode="aws_sigv4",
        model_id=bedrock_model,
        gateway_config={
            "gateway_url": bedrock_gw_url or "",
            "auth_mode": "aws_sigv4",
            "provider": "bedrock",
            "default": True,
            "aws_region": bedrock_region,
            "aws_access_key_id": aws_key or "",
            "aws_secret_access_key": aws_secret or "",
            "aws_session_token": aws_token or "",
        },
        skip_reason=_require_any_env(
            "BEDROCK_1_GATEWAY_URL",
            ("BEDROCK_1_AWS_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID"),
            ("BEDROCK_1_AWS_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY"),
        ),
    ))

    # 4. AWS Bedrock: SigV4 with assume role
    aws_role = _first_env("BEDROCK_1_AWS_ROLE_ARN", "AWS_ROLE_ARN")
    cases.append(AuthTestCase(
        name="bedrock_sigv4_assume_role",
        provider="bedrock",
        auth_mode="aws_sigv4",
        model_id=bedrock_model,
        gateway_config={
            "gateway_url": bedrock_gw_url or "",
            "auth_mode": "aws_sigv4",
            "provider": "bedrock",
            "default": True,
            "aws_region": bedrock_region,
            "aws_role_arn": aws_role or "",
        },
        skip_reason=_require_any_env(
            "BEDROCK_1_GATEWAY_URL",
            ("BEDROCK_1_AWS_ROLE_ARN", "AWS_ROLE_ARN"),
        ),
    ))

    # 5. AWS Bedrock: api_key (Bearer token)
    cases.append(AuthTestCase(
        name="bedrock_api_key",
        provider="bedrock",
        auth_mode="api_key",
        model_id=bedrock_model,
        gateway_config={
            "gateway_url": bedrock_gw_url or "",
            "auth_mode": "api_key",
            "gateway_api_key": _env("BEDROCK_GATEWAY_API_KEY") or "",
            "provider": "bedrock",
            "default": True,
        },
        skip_reason=_require_any_env("BEDROCK_1_GATEWAY_URL", "BEDROCK_GATEWAY_API_KEY"),
    ))

    # ── GCP Vertex AI ──
    vertex_gw_url = _env("VERTEXAI_1_GATEWAY_URL")
    vertex_model = "gemini-2.5-flash-lite"
    gcp_project = _first_env("VERTEXAI_1_GCP_PROJECT", "GOOGLE_CLOUD_PROJECT")
    gcp_location = _first_env("VERTEXAI_1_GCP_LOCATION", "GOOGLE_CLOUD_LOCATION") or "us-central1"

    def _vertex_base(**overrides):
        base = {
            "gateway_url": vertex_gw_url or "",
            "provider": "vertexai",
            "default": True,
            "sdk": _env("GOOGLE_AI_SDK") or "vertexai",
            "gcp_project": gcp_project or "",
            "gcp_location": gcp_location,
        }
        base.update(overrides)
        return base

    # 6. GCP Vertex: Google ADC (default credentials)
    cases.append(AuthTestCase(
        name="vertex_adc_default",
        provider="vertex",
        auth_mode="google_adc",
        model_id=vertex_model,
        gateway_config=_vertex_base(auth_mode="google_adc"),
        skip_reason=_require_any_env(
            "VERTEXAI_1_GATEWAY_URL",
            ("VERTEXAI_1_GCP_PROJECT", "GOOGLE_CLOUD_PROJECT"),
        ),
    ))

    # 7. GCP Vertex: Google ADC with SA key file
    sa_key_file = _first_env("VERTEXAI_1_SA_KEY_FILE", "GCP_SERVICE_ACCOUNT_KEY_FILE")
    cases.append(AuthTestCase(
        name="vertex_adc_sa_key_file",
        provider="vertex",
        auth_mode="google_adc",
        model_id=vertex_model,
        gateway_config=_vertex_base(
            auth_mode="google_adc",
            gcp_service_account_key_file=sa_key_file or "",
        ),
        skip_reason=_require_any_env(
            "VERTEXAI_1_GATEWAY_URL",
            ("VERTEXAI_1_GCP_PROJECT", "GOOGLE_CLOUD_PROJECT"),
            ("VERTEXAI_1_SA_KEY_FILE", "GCP_SERVICE_ACCOUNT_KEY_FILE"),
        ),
    ))

    # 8. GCP Vertex: Google ADC with impersonation
    target_sa = _first_env("VERTEXAI_1_TARGET_SA", "GCP_TARGET_SERVICE_ACCOUNT")
    cases.append(AuthTestCase(
        name="vertex_adc_impersonation",
        provider="vertex",
        auth_mode="google_adc",
        model_id=vertex_model,
        gateway_config=_vertex_base(
            auth_mode="google_adc",
            gcp_target_service_account=target_sa or "",
        ),
        skip_reason=_require_any_env(
            "VERTEXAI_1_GATEWAY_URL",
            ("VERTEXAI_1_GCP_PROJECT", "GOOGLE_CLOUD_PROJECT"),
            ("VERTEXAI_1_TARGET_SA", "GCP_TARGET_SERVICE_ACCOUNT"),
        ),
    ))

    # 9. GCP Vertex: api_key (Bearer token)
    cases.append(AuthTestCase(
        name="vertex_api_key",
        provider="vertex",
        auth_mode="api_key",
        model_id=vertex_model,
        gateway_config=_vertex_base(
            auth_mode="api_key",
            gateway_api_key=_env("VERTEXAI_GATEWAY_API_KEY") or "",
        ),
        skip_reason=_require_any_env(
            "VERTEXAI_1_GATEWAY_URL",
            "VERTEXAI_GATEWAY_API_KEY",
            ("VERTEXAI_1_GCP_PROJECT", "GOOGLE_CLOUD_PROJECT"),
        ),
    ))

    return cases


def run_bedrock_call(model_id: str, prompt: str):
    """Make a Bedrock converse call and return the response text."""
    import boto3
    client = boto3.client(
        "bedrock-runtime",
        region_name=_first_env("BEDROCK_1_AWS_REGION", "AWS_REGION") or "us-east-1",
    )
    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
    )
    return response["output"]["message"]["content"][0]["text"]


def run_vertex_call(model_id: str, prompt: str):
    """Make a Vertex AI generate_content call and return the response text."""
    gcp_project = _first_env("VERTEXAI_1_GCP_PROJECT", "GOOGLE_CLOUD_PROJECT")
    gcp_location = _first_env("VERTEXAI_1_GCP_LOCATION", "GOOGLE_CLOUD_LOCATION") or "us-central1"
    sdk = _env("GOOGLE_AI_SDK") or "vertexai"
    if sdk == "vertexai":
        import vertexai
        from vertexai.generative_models import GenerativeModel
        vertexai.init(project=gcp_project, location=gcp_location)
        model = GenerativeModel(model_id)
        response = model.generate_content(prompt)
        return response.text
    else:
        from google import genai
        client = genai.Client(
            vertexai=True,
            project=gcp_project,
            location=gcp_location,
        )
        response = client.models.generate_content(model=model_id, contents=prompt)
        return response.text


def run_single_test(case: AuthTestCase, mode: str, verbose: bool = False) -> dict:
    """Run a single auth test case. Returns {passed, error, duration_s}."""
    import aidefense.runtime.agentsec as agentsec
    from aidefense.runtime.agentsec import _state

    label = f"{case.name} [{mode}]"
    start = time.time()

    try:
        _state.reset()

        gw_name = f"{case.provider}-test"
        gateway_config = {
            "llm_gateways": {gw_name: case.gateway_config},
        }

        agentsec.protect(
            llm_integration_mode=mode,
            gateway_mode=gateway_config if mode == "gateway" else None,
        )

        if case.provider == "bedrock":
            result = run_bedrock_call(case.model_id, case.prompt)
        else:
            result = run_vertex_call(case.model_id, case.prompt)

        duration = time.time() - start
        print(f"  \033[32m\u2713 PASSED\033[0m  {label}  ({duration:.1f}s)")
        if verbose:
            print(f"           Response: {result[:80]}...")
        return {"passed": True, "error": None, "duration_s": duration}

    except Exception as e:
        duration = time.time() - start
        print(f"  \033[31m\u2717 FAILED\033[0m  {label}  ({duration:.1f}s)")
        print(f"           {type(e).__name__}: {e}")
        if verbose:
            traceback.print_exc()
        return {"passed": False, "error": str(e), "duration_s": duration}
    finally:
        try:
            _state.reset()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="Test AWS/GCP auth modes for agentsec LLM gateways",
    )
    parser.add_argument("--provider", choices=["bedrock", "vertex"],
                        help="Test only this provider")
    parser.add_argument("--mode", choices=["api", "gateway"],
                        help="Test only this integration mode")
    parser.add_argument("--auth",
                        help="Run only the named test case (e.g. bedrock_sigv4_default)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show debug logs and full responses")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    cases = build_test_cases()

    if args.provider:
        cases = [c for c in cases if c.provider == args.provider]
    if args.auth:
        cases = [c for c in cases if c.name == args.auth]

    modes = [args.mode] if args.mode else ["api", "gateway"]

    print("=" * 60)
    print("  Agentsec LLM Auth Mode Integration Tests")
    print("=" * 60)
    print(f"  Providers: {args.provider or 'all'}")
    print(f"  Modes:     {', '.join(modes)}")
    print(f"  Cases:     {len(cases)}")
    print("=" * 60)
    print()

    passed = 0
    failed = 0
    skipped = 0
    results = []

    for case in cases:
        for mode in modes:
            if case.skip_reason:
                skipped += 1
                print(f"  \033[33m\u2298 SKIP\033[0m    {case.name} [{mode}]  ({case.skip_reason})")
                continue

            result = run_single_test(case, mode, verbose=args.verbose)
            results.append({"case": case.name, "mode": mode, **result})
            if result["passed"]:
                passed += 1
            else:
                failed += 1

    print()
    print("=" * 60)
    print("  Results")
    print("=" * 60)
    print(f"  Passed:  \033[32m{passed}\033[0m")
    print(f"  Failed:  \033[31m{failed}\033[0m")
    print(f"  Skipped: \033[33m{skipped}\033[0m")
    print("=" * 60)

    if failed > 0:
        print()
        print("  Failed tests:")
        for r in results:
            if not r["passed"]:
                print(f"    - {r['case']} [{r['mode']}]: {r['error']}")
        sys.exit(1)
    elif passed == 0:
        print()
        print("  \033[33mNo tests ran. Set environment variables to enable tests.\033[0m")
        print("  See --help for required env vars.")
        sys.exit(0)
    else:
        print()
        print(f"  \033[32mAll {passed} tests passed!\033[0m")
        sys.exit(0)


if __name__ == "__main__":
    main()
