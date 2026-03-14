# Copyright 2025 Cisco Systems, Inc. and its affiliates
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

"""Base utilities for patching infrastructure."""

import logging
from typing import Any, Optional

from .. import _state
from .._context import get_active_gateway, is_llm_skip_active
from ..decision import Decision
from ..exceptions import SecurityPolicyError
from ..gateway_settings import GatewaySettings

logger = logging.getLogger("aidefense.runtime.agentsec.patchers")


def safe_import(module_name: str) -> Optional[Any]:
    """
    Safely import a module, returning None if not installed.
    
    Args:
        module_name: Full module path to import
        
    Returns:
        The imported module, or None if import fails
    """
    try:
        import importlib
        module = importlib.import_module(module_name)
        logger.debug(f"Successfully imported {module_name}")
        return module
    except ImportError:
        logger.debug(f"Module {module_name} not installed, skipping patch")
        return None


# =========================================================================
# Shared gateway resolver for all LLM patchers
# =========================================================================

def resolve_gateway_settings(provider: str) -> Optional[GatewaySettings]:
    """Determine which LLM gateway to use for the current call.

    This is the shared resolver used by all LLM patchers.  It implements
    the routing logic:

    0. Gate: skip if integration mode is not ``"gateway"`` or if
       ``skip_inspection`` is active.
    1. If a named gateway is active (via ``agentsec.gateway("name")``),
       look it up.  Use it only if its ``provider`` field matches the
       detected provider (or is absent).
    2. Fall back to the default gateway for this provider (the
       ``llm_gateways`` entry with ``provider: X`` and ``default: true``).

    If gateway mode is active but no gateway configuration is found for
    the provider, a :class:`SecurityPolicyError` is raised to prevent
    silent fallback to API mode.

    Args:
        provider: The detected provider name (e.g. ``"openai"``).

    Returns:
        A resolved :class:`GatewaySettings` or ``None`` if gateway mode
        is not active (i.e. integration mode is ``"api"``).

    Raises:
        SecurityPolicyError: If gateway mode is active but no gateway is
            configured for the given provider.
    """
    # Gate: only resolve if gateway mode is active for LLM
    if _state.get_llm_integration_mode() != "gateway":
        return None

    # Gate: gateway mode must be "on"
    if _state.get_gw_llm_mode() == "off":
        return None

    # Respect skip_inspection context
    if is_llm_skip_active():
        return None

    # Step 1: Check named gateway from context var
    active = get_active_gateway()
    if active:
        config = _state.get_llm_gateway(active)
        if config:
            gw_provider = config.get("provider")
            if gw_provider and gw_provider != provider:
                # Provider mismatch -- fall through to provider default
                pass
            else:
                return _state.resolve_llm_gateway_settings(
                    config, provider=gw_provider or provider
                )

    # Step 2: Fall back to the default gateway for this provider
    config = _state.get_default_gateway_for_provider(provider)
    if config:
        return _state.resolve_llm_gateway_settings(config, provider=provider)

    # Gateway mode is active but no gateway found -- raise rather than
    # silently falling back to API mode which would change the security
    # posture without the user's knowledge.
    raise SecurityPolicyError(
        Decision.block(
            reasons=[
                f"Gateway mode enabled but no gateway configured for "
                f"provider '{provider}'"
            ]
        ),
        f"Gateway mode is active but no gateway configuration found for "
        f"provider '{provider}'. Configure a gateway for this provider in "
        f"gateway_mode.llm_gateways or switch to api integration mode.",
    )
