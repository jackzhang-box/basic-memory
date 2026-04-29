"""MCP composition root for Agent Brain.

This container owns reading ConfigManager and environment variables for the
MCP server entrypoint. Downstream modules receive config/dependencies explicitly
rather than reading globals.

Design principles:
- Only this module reads ConfigManager directly
- Runtime mode (cloud/local/test) is resolved here
- File sync decisions are centralized here
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from agent_brain.config import AgentBrainConfig, ConfigManager
from agent_brain.runtime import RuntimeMode, resolve_runtime_mode

if TYPE_CHECKING:  # pragma: no cover
    from agent_brain.sync import SyncCoordinator


@dataclass
class McpContainer:
    """Composition root for the MCP server entrypoint.

    Holds resolved configuration and runtime context.
    Created once at server startup, then used to wire dependencies.
    """

    config: AgentBrainConfig
    mode: RuntimeMode

    @classmethod
    def create(cls) -> "McpContainer":
        """Create container by reading ConfigManager.

        This is the single point where MCP reads global config.
        """
        config = ConfigManager().config
        mode = resolve_runtime_mode(
            is_test_env=config.is_test_env,
        )
        return cls(config=config, mode=mode)

    # --- Runtime Mode Properties ---

    @property
    def should_sync_files(self) -> bool:
        """Whether local file sync should be started.

        Sync is enabled when:
        - sync_changes is True in config
        - Not in test mode (tests manage their own sync)
        - Not in cloud mode (cloud handles sync differently)
        """
        return self.config.sync_changes and not self.mode.is_test

    @property
    def sync_skip_reason(self) -> str | None:
        """Reason why sync is skipped, or None if sync should run.

        Useful for logging why sync was disabled.
        """
        if self.mode.is_test:
            return "Test environment detected"
        if not self.config.sync_changes:
            return "Sync changes disabled"
        return None

    def create_sync_coordinator(self) -> "SyncCoordinator":
        """Create a SyncCoordinator with this container's settings.

        Returns:
            SyncCoordinator configured for this runtime environment
        """
        # Deferred import to avoid circular dependency
        from agent_brain.sync import SyncCoordinator

        return SyncCoordinator(
            config=self.config,
            should_sync=self.should_sync_files,
            skip_reason=self.sync_skip_reason,
        )


# Module-level container instance (set by lifespan)
_container: McpContainer | None = None


def get_container() -> McpContainer:
    """Get the current MCP container.

    Raises:
        RuntimeError: If container hasn't been initialized
    """
    if _container is None:
        raise RuntimeError("MCP container not initialized. Call set_container() first.")
    return _container


def set_container(container: McpContainer) -> None:
    """Set the MCP container (called by lifespan)."""
    global _container
    _container = container
