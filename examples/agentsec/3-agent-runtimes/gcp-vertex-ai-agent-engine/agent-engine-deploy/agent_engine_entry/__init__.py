"""
Agent Engine entry point package.

This package provides the entry point for Vertex AI Agent Engine deployment.
The agent is a simple callable wrapper around the invoke_agent function.
"""
from .entry import agent

__all__ = ["agent"]
