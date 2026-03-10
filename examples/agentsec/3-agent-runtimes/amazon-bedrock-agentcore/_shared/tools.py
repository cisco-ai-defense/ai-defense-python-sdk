"""Demo tools for the SRE agent.

These tools simulate SRE operations for demonstration purposes.
"""

import random
from strands import tool

STATUSES = ("healthy", "degraded", "down")


@tool
def add(a: float, b: float) -> float:
    """Add two numbers together.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
    """
    return a + b


@tool
def check_service_health(service: str) -> str:
    """Check the health status of a service.
    
    Args:
        service: Name of the service to check
        
    Returns:
        Health status message (simulated)
    """
    status = random.choice(STATUSES)
    return f"{service}: {status} (simulated)"


@tool
def summarize_log(text: str) -> str:
    """Summarize a log file or log text.
    
    Args:
        text: The log text to summarize
        
    Returns:
        Summary of the log (simulated)
    """
    summary = random.choice(("Good Summary", "Bad Summary", "Needs review"))
    text_length = len(text or "")
    return f"Summary ({text_length} chars): {summary} (simulated)"
