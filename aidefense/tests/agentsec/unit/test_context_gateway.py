"""Tests for gateway routing context (gateway, use_gateway, get_active_gateway)."""

import asyncio

import pytest

from aidefense.runtime.agentsec._context import (
    gateway,
    get_active_gateway,
    use_gateway,
)


class TestGatewayContext:
    """Tests for the gateway() context manager."""

    def test_no_active_gateway_by_default(self):
        assert get_active_gateway() is None

    def test_sync_context_sets_gateway(self):
        with gateway("math-gw"):
            assert get_active_gateway() == "math-gw"
        assert get_active_gateway() is None

    def test_nested_gateways(self):
        with gateway("outer"):
            assert get_active_gateway() == "outer"
            with gateway("inner"):
                assert get_active_gateway() == "inner"
            assert get_active_gateway() == "outer"
        assert get_active_gateway() is None

    @pytest.mark.asyncio
    async def test_async_context_sets_gateway(self):
        async with gateway("async-gw"):
            assert get_active_gateway() == "async-gw"
        assert get_active_gateway() is None

    @pytest.mark.asyncio
    async def test_async_nested(self):
        async with gateway("a"):
            assert get_active_gateway() == "a"
            async with gateway("b"):
                assert get_active_gateway() == "b"
            assert get_active_gateway() == "a"
        assert get_active_gateway() is None


class TestUseGatewayDecorator:
    """Tests for the @use_gateway decorator."""

    def test_sync_decorator(self):
        @use_gateway("dec-gw")
        def my_func():
            return get_active_gateway()

        result = my_func()
        assert result == "dec-gw"
        # After the function returns, gateway is reset
        assert get_active_gateway() is None

    @pytest.mark.asyncio
    async def test_async_decorator(self):
        @use_gateway("async-dec-gw")
        async def my_async_func():
            return get_active_gateway()

        result = await my_async_func()
        assert result == "async-dec-gw"
        assert get_active_gateway() is None

    def test_decorator_preserves_function_name(self):
        @use_gateway("test")
        def original_name():
            pass

        assert original_name.__name__ == "original_name"
