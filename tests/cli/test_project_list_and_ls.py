"""Tests for project list display and project ls routing behavior."""

import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from typer.testing import CliRunner

from basic_memory.cli.app import app
from basic_memory.mcp.clients.project import ProjectClient
from basic_memory.schemas.project_info import ProjectList

# Importing registers project subcommands on the shared app instance.
import basic_memory.cli.commands.project as project_cmd  # noqa: F401


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def write_config(tmp_path, monkeypatch):
    """Write config.json under a temporary HOME and return the file path."""

    def _write(config_data: dict) -> Path:
        from basic_memory import config as config_module

        config_module._CONFIG_CACHE = None
        config_module._CONFIG_MTIME = None
        config_module._CONFIG_SIZE = None

        config_dir = tmp_path / ".basic-memory"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps(config_data, indent=2))
        monkeypatch.setenv("HOME", str(tmp_path))
        return config_file

    return _write


@pytest.fixture
def mock_client(monkeypatch):
    """Mock get_client with a no-op async context manager."""

    @asynccontextmanager
    async def fake_get_client():
        yield object()

    monkeypatch.setattr(project_cmd, "get_client", fake_get_client)


def test_project_list_shows_local_projects(
    runner: CliRunner, write_config, mock_client, tmp_path, monkeypatch
):
    """project list should show local project paths and mode."""
    alpha_local = (tmp_path / "alpha-local").as_posix()

    write_config(
        {
            "env": "dev",
            "projects": {
                "alpha": {"path": alpha_local, "mode": "local"},
            },
            "default_project": "alpha",
        }
    )

    local_payload = {
        "projects": [
            {
                "id": 1,
                "external_id": "11111111-1111-1111-1111-111111111111",
                "name": "alpha",
                "path": alpha_local,
                "is_default": True,
            }
        ],
        "default_project": "alpha",
    }

    async def fake_list_projects(self):
        return ProjectList.model_validate(local_payload)

    monkeypatch.setattr(ProjectClient, "list_projects", fake_list_projects)

    result = runner.invoke(app, ["project", "list"], env={"COLUMNS": "240"})

    assert result.exit_code == 0, f"Exit code: {result.exit_code}, output: {result.stdout}"
    assert "alpha" in result.stdout
    assert "alpha-local" in result.stdout


def test_project_list_shows_display_name_for_private_projects(
    runner: CliRunner, write_config, mock_client, tmp_path, monkeypatch
):
    """Private projects should show display_name ('My Project') instead of raw UUID name."""
    private_uuid = "f1df8f39-d5aa-4095-ae05-8c5a2883029a"

    write_config(
        {
            "env": "dev",
            "projects": {},
            "default_project": "main",
        }
    )

    local_payload = {
        "projects": [
            {
                "id": 1,
                "external_id": "11111111-1111-1111-1111-111111111111",
                "name": "main",
                "path": "/main",
                "is_default": True,
            },
            {
                "id": 2,
                "external_id": "22222222-2222-2222-2222-222222222222",
                "name": private_uuid,
                "path": f"/{private_uuid}",
                "is_default": False,
                "display_name": "My Project",
                "is_private": True,
            },
        ],
        "default_project": "main",
    }

    async def fake_list_projects(self):
        return ProjectList.model_validate(local_payload)

    monkeypatch.setattr(ProjectClient, "list_projects", fake_list_projects)

    result = runner.invoke(app, ["project", "list"], env={"COLUMNS": "240"})

    assert result.exit_code == 0, f"Exit code: {result.exit_code}, output: {result.stdout}"

    # JSON output should preserve canonical name for scripting, with display_name as separate field
    json_result = runner.invoke(app, ["project", "list", "--json"], env={"COLUMNS": "240"})
    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    private_project = next(p for p in data["projects"] if p["name"] == private_uuid)
    assert private_project["name"] == private_uuid


def test_project_ls_local_mode_lists_files(
    runner: CliRunner, write_config, mock_client, tmp_path, monkeypatch
):
    """project ls for a local-mode project should list local files."""
    project_dir = tmp_path / "alpha-files"
    (project_dir / "docs").mkdir(parents=True, exist_ok=True)
    (project_dir / "notes.md").write_text("# local note")
    (project_dir / "docs" / "spec.md").write_text("# spec")

    write_config(
        {
            "env": "dev",
            "projects": {"alpha": {"path": project_dir.as_posix(), "mode": "local"}},
            "default_project": "alpha",
        }
    )

    payload = {
        "projects": [
            {
                "id": 1,
                "external_id": "11111111-1111-1111-1111-111111111111",
                "name": "alpha",
                "path": project_dir.as_posix(),
                "is_default": True,
            }
        ],
        "default_project": "alpha",
    }

    async def fake_list_projects(self):
        return ProjectList.model_validate(payload)

    monkeypatch.setattr(ProjectClient, "list_projects", fake_list_projects)

    result = runner.invoke(app, ["project", "ls", "--name", "alpha"], env={"COLUMNS": "200"})

    assert result.exit_code == 0, f"Exit code: {result.exit_code}, output: {result.stdout}"
    assert "Files in alpha" in result.stdout
    assert "notes.md" in result.stdout
    assert "docs/spec.md" in result.stdout
