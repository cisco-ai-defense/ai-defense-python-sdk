"""Tests for agentsec config module (validation constants only)."""

from aidefense.runtime.agentsec.config import VALID_MODES, VALID_GATEWAY_MODES, VALID_INTEGRATION_MODES


def test_valid_modes():
    assert "off" in VALID_MODES
    assert "monitor" in VALID_MODES
    assert "enforce" in VALID_MODES


def test_valid_gateway_modes():
    assert "on" in VALID_GATEWAY_MODES
    assert "off" in VALID_GATEWAY_MODES


def test_valid_integration_modes():
    assert "api" in VALID_INTEGRATION_MODES
    assert "gateway" in VALID_INTEGRATION_MODES
