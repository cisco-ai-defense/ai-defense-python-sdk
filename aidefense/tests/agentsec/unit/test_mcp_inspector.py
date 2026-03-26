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

"""Tests for MCPInspector with real API integration.

MCPInspector uses MCPInspectionClient; tests mock _get_mcp_client where needed.
"""

import os
from unittest.mock import patch, MagicMock
import pytest
import httpx

from aidefense.runtime.agentsec.inspectors.api_mcp import (
    MCPInspector,
    _mcp_inspect_response_to_decision,
    _result_to_content_dict,
    _request_params_for_method,
)
from aidefense.runtime.agentsec.decision import Decision
from aidefense.runtime.agentsec.exceptions import (
    SecurityPolicyError,
    InspectionTimeoutError,
    InspectionNetworkError,
)
from aidefense.runtime.models import InspectResponse, Action, Classification
from aidefense.runtime.mcp_models import MCPInspectResponse

API_KEY_64 = "x" * 64


def _mcp_allow():
    return MCPInspectResponse(
        result=InspectResponse(
            classifications=[],
            is_safe=True,
            action=Action.ALLOW,
        ),
        id=1,
    )


def _mcp_block(reasons=None):
    return MCPInspectResponse(
        result=InspectResponse(
            classifications=[Classification.SECURITY_VIOLATION],
            is_safe=False,
            action=Action.BLOCK,
            explanation=reasons[0] if reasons else "policy violation",
        ),
        id=1,
    )


class TestMCPInspectorConstructor:
    """Test MCPInspector constructor and initialization (Task Group 2)."""

    def test_constructor_with_explicit_params(self):
        """Test constructor with explicit api_key and endpoint params."""
        inspector = MCPInspector(
            api_key="explicit-key",
            endpoint="https://explicit.example.com",
            timeout_ms=2000,
            retry_attempts=3,
            fail_open=False,
        )
        
        assert inspector.api_key == "explicit-key"
        assert inspector.endpoint == "https://explicit.example.com"
        assert inspector.timeout_ms == 2000
        assert inspector.retry_attempts == 3
        assert inspector.fail_open is False
        inspector.close()

    def test_constructor_env_var_fallback_mcp_specific(self):
        """Test constructor falls back to MCP-specific env vars."""
        env_vars = {
            "AI_DEFENSE_API_MODE_MCP_API_KEY": "mcp-key",
            "AI_DEFENSE_API_MODE_MCP_ENDPOINT": "https://mcp.example.com",
            "AI_DEFENSE_API_MODE_LLM_API_KEY": "general-key",
            "AI_DEFENSE_API_MODE_LLM_ENDPOINT": "https://general.example.com",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            inspector = MCPInspector()
            
            # Should use MCP-specific vars
            assert inspector.api_key == "mcp-key"
            assert inspector.endpoint == "https://mcp.example.com"
            inspector.close()

    def test_constructor_no_llm_env_var_fallback(self):
        """Test constructor does NOT fall back to LLM env vars when MCP not set."""
        env_vars = {
            "AI_DEFENSE_API_MODE_LLM_API_KEY": "general-key",
            "AI_DEFENSE_API_MODE_LLM_ENDPOINT": "https://general.example.com",
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            os.environ.pop("AI_DEFENSE_API_MODE_MCP_API_KEY", None)
            os.environ.pop("AI_DEFENSE_API_MODE_MCP_ENDPOINT", None)
            
            inspector = MCPInspector()
            
            assert inspector.api_key is None
            assert inspector.endpoint is None
            inspector.close()

    def test_constructor_defaults(self):
        """Test constructor default values."""
        # Clear all env vars
        with patch.dict(os.environ, {}, clear=False):
            for var in ["AI_DEFENSE_API_MODE_MCP_API_KEY", "AI_DEFENSE_API_MODE_MCP_ENDPOINT",
                       "AI_DEFENSE_API_MODE_LLM_API_KEY", "AI_DEFENSE_API_MODE_LLM_ENDPOINT"]:
                os.environ.pop(var, None)
            
            inspector = MCPInspector()
            
            assert inspector.api_key is None
            assert inspector.endpoint is None
            # Default timeout from api_mode.mcp_defaults (5 seconds = 5000 ms)
            assert inspector.timeout_ms == 5000
            assert inspector.retry_attempts == 2  # api_mcp default
            assert inspector.fail_open is True
            # _request_id_counter is now itertools.count() for thread safety
            assert next(inspector._request_id_counter) == 1
            inspector.close()

    def test_mcp_client_lazy_created(self):
        """Test that MCP client is created lazily (not in __init__)."""
        inspector = MCPInspector(api_key=API_KEY_64, endpoint="https://test.com")
        assert inspector._mcp_client is None
        assert inspector._mcp_client_lock is not None
        inspector.close()


class TestMCPInspectorRequestBuilding:
    """Test result/params helpers used for MCP inspection."""

    def test_result_to_content_dict_string(self):
        """Test _result_to_content_dict with string result."""
        out = _result_to_content_dict("Hello, world!")
        assert out["content"][0]["type"] == "text"
        assert out["content"][0]["text"] == "Hello, world!"

    def test_result_to_content_dict_mcp_result_passthrough(self):
        """Test _result_to_content_dict with MCP result (dict with content) passed as-is."""
        result = {"content": [{"type": "text", "text": "ok"}, {"type": "image", "data": "x", "mimeType": "image/png"}], "isError": False}
        out = _result_to_content_dict(result)
        assert out is result
        assert out["content"][0]["text"] == "ok"
        assert out["content"][1]["type"] == "image"

    def test_result_to_content_dict_dict(self):
        """Test _result_to_content_dict with dict result (single content item, passed as-is)."""
        result = {"status": "success", "data": [1, 2, 3]}
        out = _result_to_content_dict(result)
        assert out["content"] == [result]

    def test_result_to_content_dict_list(self):
        """Test _result_to_content_dict with list result (content array, passed as-is)."""
        result = [{"type": "text", "text": "hi"}, {"type": "image", "data": "base64..."}]
        out = _result_to_content_dict(result)
        assert out["content"] == result

    def test_request_params_tools_call(self):
        """Test _request_params_for_method for tools/call."""
        params = _request_params_for_method("tools/call", "search_docs", {"query": "test"})
        assert params["name"] == "search_docs"
        assert params["arguments"] == {"query": "test"}

    def test_request_params_resources_read(self):
        """Test _request_params_for_method for resources/read."""
        params = _request_params_for_method("resources/read", "file:///config.yaml", {})
        assert params["uri"] == "file:///config.yaml"

    def test_request_params_prompts_get(self):
        """Test _request_params_for_method for prompts/get."""
        params = _request_params_for_method("prompts/get", "code_review", {"lang": "python"})
        assert params["name"] == "code_review"
        assert params["arguments"] == {"lang": "python"}


class TestMCPInspectorResponseParsing:
    """Test _mcp_inspect_response_to_decision mapping."""

    def test_parse_allow_response(self):
        """Test parsing Allow response."""
        mcp_resp = _mcp_allow()
        decision = _mcp_inspect_response_to_decision(mcp_resp)
        assert decision.action == "allow"

    def test_parse_block_response_by_action(self):
        """Test parsing Block response."""
        mcp_resp = _mcp_block(["Code Detection: SECURITY_VIOLATION"])
        decision = _mcp_inspect_response_to_decision(mcp_resp)
        assert decision.action == "block"
        assert any("SECURITY_VIOLATION" in r for r in decision.reasons)

    def test_parse_block_response_by_is_safe(self):
        """Test parsing block when is_safe is False."""
        mcp_resp = MCPInspectResponse(
            result=InspectResponse(
                classifications=[],
                is_safe=False,
                action=Action.ALLOW,
                explanation="Potentially unsafe content",
            ),
            id=1,
        )
        decision = _mcp_inspect_response_to_decision(mcp_resp)
        assert decision.action == "block"
        assert "Potentially unsafe content" in decision.reasons

    def test_parse_response_with_attack_technique(self):
        """Test parsing response with attack technique in explanation."""
        mcp_resp = MCPInspectResponse(
            result=InspectResponse(
                classifications=[Classification.SECURITY_VIOLATION],
                is_safe=False,
                action=Action.BLOCK,
                explanation="SQL_INJECTION detected",
            ),
            id=1,
        )
        decision = _mcp_inspect_response_to_decision(mcp_resp)
        assert decision.action == "block"
        assert any("SQL_INJECTION" in r for r in decision.reasons)


class TestMCPInspectorInspectRequest:
    """Test inspect_request method (Task Group 3)."""

    def test_inspect_request_no_api_configured(self):
        """Test inspect_request allows when no API configured."""
        with patch.dict(os.environ, {}, clear=False):
            for var in ["AI_DEFENSE_API_MODE_MCP_API_KEY", "AI_DEFENSE_API_MODE_MCP_ENDPOINT",
                       "AI_DEFENSE_API_MODE_LLM_API_KEY", "AI_DEFENSE_API_MODE_LLM_ENDPOINT"]:
                os.environ.pop(var, None)
            
            inspector = MCPInspector()
            
            decision = inspector.inspect_request(
                tool_name="test_tool",
                arguments={"arg": "value"},
                metadata={},
            )
            
            assert decision.action == "allow"
            inspector.close()

    def test_inspect_request_allow(self):
        """Test inspect_request returns allow for safe request."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.return_value = _mcp_allow()
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_request(
                tool_name="search_docs",
                arguments={"query": "safe query"},
                metadata={},
            )
            assert decision.action == "allow"
        inspector.close()

    def test_inspect_request_block(self):
        """Test inspect_request returns block for unsafe request."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.return_value = _mcp_block(["Violence: SAFETY_VIOLATION"])
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_request(
                tool_name="search_docs",
                arguments={"query": "how to make a bomb"},
                metadata={},
            )
            assert decision.action == "block"
        inspector.close()

    def test_inspect_request_api_error_fail_open_true(self):
        """Test inspect_request allows on API error when fail_open=True."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.side_effect = httpx.ConnectError("Connection failed")
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_request(
                tool_name="test_tool",
                arguments={},
                metadata={},
            )
            assert decision.action == "allow"
            assert any("fail_open" in r for r in decision.reasons)
        inspector.close()

    def test_inspect_request_api_error_fail_open_false(self):
        """Test inspect_request raises InspectionNetworkError when fail_open=False."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            fail_open=False,
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.side_effect = httpx.ConnectError("Connection failed")
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            with pytest.raises(InspectionNetworkError):
                inspector.inspect_request(
                    tool_name="test_tool",
                    arguments={},
                    metadata={},
                )
        inspector.close()

    def test_inspect_request_prompts_get(self):
        """Test inspect_request with prompts/get method."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
        )
        mock_client = MagicMock()
        mock_client.inspect.return_value = _mcp_allow()
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_request(
                tool_name="code_review_prompt",
                arguments={"language": "python"},
                metadata={},
                method="prompts/get",
            )
            assert decision.action == "allow"
            mock_client.inspect.assert_called_once()
            call_msg = mock_client.inspect.call_args[0][0]
            assert call_msg.method == "prompts/get"
        inspector.close()

    def test_inspect_request_resources_read(self):
        """Test inspect_request with resources/read method."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
        )
        mock_client = MagicMock()
        mock_client.inspect_resource_read.return_value = _mcp_allow()
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_request(
                tool_name="file:///config.yaml",
                arguments={},
                metadata={},
                method="resources/read",
            )
            assert decision.action == "allow"
            mock_client.inspect_resource_read.assert_called_once()
            assert mock_client.inspect_resource_read.call_args[1]["uri"] == "file:///config.yaml"
        inspector.close()


class TestMCPInspectorInspectResponse:
    """Test inspect_response method (Task Group 4)."""

    def test_inspect_response_no_api_configured(self):
        """Test inspect_response allows when no API configured."""
        with patch.dict(os.environ, {}, clear=False):
            for var in ["AI_DEFENSE_API_MODE_MCP_API_KEY", "AI_DEFENSE_API_MODE_MCP_ENDPOINT",
                       "AI_DEFENSE_API_MODE_LLM_API_KEY", "AI_DEFENSE_API_MODE_LLM_ENDPOINT"]:
                os.environ.pop(var, None)
            
            inspector = MCPInspector()
            
            decision = inspector.inspect_response(
                tool_name="test_tool",
                arguments={},
                result="Some result",
                metadata={},
            )
            
            assert decision.action == "allow"
            inspector.close()

    def test_inspect_response_allow(self):
        """Test inspect_response returns allow for safe response."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
        )
        mock_client = MagicMock()
        mock_client.inspect_response.return_value = _mcp_allow()
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_response(
                tool_name="search_docs",
                arguments={},
                result="Safe search results",
                metadata={},
            )
            assert decision.action == "allow"
        inspector.close()

    def test_inspect_response_block_pii(self):
        """Test inspect_response blocks response with PII."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
        )
        mock_client = MagicMock()
        mock_client.inspect_response.return_value = MCPInspectResponse(
            result=InspectResponse(
                classifications=[Classification.PRIVACY_VIOLATION],
                is_safe=False,
                action=Action.BLOCK,
                explanation="PII: PRIVACY_VIOLATION",
            ),
            id=1,
        )
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = inspector.inspect_response(
                tool_name="get_user",
                arguments={},
                result="SSN: 123-45-6789",
                metadata={},
            )
            assert decision.action == "block"
            assert any("PRIVACY_VIOLATION" in r or "PII" in r for r in decision.reasons)
        inspector.close()


class TestMCPInspectorAsync:
    """Test async methods (Task Group 5)."""

    @pytest.mark.asyncio
    async def test_ainspect_request_no_api_configured(self):
        """Test ainspect_request allows when no API configured."""
        with patch.dict(os.environ, {}, clear=False):
            for var in ["AI_DEFENSE_API_MODE_MCP_API_KEY", "AI_DEFENSE_API_MODE_MCP_ENDPOINT",
                       "AI_DEFENSE_API_MODE_LLM_API_KEY", "AI_DEFENSE_API_MODE_LLM_ENDPOINT"]:
                os.environ.pop(var, None)
            
            inspector = MCPInspector()
            
            decision = await inspector.ainspect_request(
                tool_name="test_tool",
                arguments={},
                metadata={},
            )
            
            assert decision.action == "allow"
            inspector.close()

    @pytest.mark.asyncio
    async def test_ainspect_response_no_api_configured(self):
        """Test ainspect_response allows when no API configured."""
        with patch.dict(os.environ, {}, clear=False):
            for var in ["AI_DEFENSE_API_MODE_MCP_API_KEY", "AI_DEFENSE_API_MODE_MCP_ENDPOINT",
                       "AI_DEFENSE_API_MODE_LLM_API_KEY", "AI_DEFENSE_API_MODE_LLM_ENDPOINT"]:
                os.environ.pop(var, None)
            
            inspector = MCPInspector()
            
            decision = await inspector.ainspect_response(
                tool_name="test_tool",
                arguments={},
                result="Some result",
                metadata={},
            )
            
            assert decision.action == "allow"
            inspector.close()

    @pytest.mark.asyncio
    async def test_ainspect_request_error_handling(self):
        """Test ainspect_request error handling with fail_open=True."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
            fail_open=True,
        )
        mock_client = MagicMock()
        mock_client.inspect_tool_call.side_effect = httpx.ConnectError("Connection failed")
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = await inspector.ainspect_request(
                tool_name="test_tool",
                arguments={},
                metadata={},
            )
            assert decision.action == "allow"
            assert any("fail_open" in r for r in decision.reasons)
        inspector.close()

    @pytest.mark.asyncio
    async def test_ainspect_request_prompts_get(self):
        """Test ainspect_request with prompts/get method."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
        )
        mock_client = MagicMock()
        mock_client.inspect.return_value = _mcp_allow()
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = await inspector.ainspect_request(
                tool_name="code_review_prompt",
                arguments={"language": "python"},
                metadata={},
                method="prompts/get",
            )
            assert decision.action == "allow"
        inspector.close()

    @pytest.mark.asyncio
    async def test_ainspect_request_resources_read(self):
        """Test ainspect_request with resources/read method."""
        inspector = MCPInspector(
            api_key=API_KEY_64,
            endpoint="https://test.example.com",
        )
        mock_client = MagicMock()
        mock_client.inspect_resource_read.return_value = _mcp_allow()
        with patch.object(inspector, "_get_mcp_client", return_value=mock_client):
            decision = await inspector.ainspect_request(
                tool_name="file:///config.yaml",
                arguments={},
                metadata={},
                method="resources/read",
            )
            assert decision.action == "allow"
        inspector.close()
