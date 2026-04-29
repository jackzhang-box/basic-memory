"""Dependency injection functions for agent-brain services.

DEPRECATED: This module is a backwards-compatibility shim.
Import from agent_brain.deps package submodules instead:
- agent_brain.deps.config for configuration
- agent_brain.deps.db for database/session
- agent_brain.deps.projects for project resolution
- agent_brain.deps.repositories for data access
- agent_brain.deps.services for business logic
- agent_brain.deps.importers for import functionality

This file will be removed once all callers are migrated.
"""

# Re-export everything from the deps package for backwards compatibility
from agent_brain.deps import *  # noqa: F401, F403  # pragma: no cover
