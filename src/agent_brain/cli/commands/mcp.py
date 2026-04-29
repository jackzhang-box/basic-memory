"""MCP server command with streamable HTTP transport."""

import os
import threading
from typing import Any, Optional

import typer
from loguru import logger

from agent_brain.cli.app import app
from agent_brain.cli.auto_update import AutoUpdateStatus, run_auto_update
from agent_brain.config import ConfigManager, init_mcp_logging


class _DeferredMcpServer:
    def run(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        from agent_brain.mcp.server import mcp as live_mcp_server

        live_mcp_server.run(*args, **kwargs)


# Keep module-level attribute for tests/monkeypatching while deferring heavy import.
mcp_server = _DeferredMcpServer()


@app.command()
def mcp(
    transport: str = typer.Option("stdio", help="Transport type: stdio, streamable-http, or sse"),
    host: str = typer.Option(
        "0.0.0.0", help="Host for HTTP transports (use 0.0.0.0 to allow external connections)"
    ),
    port: int = typer.Option(8000, help="Port for HTTP transports"),
    path: str = typer.Option("/mcp", help="Path prefix for streamable-http transport"),
    project: Optional[str] = typer.Option(None, help="Restrict MCP server to single project"),
):  # pragma: no cover
    """Run the MCP server with configurable transport options.

    This command starts an MCP server using one of three transport options:

    - stdio: Standard I/O (good for local usage)
    - streamable-http: Recommended for web deployments
    - sse: Server-Sent Events (for compatibility with existing clients)

    Initialization, file sync, and cleanup are handled by the MCP server's lifespan.

    Note: This command is available regardless of cloud mode setting.
    Users who have cloud mode enabled can still use local MCP for Claude Code
    and Claude Desktop while using cloud MCP for web and mobile access.
    """
    # --- Routing setup ---
    # Trigger: MCP server command invocation.
    # Why: HTTP/SSE transports serve as local API endpoints and must always
    #      route locally. Stdio defaults to local routing as well.
    # Outcome: HTTP/SSE get explicit local override; stdio uses default routing.
    if transport in ("streamable-http", "sse"):
        os.environ["AGENT_BRAIN_FORCE_LOCAL"] = "true"

    # Import mcp tools/prompts to register them with the server
    import agent_brain.mcp.tools  # noqa: F401  # pragma: no cover
    import agent_brain.mcp.prompts  # noqa: F401  # pragma: no cover
    import agent_brain.mcp.resources  # noqa: F401  # pragma: no cover

    # Initialize logging for MCP (file only, stdout breaks protocol)
    init_mcp_logging()

    # Validate and set project constraint if specified
    if project:
        config_manager = ConfigManager()
        project_name, _ = config_manager.get_project(project)
        if not project_name:
            typer.echo(f"No project found named: {project}", err=True)
            raise typer.Exit(1)

        # Set env var with validated project name
        os.environ["AGENT_BRAIN_MCP_PROJECT"] = project_name
        logger.info(f"MCP server constrained to project: {project_name}")

    def _run_background_auto_update() -> None:
        result = run_auto_update(force=False, check_only=False, silent=True)
        if result.restart_recommended:
            logger.info(
                "A newer Agent Brain version was installed and will apply on next restart."
            )
        elif result.status == AutoUpdateStatus.FAILED and result.error:
            logger.warning(f"MCP background auto-update failed: {result.error}")

    # Trigger: stdio transport corresponds to local user installs.
    # Why: server transports (HTTP/SSE) run in managed environments where
    # package-manager self-upgrades are inappropriate.
    # Outcome: background auto-update runs only for local stdio MCP sessions.
    if transport == "stdio":
        threading.Thread(target=_run_background_auto_update, daemon=True).start()

    # Run the MCP server (blocks)
    # Lifespan handles: initialization, migrations, file sync, cleanup
    logger.info(f"Starting MCP server with {transport.upper()} transport")

    if transport == "stdio":
        mcp_server.run(
            transport=transport,
        )
    elif transport == "streamable-http" or transport == "sse":
        mcp_server.run(
            transport=transport,
            host=host,
            port=port,
            path=path,
            log_level="INFO",
        )
