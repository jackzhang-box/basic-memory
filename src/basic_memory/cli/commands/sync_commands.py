"""Git sync CLI commands for Basic Memory.

Provides `bm sync init|push|pull|status|config` for sharing knowledge
between team members via an internal git remote.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Optional

import typer
from loguru import logger
from rich.console import Console

from basic_memory.cli.app import app
from basic_memory.config import ConfigManager, ProjectMode

console = Console()

sync_app = typer.Typer(help="Git sync commands for shared knowledge")
app.add_typer(sync_app, name="sync")


def _resolve_project(project: str | None) -> tuple[str, Path]:
    """Resolve project name and path from CLI argument or config default."""
    cm = ConfigManager()
    if project:
        name, path = cm.get_project(project)
        if not name or not path:
            console.print(f"[red]Project not found: {project}[/red]")
            raise typer.Exit(1)
        return name, Path(path)

    default = cm.default_project
    if not default:
        console.print("[red]No default project set. Use --project or set a default.[/red]")
        raise typer.Exit(1)

    name, path = cm.get_project(default)
    return name, Path(path)  # type: ignore[arg-type]


@sync_app.command("init")
def sync_init(
    project: Annotated[
        Optional[str],
        typer.Option("--project", "-p", help="Project name"),
    ] = None,
    remote: Annotated[
        str,
        typer.Option("--remote", "-r", help="Git remote URL"),
    ] = ...,  # type: ignore[assignment]
    branch: Annotated[
        str,
        typer.Option("--branch", "-b", help="Git branch"),
    ] = "main",
) -> None:
    """Initialize git sync for a project.

    Sets up a git repo, configures the remote, and updates project config to GIT mode.

    Example:\n
        bm sync init --project research --remote git@github.internal:team/research-kb.git
    """
    from basic_memory.sync.git_sync import GitSyncBackend

    name, project_path = _resolve_project(project)

    async def _init():
        backend = GitSyncBackend(project_path)
        await backend.init_repo()
        await backend.configure_remote(remote)

    asyncio.run(_init())

    # Update project config to GIT mode
    cm = ConfigManager()
    cm.update_project(name, mode=ProjectMode.GIT, git_remote_url=remote, git_branch=branch)

    console.print(f"[green]Initialized git sync for '{name}'[/green]")
    console.print(f"  Remote: {remote}")
    console.print(f"  Branch: {branch}")


@sync_app.command("push")
def sync_push(
    project: Annotated[
        Optional[str],
        typer.Option("--project", "-p", help="Project name"),
    ] = None,
    message: Annotated[
        Optional[str],
        typer.Option("-m", "--message", help="Commit message"),
    ] = None,
) -> None:
    """Stage, commit, and push changes to the remote.

    Example:\n
        bm sync push --project research -m "Add meeting notes"
    """
    from basic_memory.sync.git_sync import GitSyncBackend

    name, project_path = _resolve_project(project)

    async def _push():
        backend = GitSyncBackend(project_path)
        return await backend.push(message=message)

    result = asyncio.run(_push())

    if result.success:
        if result.files_committed == 0:
            console.print(f"[dim]{name}: Nothing to push[/dim]")
        else:
            console.print(
                f"[green]{name}: Pushed {result.files_committed} file(s)[/green]"
                f"  ({result.commit_sha[:8] if result.commit_sha else ''})"
            )
    else:
        console.print(f"[red]{name}: {result.message}[/red]")
        raise typer.Exit(1)


@sync_app.command("pull")
def sync_pull(
    project: Annotated[
        Optional[str],
        typer.Option("--project", "-p", help="Project name"),
    ] = None,
) -> None:
    """Pull changes from the remote.

    Example:\n
        bm sync pull --project research
    """
    from basic_memory.sync.git_sync import GitSyncBackend

    name, project_path = _resolve_project(project)

    async def _pull():
        backend = GitSyncBackend(project_path)
        return await backend.pull()

    result = asyncio.run(_pull())

    if result.success:
        if result.files_updated == 0:
            console.print(f"[dim]{name}: Already up to date[/dim]")
        else:
            console.print(f"[green]{name}: Pulled {result.files_updated} file(s)[/green]")
    else:
        if result.has_conflicts:
            console.print(f"[yellow]{name}: Merge conflicts detected:[/yellow]")
            for f in result.conflict_files:
                console.print(f"  - {f}")
            console.print("[yellow]Resolve conflicts manually, then run `bm sync push`.[/yellow]")
        else:
            console.print(f"[red]{name}: {result.message}[/red]")
        raise typer.Exit(1)


@sync_app.command("status")
def sync_status(
    project: Annotated[
        Optional[str],
        typer.Option("--project", "-p", help="Project name"),
    ] = None,
) -> None:
    """Show git sync status for a project.

    Example:\n
        bm sync status --project research
    """
    from basic_memory.sync.git_sync import GitSyncBackend

    name, project_path = _resolve_project(project)

    async def _status():
        backend = GitSyncBackend(project_path)
        return await backend.status()

    status = asyncio.run(_status())

    if not status.is_repo:
        console.print(f"[yellow]{name}: Not a git repository[/yellow]")
        console.print("Run `bm sync init` to set up git sync.")
        return

    console.print(f"[bold]{name}[/bold] git sync status:")
    console.print(f"  Branch: {status.branch or 'unknown'}")
    console.print(f"  Remote: {status.remote_url or 'not configured'}")
    console.print(f"  Clean:  {'yes' if status.is_clean else f'no ({status.files_changed} changed)'}")
    if status.has_remote:
        console.print(f"  Ahead:  {status.ahead}")
        console.print(f"  Behind: {status.behind}")


@sync_app.command("config")
def sync_config(
    project: Annotated[
        Optional[str],
        typer.Option("--project", "-p", help="Project name"),
    ] = None,
    remote: Annotated[
        Optional[str],
        typer.Option("--remote", "-r", help="Update git remote URL"),
    ] = None,
    branch: Annotated[
        Optional[str],
        typer.Option("--branch", "-b", help="Update git branch"),
    ] = None,
) -> None:
    """Update git sync configuration for a project.

    Example:\n
        bm sync config --project research --remote git@new-host:team/kb.git
    """
    if not remote and not branch:
        console.print("[yellow]Specify --remote or --branch to update.[/yellow]")
        raise typer.Exit(1)

    name, project_path = _resolve_project(project)
    cm = ConfigManager()

    kwargs: dict = {}
    if remote:
        from basic_memory.sync.git_sync import GitSyncBackend

        asyncio.run(GitSyncBackend(project_path).configure_remote(remote))
        kwargs["git_remote_url"] = remote

    if branch:
        kwargs["git_branch"] = branch

    cm.update_project(name, **kwargs)
    console.print(f"[green]Updated sync config for '{name}'[/green]")
