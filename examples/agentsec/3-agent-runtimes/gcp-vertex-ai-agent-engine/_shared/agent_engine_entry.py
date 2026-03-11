"""
Vertex AI Agent Engine entry point class.

Defined inside the _shared package to ensure it is included in the
Agent Engine extra_packages bundle and importable at runtime.
"""

from _shared.agent_factory import invoke_agent


class SREAgent:
    """
    Vertex AI Agent Engine compatible agent.

    Implements query() so it can be deployed as a custom agent.
    """

    def set_up(self) -> None:
        """Optional setup hook for Agent Engine."""
        return None

    def query(self, input: str) -> dict:
        """
        Process a single prompt and return a response.

        Args:
            input: User prompt.
        Returns:
            Dict with input/output fields.
        """
        try:
            result = invoke_agent(input)
            return {
                "input": input,
                "output": result,
                "status": "success",
            }
        except Exception as exc:
            return {
                "input": input,
                "output": str(exc),
                "status": "error",
            }
