"""CLI routing utilities for --local flag handling.

This module provides utilities for CLI commands to override default routing.
The routing is controlled via environment variables:
- AGENT_BRAIN_FORCE_LOCAL: When "true", forces local ASGI transport
- Checked in agent_brain.mcp.async_client.get_client()
"""

import os
from contextlib import contextmanager
from typing import Generator


@contextmanager
def force_routing(local: bool = False) -> Generator[None, None, None]:
    """Context manager to temporarily override routing mode.

    Sets environment variables that are checked by get_client() to determine
    whether to use local ASGI transport.

    Args:
        local: If True, force local ASGI transport

    Usage:
        with force_routing(local=True):
            # All API calls will use local ASGI transport
            await some_api_call()
    """
    original_force_local = os.environ.get("AGENT_BRAIN_FORCE_LOCAL")

    try:
        if local:
            os.environ["AGENT_BRAIN_FORCE_LOCAL"] = "true"
        yield
    finally:
        if original_force_local is None:
            os.environ.pop("AGENT_BRAIN_FORCE_LOCAL", None)
        else:
            os.environ["AGENT_BRAIN_FORCE_LOCAL"] = original_force_local
