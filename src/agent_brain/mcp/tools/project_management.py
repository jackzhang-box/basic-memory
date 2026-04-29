"""Project management tools for Agent Brain MCP server.

These tools allow users to switch between projects, list available projects,
and manage project context during conversations.
"""

import os
from typing import Literal

from fastmcp import Context
from loguru import logger

from agent_brain.mcp.async_client import get_client
from agent_brain.mcp.server import mcp
from agent_brain.schemas.project_info import ProjectInfoRequest
from agent_brain.utils import generate_permalink


def _format_project_list_text(merged: list[dict]) -> str:
    """Format merged project list as human-readable text."""
    result = "Available projects:\n"
    for project in merged:
        display_name = project["display_name"]
        name = project["name"]
        label = f"{display_name} ({name})" if display_name else name
        source = project["source"]
        result += f"• {label} ({source})\n"

    result += "\n" + "─" * 40 + "\n"
    result += "Next: Ask which project to use for this session.\n"
    result += "Example: 'Which project should I use for this task?'\n\n"
    result += (
        "Session reminder: Track the selected project for all subsequent "
        "operations in this conversation.\n"
    )
    result += "The user can say 'switch to [project]' to change projects."
    return result


def _format_project_list_json(
    merged: list[dict],
    default_project: str | None,
    constrained_project: str | None,
) -> dict:
    """Format merged project list as structured JSON."""
    return {
        "projects": merged,
        "default_project": default_project,
        "constrained_project": constrained_project,
    }


@mcp.tool(
    "list_memory_projects",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
async def list_memory_projects(
    output_format: Literal["text", "json"] = "text",
    context: Context | None = None,
) -> str | dict:
    """List all available projects with their status.

    Args:
        output_format: "text" returns the existing human-readable project list.
            "json" returns structured project metadata.
        context: Optional FastMCP context for progress/status logging.
    """
    if context:  # pragma: no cover
        await context.info("Listing all available projects")

    constrained_project = os.environ.get("AGENT_BRAIN_MCP_PROJECT")

    from agent_brain.mcp.clients import ProjectClient

    # Fetch projects via the client (factory mode or local ASGI)
    async with get_client() as client:
        project_client = ProjectClient(client)
        project_list = await project_client.list_projects()

    # Build merged list from local projects
    merged: list[dict] = []
    for project in sorted(project_list.projects, key=lambda p: p.name):
        merged.append(
            {
                "name": project.name,
                "path": project.path,
                "source": "local",
                "is_default": project.is_default
                or project_list.default_project == project.name,
                "is_private": project.is_private,
                "display_name": project.display_name,
            }
        )

    default_project = project_list.default_project

    if output_format == "json":
        return _format_project_list_json(merged, default_project, constrained_project)

    if constrained_project:
        return _format_constrained_text(constrained_project)

    return _format_project_list_text(merged)


def _format_constrained_text(constrained_project: str) -> str:
    """Format text output when the MCP server is constrained to a single project."""
    result = f"Project: {constrained_project}\n\n"
    result += "Note: This MCP server is constrained to a single project.\n"
    result += "All operations will automatically use this project."
    return result


@mcp.tool(
    "create_memory_project",
    annotations={"destructiveHint": False, "openWorldHint": False},
)
async def create_memory_project(
    project_name: str,
    project_path: str,
    set_default: bool = False,
    output_format: Literal["text", "json"] = "text",
    context: Context | None = None,
) -> str | dict:
    """Create a new Agent Brain project.

    Creates a new project with the specified name and path. The project directory
    will be created if it doesn't exist. Optionally sets the new project as default.

    Args:
        project_name: Name for the new project (must be unique)
        project_path: File system path where the project will be stored
        set_default: Whether to set this project as the default (optional, defaults to False)
        output_format: "text" returns the existing human-readable result text.
            "json" returns structured project creation metadata.
        context: Optional FastMCP context for progress/status logging.

    Returns:
        Confirmation message with project details

    Example:
        create_memory_project("my-research", "~/Documents/research")
        create_memory_project("work-notes", "/home/user/work", set_default=True)
    """
    async with get_client() as client:
        # Check if server is constrained to a specific project
        constrained_project = os.environ.get("AGENT_BRAIN_MCP_PROJECT")
        if constrained_project:
            if output_format == "json":
                return {
                    "name": project_name,
                    "path": project_path,
                    "is_default": False,
                    "created": False,
                    "already_exists": False,
                    "error": "PROJECT_CONSTRAINED",
                    "message": (
                        f"Project creation disabled - MCP server is constrained to project "
                        f"'{constrained_project}'."
                    ),
                }
            return f'# Error\n\nProject creation disabled - MCP server is constrained to project \'{constrained_project}\'.\nUse the CLI to create projects: `agent-brain project add "{project_name}" "{project_path}"`'

        if context:  # pragma: no cover
            await context.info(f"Creating project: {project_name} at {project_path}")

        # Create the project request
        project_request = ProjectInfoRequest(
            name=project_name, path=project_path, set_default=set_default
        )

        # Import here to avoid circular import
        from agent_brain.mcp.clients import ProjectClient

        # Use typed ProjectClient for API calls
        project_client = ProjectClient(client)
        existing = await project_client.list_projects()
        existing_match = next(
            (p for p in existing.projects if p.name.casefold() == project_name.casefold()),
            None,
        )
        if existing_match:
            is_default = bool(
                existing_match.is_default or existing.default_project == existing_match.name
            )
            if output_format == "json":
                return {
                    "name": existing_match.name,
                    "path": existing_match.path,
                    "is_default": is_default,
                    "created": False,
                    "already_exists": True,
                }
            return (
                f"✓ Project already exists: {existing_match.name}\n\n"
                f"Project Details:\n"
                f"• Name: {existing_match.name}\n"
                f"• Path: {existing_match.path}\n"
                f"{'• Set as default project\n' if is_default else ''}"
                "\nProject is already available for use in tool calls.\n"
            )

        status_response = await project_client.create_project(project_request.model_dump())

        if output_format == "json":
            new_project = status_response.new_project
            return {
                "name": new_project.name if new_project else project_name,
                "path": new_project.path if new_project else project_path,
                "is_default": bool(
                    (new_project.is_default if new_project else False) or set_default
                ),
                "created": True,
                "already_exists": False,
            }

        result = f"✓ {status_response.message}\n\n"

        if status_response.new_project:
            result += "Project Details:\n"
            result += f"• Name: {status_response.new_project.name}\n"
            result += f"• Path: {status_response.new_project.path}\n"

            if set_default:
                result += "• Set as default project\n"

        result += "\nProject is now available for use in tool calls.\n"
        result += f"Use '{project_name}' as the project parameter in MCP tool calls.\n"

        return result


@mcp.tool(
    annotations={"destructiveHint": True, "openWorldHint": False},
)
async def delete_project(project_name: str, context: Context | None = None) -> str:
    """Delete a Agent Brain project.

    Removes a project from the configuration and database. This does NOT delete
    the actual files on disk - only removes the project from Agent Brain's
    configuration and database records.

    Args:
        project_name: Name of the project to delete

    Returns:
        Confirmation message about project deletion

    Example:
        delete_project("old-project")

    Warning:
        This action cannot be undone. The project will need to be re-added
        to access its content through Agent Brain again.
    """
    async with get_client() as client:
        # Check if server is constrained to a specific project
        constrained_project = os.environ.get("AGENT_BRAIN_MCP_PROJECT")
        if constrained_project:
            return f"# Error\n\nProject deletion disabled - MCP server is constrained to project '{constrained_project}'.\nUse the CLI to delete projects: `agent-brain project remove \"{project_name}\"`"

        if context:  # pragma: no cover
            await context.info(f"Deleting project: {project_name}")

        # Import here to avoid circular import
        from agent_brain.mcp.clients import ProjectClient

        # Use typed ProjectClient for API calls
        project_client = ProjectClient(client)

        # Get project info before deletion to validate it exists
        project_list = await project_client.list_projects()

        # Find the project by permalink (derived from name).
        # Note: The API response uses `ProjectItem` which derives `permalink` from `name`,
        # so a separate case-insensitive name match would be redundant here.
        project_permalink = generate_permalink(project_name)
        target_project = None
        for p in project_list.projects:
            # Match by permalink (handles case-insensitive input)
            if p.permalink == project_permalink:
                target_project = p
                break

        if not target_project:
            available_projects = [p.name for p in project_list.projects]
            raise ValueError(
                f"Project '{project_name}' not found. Available projects: {', '.join(available_projects)}"
            )

        # Delete project using project external_id
        status_response = await project_client.delete_project(target_project.external_id)

        result = f"✓ {status_response.message}\n\n"

        if status_response.old_project:
            result += "Removed project details:\n"
            result += f"• Name: {status_response.old_project.name}\n"
            if hasattr(status_response.old_project, "path"):
                result += f"• Path: {status_response.old_project.path}\n"

        result += "Files remain on disk but project is no longer tracked by Agent Brain.\n"
        result += "Re-add the project to access its content again.\n"

        return result
