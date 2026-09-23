# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Opt-in end-to-end tests for the native Anthropic integration.

These tests make real Anthropic and, in gateway mode, AI Defense requests.
They are intentionally skipped unless ``RUN_ANTHROPIC_E2E=1`` is set.  Run
API mode and gateway mode in separate pytest processes because ``protect()``
is intentionally process-global and idempotent.
"""

import os

import pytest


if os.environ.get("RUN_ANTHROPIC_E2E") != "1":
    pytest.skip("set RUN_ANTHROPIC_E2E=1 to run live Anthropic tests", allow_module_level=True)

anthropic = pytest.importorskip("anthropic")

E2E_MODE = os.environ.get("ANTHROPIC_E2E_MODE", "api").lower()
if E2E_MODE not in {"api", "gateway"}:
    pytest.skip("ANTHROPIC_E2E_MODE must be 'api' or 'gateway'", allow_module_level=True)

MODEL = os.environ.get("ANTHROPIC_MODEL")
if not MODEL:
    pytest.skip("ANTHROPIC_MODEL is required for live Anthropic tests", allow_module_level=True)


def _require_environment(*names: str) -> None:
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        pytest.skip("missing live-test environment variables: " + ", ".join(missing))


@pytest.fixture(scope="module")
def anthropic_client():
    """Install one protection configuration for the selected E2E process."""
    _require_environment("ANTHROPIC_API_KEY")

    from aidefense.runtime import agentsec

    if E2E_MODE == "api":
        _require_environment(
            "AI_DEFENSE_API_MODE_LLM_ENDPOINT",
            "AI_DEFENSE_API_MODE_LLM_API_KEY",
        )
        agentsec.protect(
            llm_integration_mode="api",
            api_mode={"llm": {"mode": "monitor"}},
        )
    else:
        gateway_url = os.environ.get("ANTHROPIC_GATEWAY_URL")
        gateway_key = os.environ.get("ANTHROPIC_GATEWAY_API_KEY")
        if not gateway_url or not gateway_key:
            pytest.skip(
                "ANTHROPIC_GATEWAY_URL and ANTHROPIC_GATEWAY_API_KEY are required "
                "for gateway-mode live tests"
            )
        agentsec.protect(
            llm_integration_mode="gateway",
            gateway_mode={
                "llm_defaults": {"fail_open": False},
                "llm_gateways": {
                    "anthropic-e2e": {
                        "gateway_url": gateway_url,
                        "gateway_api_key": gateway_key,
                        "provider": "anthropic",
                        "default": True,
                    }
                },
            },
        )

    assert "anthropic" in agentsec.get_patched_clients()
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _text(response) -> str:
    return "".join(
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    )


def test_sync_messages_create_and_raw_stream(anthropic_client):
    response = anthropic_client.messages.create(
        model=MODEL,
        max_tokens=32,
        system="Reply with exactly the word OK.",
        messages=[{"role": "user", "content": "Say OK."}],
    )
    assert response.role == "assistant"
    assert _text(response)

    events = list(
        anthropic_client.messages.create(
            model=MODEL,
            max_tokens=32,
            messages=[{"role": "user", "content": "Say OK."}],
            stream=True,
        )
    )
    assert any(getattr(event, "type", None) == "message_start" for event in events)
    assert any(getattr(event, "type", None) == "message_stop" for event in events)


def test_sync_messages_stream_helper(anthropic_client):
    with anthropic_client.messages.stream(
        model=MODEL,
        max_tokens=32,
        messages=[{"role": "user", "content": "Say OK."}],
    ) as stream:
        text = "".join(stream.text_stream)
        final_message = stream.get_final_message()

    assert text
    assert final_message.role == "assistant"


@pytest.mark.asyncio
async def test_async_messages_create_and_stream(anthropic_client):
    _require_environment("ANTHROPIC_API_KEY")
    from aidefense.runtime import agentsec

    # The async test shares the module-scoped configuration installed by the
    # synchronous fixture; protect() is intentionally process-global.
    assert "anthropic" in agentsec.get_patched_clients()

    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=32,
            messages=[{"role": "user", "content": "Say OK."}],
        )
        assert response.role == "assistant"
        assert _text(response)

        async with client.messages.stream(
            model=MODEL,
            max_tokens=32,
            messages=[{"role": "user", "content": "Say OK."}],
        ) as stream:
            chunks = []
            async for chunk in stream.text_stream:
                chunks.append(chunk)
            final_message = await stream.get_final_message()

        assert "".join(chunks)
        assert final_message.role == "assistant"
    finally:
        close = getattr(client, "close", None)
        if close is not None:
            await close()
