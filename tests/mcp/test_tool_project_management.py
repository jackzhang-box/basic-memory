"""Tests for MCP project management tools."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from agent_brain import db
from agent_brain.mcp.tools import list_memory_projects, create_memory_project, delete_project
from agent_brain.models.project import Project
from agent_brain.schemas.project_info import ProjectItem, ProjectList


# --- Helpers ---


def _make_project(
    name: str,
    path: str,
    *,
    id: int = 1,
    external_id: str = "00000000-0000-0000-0000-000000000001",
    is_default: bool = False,
    display_name: str | None = None,
    is_private: bool = False,
) -> ProjectItem:
    return ProjectItem(
        id=id,
        external_id=external_id,
        name=name,
        path=path,
        is_default=is_default,
        display_name=display_name,
        is_private=is_private,
    )


def _make_list(projects: list[ProjectItem], default: str | None = None) -> ProjectList:
    return ProjectList(projects=projects, default_project=default)


# --- Existing tests ---


@pytest.mark.asyncio
async def test_list_memory_projects_unconstrained(app, test_project):
    result = await list_memory_projects()
    assert "Available projects:" in result
    assert f"• {test_project.name}" in result


@pytest.mark.asyncio
async def test_list_memory_projects_shows_display_name(app, client, test_project):
    """When a project has display_name set, list_memory_projects shows 'display_name (name)' format."""
    mock_project = _make_project(
        "private-fb83af23",
        "/tmp/private",
        id=1,
        display_name="My Notes",
        is_private=True,
    )
    regular_project = _make_project(
        "main",
        "/tmp/main",
        id=2,
        external_id="00000000-0000-0000-0000-000000000002",
        is_default=True,
    )
    mock_list = _make_list([regular_project, mock_project], default="main")

    with patch(
        "agent_brain.mcp.clients.project.ProjectClient.list_projects",
        new_callable=AsyncMock,
        return_value=mock_list,
    ):
        result = await list_memory_projects()

    # Regular project shows name with source label
    assert "• main (local)" in result
    # Private project shows display_name with slug in parentheses, then source
    assert "• My Notes (private-fb83af23) (local)" in result


@pytest.mark.asyncio
async def test_list_memory_projects_no_display_name_shows_name_only(app, client, test_project):
    """When a project has no display_name, list_memory_projects shows just the name."""
    project = _make_project("my-project", "/tmp/my-project", is_default=True)
    mock_list = _make_list([project], default="my-project")

    with patch(
        "agent_brain.mcp.clients.project.ProjectClient.list_projects",
        new_callable=AsyncMock,
        return_value=mock_list,
    ):
        result = await list_memory_projects()

    assert "• my-project (local)" in result


@pytest.mark.asyncio
async def test_list_memory_projects_constrained_env(monkeypatch, app, test_project):
    monkeypatch.setenv("AGENT_BRAIN_MCP_PROJECT", test_project.name)
    result = await list_memory_projects()
    assert f"Project: {test_project.name}" in result
    assert "constrained to a single project" in result


@pytest.mark.asyncio
async def test_create_and_delete_project_and_name_match_branch(
    app, tmp_path_factory, session_maker
):
    # Create a project through the tool (exercises POST + response formatting).
    project_root = tmp_path_factory.mktemp("extra-project-home")
    result = await create_memory_project(
        project_name="My Project",
        project_path=str(project_root),
        set_default=False,
    )
    assert result.startswith("✓")
    assert "My Project" in result

    # Make permalink intentionally not derived from name so delete_project hits the name-match branch.
    async with db.scoped_session(session_maker) as session:
        project = (
            await session.execute(select(Project).where(Project.name == "My Project"))
        ).scalar_one()
        project.permalink = "custom-permalink"
        await session.commit()

    delete_result = await delete_project("My Project")
    assert delete_result.startswith("✓")


@pytest.mark.asyncio
async def test_list_memory_projects_json_output(app, test_project):
    """JSON output includes source fields for local projects."""
    local_main = _make_project("main", "/home/user/agent-brain", is_default=True)
    local_list = _make_list([local_main], default="main")

    with patch(
        "agent_brain.mcp.clients.project.ProjectClient.list_projects",
        new_callable=AsyncMock,
        return_value=local_list,
    ):
        result = await list_memory_projects(output_format="json")

    assert isinstance(result, dict)
    projects = result["projects"]
    assert result["default_project"] == "main"

    # Find projects by name
    by_name = {p["name"]: p for p in projects}

    # main: local only
    main_proj = by_name["main"]
    assert main_proj["source"] == "local"
    assert main_proj["path"] == "/home/user/agent-brain"
    assert main_proj["is_default"] is True
