"""Pytest configuration for _shared tests."""

import sys
from pathlib import Path

# Add _shared directory to path so imports work
_shared_dir = Path(__file__).parent.parent
_parent_dir = _shared_dir.parent  # 2_agent-frameworks

# Add both directories to ensure imports work
for path in [str(_shared_dir), str(_parent_dir)]:
    if path not in sys.path:
        sys.path.insert(0, path)
