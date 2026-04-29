"""Configuration dependency injection for agent-brain.

This module provides configuration-related dependencies.
Note: Long-term goal is to minimize direct ConfigManager access
and inject config from composition roots instead.
"""

from typing import Annotated

from fastapi import Depends

from agent_brain.config import AgentBrainConfig, ConfigManager


def get_app_config() -> AgentBrainConfig:  # pragma: no cover
    """Get the application configuration.

    Note: This is a transitional dependency. The goal is for composition roots
    to read ConfigManager and inject config explicitly. During migration,
    this provides the same behavior as before.
    """
    app_config = ConfigManager().config
    return app_config


AppConfigDep = Annotated[AgentBrainConfig, Depends(get_app_config)]
