# This prevents DEBUG logs from appearing on stdout during module-level
# initialization (e.g., template_loader.TemplateLoader() logs at DEBUG level).
from loguru import logger

logger.remove()

from typing import Optional  # noqa: E402

import typer  # noqa: E402

from agent_brain.cli.auto_update import maybe_run_periodic_auto_update  # noqa: E402
from agent_brain.cli.container import CliContainer, set_container  # noqa: E402
from agent_brain.config import init_cli_logging  # noqa: E402


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:  # pragma: no cover
        import agent_brain

        typer.echo(f"Agent Brain version: {agent_brain.__version__}")
        raise typer.Exit()


app = typer.Typer(name="agent-brain")


@app.callback()
def app_callback(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Agent Brain - Local-first personal knowledge management."""

    # Initialize logging for CLI (file only, no stdout)
    init_cli_logging()

    # --- Composition Root ---
    # Create container and read config (single point of config access)
    container = CliContainer.create()
    set_container(container)

    # Register post-command auto-update check
    ctx.call_on_close(lambda: maybe_run_periodic_auto_update(ctx.invoked_subcommand))

    # Run initialization for commands that don't use the API
    # Skip for 'mcp' command - it has its own lifespan that handles initialization
    # Skip for API-using commands (status, sync, etc.) - they handle initialization via deps.py
    # Skip for 'reset' command - it manages its own database lifecycle
    skip_init_commands = {
        "doctor",
        "mcp",
        "schema",
        "status",
        "sync",
        "project",
        "tool",
        "reset",
        "reindex",
        "update",
        "watch",
    }
    if (
        not version
        and ctx.invoked_subcommand is not None
        and ctx.invoked_subcommand not in skip_init_commands
    ):
        from agent_brain.services.initialization import ensure_initialization

        ensure_initialization(container.config)


## import
# Register sub-command groups
import_app = typer.Typer(help="Import data from various sources")
app.add_typer(import_app, name="import")

claude_app = typer.Typer(help="Import Conversations from Claude JSON export.")
import_app.add_typer(claude_app, name="claude")
